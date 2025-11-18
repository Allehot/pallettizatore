"""Utilities to export plans over network protocols."""
from __future__ import annotations

import json
from pathlib import Path

from .annotations import PlacementAnnotator
from .models import LayerPlan, LayerSequencePlan


class PlanExporter:
    def __init__(
        self,
        base_path: str | Path = "artifacts",
        annotator: PlacementAnnotator | None = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.annotator = annotator or PlacementAnnotator()

    def to_file(self, plan: LayerPlan | LayerSequencePlan, filename: str) -> Path:
        path = self.base_path / filename
        path.write_text(self._serialize(plan), encoding="utf-8")
        return path

    def to_payload(self, plan: LayerPlan | LayerSequencePlan) -> bytes:
        return self._serialize(plan).encode("utf-8")

    def _serialize(self, plan: LayerPlan | LayerSequencePlan) -> str:
        if isinstance(plan, LayerSequencePlan):
            payload = {
                "type": "sequence",
                "metadata": plan.metadata,
                "levels": plan.levels(),
                "total_boxes": plan.total_boxes(),
                "layers": [self._layer_payload(layer, idx) for idx, layer in enumerate(plan.layers, start=1)],
            }
        else:
            payload = self._layer_payload(plan, 1)
            payload["type"] = "layer"
        return json.dumps(payload, indent=2)

    def _layer_payload(self, plan: LayerPlan, index: int) -> dict:
        return {
            "index": index,
            "orientation": plan.orientation,
            "fill_ratio": plan.fill_ratio,
            "blocks": plan.blocks,
            "start_corner": plan.start_corner,
            "metadata": plan.metadata,
            "collisions": plan.collisions,
            "placements": self._placement_payload(plan),
        }

    def _placement_payload(self, plan: LayerPlan) -> list[dict]:
        annotations = {annotation.placement_index: annotation for annotation in self.annotator.annotate(plan)}
        items: list[dict] = []
        for placement in plan.placements:
            payload = {
                "index": placement.sequence_index,
                "block": placement.block,
                "x": placement.position.x,
                "y": placement.position.y,
                "z": placement.position.z,
                "rotation": placement.rotation,
            }
            annotation = annotations.get(placement.sequence_index)
            if annotation:
                payload["label"] = {
                    "x": annotation.label_position.x,
                    "y": annotation.label_position.y,
                    "z": annotation.label_position.z,
                    "face": annotation.label_face,
                }
                payload["approach"] = {
                    "direction": annotation.approach_direction,
                    "distance": annotation.approach_distance,
                    "dx": annotation.approach_vector.x,
                    "dy": annotation.approach_vector.y,
                    "dz": annotation.approach_vector.z,
                }
            items.append(payload)
        return items
