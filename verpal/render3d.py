"""Utilities to export VerPal plans as simple 3D models."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .models import (
    InterleafPlacement,
    LayerPlan,
    LayerRequest,
    LayerSequencePlan,
    Vector3,
)


Color = tuple[float, float, float]

_PALLET_COLOR: Color = (0.650, 0.466, 0.329)
_INTERLEAF_COLOR: Color = (0.900, 0.900, 0.900)
_COLOR_PALETTES: dict[str, tuple[Color, ...]] = {
    "classic": (
        (0.929, 0.490, 0.192),
        (0.231, 0.462, 0.788),
        (0.133, 0.545, 0.133),
        (0.850, 0.325, 0.098),
    ),
    "sunset": (
        (0.988, 0.537, 0.325),
        (0.984, 0.325, 0.486),
        (0.792, 0.286, 0.698),
        (0.427, 0.294, 0.741),
    ),
    "pastel": (
        (0.753, 0.898, 0.843),
        (0.929, 0.835, 0.851),
        (0.867, 0.914, 0.992),
        (0.945, 0.902, 0.733),
    ),
}


@dataclass(frozen=True)
class OBJExportResult:
    """Metadata returned after generating an OBJ file."""

    path: Path
    material_path: Path | None
    vertices: int
    faces: int
    boxes: int


def list_color_palettes() -> list[str]:
    """Return available palette names for the CLI choices."""

    return sorted(_COLOR_PALETTES.keys())


def export_layer_to_obj(
    plan: LayerPlan,
    request: LayerRequest,
    output: str | Path,
    *,
    include_pallet: bool = True,
    explode_gap: float = 0.0,
    palette: str = "classic",
    material_path: str | Path | None = None,
) -> OBJExportResult:
    """Export a single layer to Wavefront OBJ format."""

    return _export_layers_to_obj(
        [plan],
        request,
        output,
        include_pallet=include_pallet,
        explode_gap=explode_gap,
        interleaves=None,
        palette=palette,
        material_path=material_path,
    )


def export_sequence_to_obj(
    sequence: LayerSequencePlan,
    request: LayerRequest,
    output: str | Path,
    *,
    include_pallet: bool = True,
    explode_gap: float = 0.0,
    palette: str = "classic",
    material_path: str | Path | None = None,
) -> OBJExportResult:
    """Export the entire sequence to Wavefront OBJ format."""

    return _export_layers_to_obj(
        sequence.layers,
        request,
        output,
        include_pallet=include_pallet,
        explode_gap=explode_gap,
        interleaves=sequence.interleaves,
        palette=palette,
        material_path=material_path,
    )


def _export_layers_to_obj(
    layers: Sequence[LayerPlan],
    request: LayerRequest,
    output: str | Path,
    *,
    include_pallet: bool,
    explode_gap: float,
    interleaves: Sequence[InterleafPlacement] | None,
    palette: str,
    material_path: str | Path | None,
) -> OBJExportResult:
    if explode_gap < 0:
        raise ValueError("explode_gap deve essere maggiore o uguale a zero")

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["# VERPAL OBJ export"]
    mtl_lines: list[str] | None = None
    palette_name = palette or "classic"
    mtl_path: Path | None = None
    if material_path is not None:
        mtl_path = Path(material_path)
        mtl_path.parent.mkdir(parents=True, exist_ok=True)
        mtl_lines = _build_material_library(
            palette_name,
            layer_count=len(layers),
            include_pallet=include_pallet,
            include_interleaves=bool(interleaves),
        )
        lines.append(f"mtllib {mtl_path.name}")

    vertex_index = 1
    faces = 0
    box_count = 0

    if include_pallet:
        pallet_min = Vector3(0.0, 0.0, 0.0)
        pallet_max = Vector3(
            request.pallet.dimensions.width,
            request.pallet.dimensions.depth,
            request.pallet.dimensions.height,
        )
        if mtl_lines:
            lines.append("usemtl pallet")
        lines.append("o pallet")
        vertex_index = _append_prism(lines, pallet_min, pallet_max, vertex_index)
        faces += 6

    frame = request.reference_frame
    for layer_idx, layer in enumerate(layers):
        if not layer.placements:
            continue
        box_dims = layer.box.dimensions if layer.box else request.box.dimensions
        for placement in layer.placements:
            center = frame.restore(
                placement.position,
                pallet=request.pallet,
                overhang_x=request.overhang_x,
                overhang_y=request.overhang_y,
            )
            center = Vector3(center.x, center.y, center.z + layer_idx * explode_gap)
            width, depth = _footprint(box_dims.width, box_dims.depth, placement.rotation)
            half_w = width / 2
            half_d = depth / 2
            half_h = box_dims.height / 2
            min_corner = Vector3(
                center.x - half_w,
                center.y - half_d,
                center.z - half_h,
            )
            max_corner = Vector3(
                center.x + half_w,
                center.y + half_d,
                center.z + half_h,
            )
            if mtl_lines:
                lines.append(f"usemtl layer_{layer_idx + 1}")
            lines.append(f"o layer_{layer_idx + 1}_box_{placement.sequence_index}")
            vertex_index = _append_prism(lines, min_corner, max_corner, vertex_index)
            faces += 6
            box_count += 1

    if interleaves:
        for slip in interleaves:
            gap_offset = slip.level * explode_gap
            min_corner = Vector3(
                0.0,
                0.0,
                slip.z_position + gap_offset,
            )
            max_corner = Vector3(
                request.pallet.dimensions.width,
                request.pallet.dimensions.depth,
                slip.z_position + slip.interleaf.thickness + gap_offset,
            )
            if mtl_lines:
                lines.append("usemtl interleaf")
            lines.append(f"o interleaf_{slip.level}")
            vertex_index = _append_prism(lines, min_corner, max_corner, vertex_index)
            faces += 6

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if mtl_lines and mtl_path is not None:
        mtl_path.write_text("\n".join(mtl_lines) + "\n", encoding="utf-8")

    return OBJExportResult(
        path=path,
        material_path=mtl_path,
        vertices=vertex_index - 1,
        faces=faces,
        boxes=box_count,
    )


def _append_prism(
    lines: list[str],
    min_corner: Vector3,
    max_corner: Vector3,
    start_index: int,
) -> int:
    x0, y0, z0 = min_corner.x, min_corner.y, min_corner.z
    x1, y1, z1 = max_corner.x, max_corner.y, max_corner.z
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    for vx, vy, vz in vertices:
        lines.append(f"v {vx:.3f} {vy:.3f} {vz:.3f}")
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    for face in faces:
        indices = " ".join(str(start_index + idx) for idx in face)
        lines.append(f"f {indices}")
    return start_index + len(vertices)


def _footprint(width: float, depth: float, rotation: int) -> tuple[float, float]:
    if rotation % 180 == 0:
        return width, depth
    return depth, width


def _resolve_palette(name: str) -> tuple[Color, ...]:
    palette = _COLOR_PALETTES.get(name.lower())
    if not palette:
        raise ValueError(f"Palette colori '{name}' non supportata")
    return palette


def _build_material_library(
    palette_name: str,
    *,
    layer_count: int,
    include_pallet: bool,
    include_interleaves: bool,
) -> list[str]:
    palette = _resolve_palette(palette_name)
    if not palette:
        raise ValueError("Palette vuota: impossibile generare materiali")

    lines: list[str] = [f"# materials palette={palette_name}"]

    def _append_material(name: str, color: Color) -> None:
        lines.append(f"newmtl {name}")
        lines.append("Ka 0.200 0.200 0.200")
        lines.append(f"Kd {color[0]:.3f} {color[1]:.3f} {color[2]:.3f}")
        lines.append("d 1.0")
        lines.append("Ns 10.000")
        lines.append("")

    if include_pallet:
        _append_material("pallet", _PALLET_COLOR)

    for idx in range(layer_count):
        color = palette[idx % len(palette)]
        _append_material(f"layer_{idx + 1}", color)

    if include_interleaves:
        _append_material("interleaf", _INTERLEAF_COLOR)

    return lines

