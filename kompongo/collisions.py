"""Collision detection and validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .models import LayerPlan, LayerPlacement, LayerRequest


@dataclass
class Collision:
    description: str


class CollisionChecker:
    def __init__(self, clearance: float = 1e-3):
        self.clearance = clearance

    def validate(self, plan: LayerPlan, request: LayerRequest) -> Sequence[Collision]:
        collisions: List[Collision] = []
        collisions.extend(self._check_pallet_bounds(plan, request))
        collisions.extend(self._check_overlap(plan, request))
        return collisions

    def _box_footprint(self, plan: LayerPlan, request: LayerRequest) -> tuple[float, float]:
        box_dims = request.box.dimensions
        if plan.orientation == 0:
            return box_dims.width, box_dims.depth
        return box_dims.depth, box_dims.width

    def _check_pallet_bounds(self, plan: LayerPlan, request: LayerRequest) -> Iterable[Collision]:
        limit_x = request.pallet.dimensions.width + request.overhang_x * 2
        limit_y = request.pallet.dimensions.depth + request.overhang_y * 2
        width, depth = self._box_footprint(plan, request)
        half_width = width / 2
        half_depth = depth / 2
        for placement in plan.placements:
            x_min = placement.position.x - half_width
            x_max = placement.position.x + half_width
            y_min = placement.position.y - half_depth
            y_max = placement.position.y + half_depth
            if x_min < -self.clearance or x_max > limit_x + self.clearance:
                yield Collision(f"Box {placement.sequence_index} exceeds pallet width limits")
            if y_min < -self.clearance or y_max > limit_y + self.clearance:
                yield Collision(f"Box {placement.sequence_index} exceeds pallet depth limits")

    def _check_overlap(self, plan: LayerPlan, request: LayerRequest) -> Iterable[Collision]:
        items = plan.placements
        width, depth = self._box_footprint(plan, request)
        for i, first in enumerate(items):
            for second in items[i + 1 :]:
                if self._overlap(first, second, width, depth):
                    yield Collision(f"Collision between {first.sequence_index} and {second.sequence_index}")

    def _overlap(self, a: LayerPlacement, b: LayerPlacement, width: float, depth: float) -> bool:
        return (
            abs(a.position.x - b.position.x) < width - self.clearance
            and abs(a.position.y - b.position.y) < depth - self.clearance
        )
