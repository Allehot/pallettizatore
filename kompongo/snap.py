"""Snap point helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import LayerPlan, LayerPlacement, Vector3


@dataclass
class SnapPoint:
    name: str
    position: Vector3


class SnapPointGenerator:
    def generate(self, plan: LayerPlan, box_width: float, box_depth: float) -> Dict[int, List[SnapPoint]]:
        snap_points: Dict[int, List[SnapPoint]] = {}
        for placement in plan.placements:
            snap_points[placement.sequence_index] = self._placement_points(placement, box_width, box_depth)
        return snap_points

    def _placement_points(self, placement: LayerPlacement, box_width: float, box_depth: float) -> List[SnapPoint]:
        x = placement.position.x
        y = placement.position.y
        z = placement.position.z
        half_w = box_width / 2
        half_d = box_depth / 2
        return [
            SnapPoint("center", Vector3(x, y, z)),
            SnapPoint("west", Vector3(x - half_w, y, z)),
            SnapPoint("east", Vector3(x + half_w, y, z)),
            SnapPoint("south", Vector3(x, y - half_d, z)),
            SnapPoint("north", Vector3(x, y + half_d, z)),
            SnapPoint("SW", Vector3(x - half_w, y - half_d, z)),
            SnapPoint("SE", Vector3(x + half_w, y - half_d, z)),
            SnapPoint("NW", Vector3(x - half_w, y + half_d, z)),
            SnapPoint("NE", Vector3(x + half_w, y + half_d, z)),
        ]
