"""Layer sequence planner utilities."""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from .collisions import CollisionChecker
from .models import (
    ApproachConfig,
    Interleaf,
    InterleafPlacement,
    LayerPlan,
    LayerPlacement,
    LayerRequest,
    LayerSequencePlan,
    Vector3,
)
from .planner import RecursiveFiveBlockPlanner


class LayerSequencePlanner:
    """Generate multi-layer pallet plans by stacking layer results."""

    def __init__(self, layer_planner: RecursiveFiveBlockPlanner | None = None) -> None:
        self.layer_planner = layer_planner or RecursiveFiveBlockPlanner()

    def stack_layers(
        self,
        request: LayerRequest,
        *,
        levels: int,
        corners: Sequence[str] | None = None,
        z_step: float | None = None,
        collision_checker: CollisionChecker | None = None,
        approach_overrides: dict[str, ApproachConfig] | None = None,
        interleaf: Interleaf | None = None,
        interleaf_frequency: int = 1,
    ) -> LayerSequencePlan:
        if levels <= 0:
            raise ValueError("levels must be a positive integer")
        z_increment = z_step if z_step is not None else request.box.dimensions.height
        if z_increment <= 0:
            raise ValueError("z_step must be positive")
        if interleaf_frequency <= 0:
            raise ValueError("interleaf_frequency must be positive")
        ordered_corners = list(corners) if corners else [request.start_corner]
        if not ordered_corners:
            ordered_corners = [request.start_corner]

        layers: list[LayerPlan] = []
        interleaves: list[InterleafPlacement] = []
        current_z = 0.0
        for level in range(levels):
            corner = ordered_corners[level % len(ordered_corners)]
            level_request = replace(request, start_corner=corner)
            plan = self.layer_planner.plan_layer(level_request)
            elevated = [
                LayerPlacement(
                    box_id=placement.box_id,
                    position=Vector3(
                        x=placement.position.x,
                        y=placement.position.y,
                        z=placement.position.z + current_z,
                    ),
                    rotation=placement.rotation,
                    block=placement.block,
                    sequence_index=placement.sequence_index,
                )
                for placement in plan.placements
            ]
            level_plan = LayerPlan(
                placements=elevated,
                orientation=plan.orientation,
                fill_ratio=plan.fill_ratio,
                blocks=plan.blocks.copy(),
                start_corner=corner,
                metadata={**plan.metadata, "level": str(level + 1), "z_offset": f"{current_z:.3f}"},
                collisions=[],
                box=plan.box,
                approach_overrides=approach_overrides.copy() if approach_overrides else plan.approach_overrides.copy(),
            )
            if collision_checker is not None:
                issues = collision_checker.validate(level_plan, level_request)
                level_plan.collisions = [issue.description for issue in issues]
            layers.append(level_plan)
            current_z += z_increment
            if (
                interleaf is not None
                and (level + 1) < levels
                and ((level + 1) % interleaf_frequency == 0)
            ):
                interleaves.append(
                    InterleafPlacement(level=level + 1, z_position=current_z, interleaf=interleaf)
                )
                current_z += interleaf.thickness

        metadata = {
            "levels": str(levels),
            "z_step": f"{z_increment:.3f}",
            "corners": ",".join(ordered_corners),
            "reference_origin": request.reference_frame.origin,
            "reference_axes": request.reference_frame.axes_token,
        }
        if interleaf is not None:
            metadata.update(
                {
                    "interleaf_id": interleaf.id,
                    "interleaf_thickness": f"{interleaf.thickness:.3f}",
                    "interleaf_weight": f"{interleaf.weight:.3f}",
                    "interleaf_frequency": str(interleaf_frequency),
                }
            )
        return LayerSequencePlan(layers=layers, metadata=metadata, interleaves=interleaves)
