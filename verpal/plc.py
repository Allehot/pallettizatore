"""Utilities to export plans toward Siemens PLC controllers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .annotations import PlacementAnnotator
from .metrics import LayerMetrics, SequenceMetrics, compute_layer_metrics, compute_sequence_metrics
from .models import LayerPlan, LayerSequencePlan


@dataclass(frozen=True)
class PLCRow:
    """Single placement entry translated for PLC consumption."""

    index: int
    layer: int
    block: str
    x: float
    y: float
    z: float
    rotation: int
    approach_direction: str | None
    approach_distance: float | None
    label_x: float | None
    label_y: float | None
    label_z: float | None


class SiemensPLCExporter:
    """Serialize VerPal plans into a deterministic S7-friendly text file."""

    def __init__(self, annotator: PlacementAnnotator | None = None) -> None:
        self.annotator = annotator or PlacementAnnotator()

    def to_file(self, plan: LayerPlan | LayerSequencePlan, filename: str | Path) -> Path:
        path = Path(filename)
        path.write_text(self._serialize(plan), encoding="utf-8")
        return path

    def to_payload(self, plan: LayerPlan | LayerSequencePlan) -> bytes:
        return self._serialize(plan).encode("utf-8")

    def _serialize(self, plan: LayerPlan | LayerSequencePlan) -> str:
        layers = plan.layers if isinstance(plan, LayerSequencePlan) else [plan]
        rows = self._build_rows(layers)
        metrics: LayerMetrics | SequenceMetrics
        if isinstance(plan, LayerSequencePlan):
            metrics = compute_sequence_metrics(plan)
            metadata = plan.metadata
            interleaves = plan.interleaves
        else:
            metrics = compute_layer_metrics(plan)
            metadata = plan.metadata
            interleaves = []

        lines: List[str] = ["#VERPAL-S7"]
        lines.append(f"layers={len(layers)}")
        lines.append(f"placements={len(rows)}")
        lines.append(f"total_weight={metrics.total_weight:.3f}kg")
        lines.append(
            "center_of_mass={:.1f},{:.1f},{:.1f}mm".format(
                metrics.center_of_mass.x,
                metrics.center_of_mass.y,
                metrics.center_of_mass.z,
            )
        )
        lines.append(
            "footprint={:.1f}x{:.1f}mm".format(
                metrics.footprint_width,
                metrics.footprint_depth,
            )
        )
        lines.append(f"max_height={metrics.max_height:.1f}mm")
        if metadata:
            meta_str = ",".join(f"{key}={value}" for key, value in sorted(metadata.items()))
            lines.append(f"metadata={meta_str}")
        if interleaves:
            lines.append(
                "interleaves="
                + ",".join(
                    f"{entry.level}@{entry.z_position:.1f}mm/{entry.interleaf.thickness:.1f}mm"
                    for entry in interleaves
                )
            )
        lines.append("")
        lines.append(
            "IDX;LAYER;BLOCK;X;Y;Z;ROT;APP_DIR;APP_DIST;LABEL_X;LABEL_Y;LABEL_Z"
        )
        for row in rows:
            lines.append(
                "{idx};{layer};{block};{x:.2f};{y:.2f};{z:.2f};{rot};{ad};{dist:.2f};{lx};{ly};{lz}".format(
                    idx=row.index,
                    layer=row.layer,
                    block=row.block,
                    x=row.x,
                    y=row.y,
                    z=row.z,
                    rot=row.rotation,
                    ad=row.approach_direction or "",
                    dist=row.approach_distance or 0.0,
                    lx=f"{row.label_x:.2f}" if row.label_x is not None else "",
                    ly=f"{row.label_y:.2f}" if row.label_y is not None else "",
                    lz=f"{row.label_z:.2f}" if row.label_z is not None else "",
                )
            )
        return "\n".join(lines)

    def _build_rows(self, layers: Iterable[LayerPlan]) -> list[PLCRow]:
        rows: list[PLCRow] = []
        counter = 1
        for layer_idx, layer in enumerate(layers, start=1):
            annotations = {
                annotation.placement_index: annotation for annotation in self.annotator.annotate(layer)
            }
            for placement in layer.placements:
                annotation = annotations.get(placement.sequence_index)
                rows.append(
                    PLCRow(
                        index=counter,
                        layer=layer_idx,
                        block=placement.block,
                        x=placement.position.x,
                        y=placement.position.y,
                        z=placement.position.z,
                        rotation=placement.rotation,
                        approach_direction=annotation.approach_direction if annotation else None,
                        approach_distance=annotation.approach_distance if annotation else None,
                        label_x=annotation.label_position.x if annotation else None,
                        label_y=annotation.label_position.y if annotation else None,
                        label_z=annotation.label_position.z if annotation else None,
                    )
                )
                counter += 1
        return rows


__all__ = ["PLCRow", "SiemensPLCExporter"]
