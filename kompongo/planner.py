"""Recursive five-block planner implementation."""
from __future__ import annotations

from math import floor
from typing import Dict, List, Tuple

from .models import LayerPlan, LayerPlacement, LayerRequest, Vector3


class RecursiveFiveBlockPlanner:
    """Build a layer by dividing the pallet into up to five rectangular blocks."""

    def __init__(self, tolerance: float = 1e-4):
        self.tolerance = tolerance

    def plan_layer(self, request: LayerRequest) -> LayerPlan:
        best_plan: LayerPlan | None = None
        for orientation in request.allowed_orientations():
            candidate = self._plan_orientation(request, orientation)
            if not candidate.placements:
                continue
            if best_plan is None or candidate.fill_ratio > best_plan.fill_ratio:
                best_plan = candidate
        if best_plan is None:
            raise ValueError("Unable to generate a layer with the provided inputs")
        return best_plan

    def _plan_orientation(self, request: LayerRequest, orientation: int) -> LayerPlan:
        box_dims = request.box.dimensions
        width = box_dims.width if orientation == 0 else box_dims.depth
        depth = box_dims.depth if orientation == 0 else box_dims.width

        usable_width = request.pallet.dimensions.width + request.overhang_x * 2
        usable_depth = request.pallet.dimensions.depth + request.overhang_y * 2

        columns = max(0, floor(usable_width / width))
        rows = max(0, floor(usable_depth / depth))
        if columns == 0 or rows == 0:
            return LayerPlan([], orientation, 0.0, {}, request.start_corner, {}, [], box=request.box)

        placements: List[LayerPlacement] = []
        total_boxes = columns * rows
        fill_ratio = (total_boxes * width * depth) / (usable_width * usable_depth)
        offsets = self._start_offsets(usable_width, usable_depth, width, depth, columns, rows)
        seq = 0
        block_counts: Dict[str, int] = {}
        for row in range(rows):
            for col in range(columns):
                block_name = self._block_name(row, col, rows, columns)
                block_counts[block_name] = block_counts.get(block_name, 0) + 1
                x = offsets[0] + col * width + width / 2
                y = offsets[1] + row * depth + depth / 2
                placements.append(
                    LayerPlacement(
                        box_id=request.box.id,
                        position=Vector3(x=x, y=y, z=request.pickup_offset.z),
                        rotation=orientation,
                        block=block_name,
                        sequence_index=seq,
                    )
                )
                seq += 1

        metadata = {
            "columns": str(columns),
            "rows": str(rows),
            "usable_width": f"{usable_width:.1f}",
            "usable_depth": f"{usable_depth:.1f}",
        }
        return LayerPlan(
            placements,
            orientation,
            fill_ratio,
            block_counts,
            request.start_corner,
            metadata,
            box=request.box,
        )

    def _block_name(self, row: int, col: int, rows: int, columns: int) -> str:
        is_left = col == 0
        is_right = col == columns - 1
        is_bottom = row == 0
        is_top = row == rows - 1

        if not (is_left or is_right or is_bottom or is_top):
            return "center"
        if is_left and not (is_top or is_bottom):
            return "west"
        if is_right and not (is_top or is_bottom):
            return "east"
        if is_bottom:
            return "south"
        return "north"

    def _start_offsets(
        self,
        usable_width: float,
        usable_depth: float,
        box_width: float,
        box_depth: float,
        columns: int,
        rows: int,
    ) -> Tuple[float, float]:
        total_width = columns * box_width
        total_depth = rows * box_depth
        offset_x = (usable_width - total_width) / 2
        offset_y = (usable_depth - total_depth) / 2
        return offset_x, offset_y
