"""Virtual 3D viewer helpers for textual simulations."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .metrics import compute_layer_metrics, compute_sequence_metrics
from .models import LayerPlan, LayerSequencePlan, Vector3


@dataclass
class ViewerScene:
    """Summary of the pallet scene used by the viewer."""

    width: float
    depth: float
    height: float
    layers: int
    explode_gap: float = 0.0

    def exploded_height(self) -> float:
        extra = max(0, self.layers - 1) * max(self.explode_gap, 0.0)
        return self.height + extra


@dataclass
class VirtualCamera:
    """Minimal camera model controllable via CLI."""

    radius: float
    polar_deg: float
    azimuth_deg: float
    target: Vector3

    def rotate(self, delta_polar: float, delta_azimuth: float) -> None:
        self.polar_deg = min(max(self.polar_deg + delta_polar, 5.0), 175.0)
        self.azimuth_deg = (self.azimuth_deg + delta_azimuth) % 360

    def translate(self, dx: float, dy: float, dz: float) -> None:
        self.target = Vector3(self.target.x + dx, self.target.y + dy, self.target.z + dz)

    def zoom(self, delta: float) -> None:
        self.radius = max(10.0, self.radius + delta)

    def position(self) -> Vector3:
        polar = math.radians(self.polar_deg)
        azimuth = math.radians(self.azimuth_deg)
        x = self.target.x + self.radius * math.sin(polar) * math.cos(azimuth)
        y = self.target.y + self.radius * math.sin(polar) * math.sin(azimuth)
        z = self.target.z + self.radius * math.cos(polar)
        return Vector3(x, y, z)

    def view_vector(self) -> Vector3:
        pos = self.position()
        return Vector3(self.target.x - pos.x, self.target.y - pos.y, self.target.z - pos.z)


def build_scene(plan: LayerPlan | LayerSequencePlan, *, width: float, depth: float, explode_gap: float = 0.0) -> ViewerScene:
    """Create a viewer scene from a plan or sequence."""

    if isinstance(plan, LayerSequencePlan):
        height = plan.max_height()
        layers = plan.levels()
    else:
        height = _plan_height(plan)
        layers = 1
    return ViewerScene(width=width, depth=depth, height=height, layers=layers, explode_gap=explode_gap)


def summarize_metrics(plan: LayerPlan | LayerSequencePlan) -> dict[str, float | str]:
    """Return an extract of the metrics for reporting purposes."""

    if isinstance(plan, LayerSequencePlan):
        metrics = compute_sequence_metrics(plan)
        return {
            "mode": "sequence",
            "layers": metrics.layers,
            "total_boxes": metrics.total_boxes,
            "max_height_mm": metrics.max_height,
            "weight_kg": round(metrics.total_weight, 3),
        }
    metrics = compute_layer_metrics(plan)
    return {
        "mode": "layer",
        "layers": 1,
        "total_boxes": metrics.total_boxes,
        "max_height_mm": metrics.max_height,
        "weight_kg": round(metrics.total_weight, 3),
    }


def apply_camera_script(
    camera: VirtualCamera,
    rotations: Iterable[tuple[float, float]] | None = None,
    translations: Iterable[tuple[float, float, float]] | None = None,
    zooms: Iterable[float] | None = None,
) -> list[str]:
    """Apply scripted moves to the camera returning a textual log."""

    log: list[str] = []
    for delta_polar, delta_azimuth in rotations or []:
        camera.rotate(delta_polar, delta_azimuth)
        log.append(f"rotate Δpolar={delta_polar:.1f}° Δazimuth={delta_azimuth:.1f}°")
    for dx, dy, dz in translations or []:
        camera.translate(dx, dy, dz)
        log.append(f"translate dx={dx:.1f} dy={dy:.1f} dz={dz:.1f}")
    for delta in zooms or []:
        camera.zoom(delta)
        log.append(f"zoom Δr={delta:.1f}mm")
    return log


def describe_sequence_layers(plan: LayerSequencePlan) -> list[str]:
    """Produce human-readable lines describing each layer of a sequence."""

    lines: list[str] = []
    slip_levels = {placement.level for placement in plan.interleaves}
    for idx, layer in enumerate(plan.layers, start=1):
        blocks = ", ".join(layer.describe_blocks()) or "schema non disponibile"
        slip_note = " + falda" if idx in slip_levels else ""
        lines.append(
            "Layer {idx}: corner {corner} orient {orientation}° schema {blocks}{extra}".format(
                idx=idx,
                corner=layer.start_corner.upper(),
                orientation=layer.orientation,
                blocks=blocks,
                extra=slip_note,
            )
        )
    return lines


def _plan_height(plan: LayerPlan) -> float:
    if not plan.placements:
        return 0.0
    highest = max(placement.position.z for placement in plan.placements)
    return highest
