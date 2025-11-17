"""Placement annotations for labels and approach vectors."""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from typing import Dict

from .models import Box, LayerPlan, LayerPlacement, Vector3
from .models import ensure_positive


@dataclass(frozen=True)
class PlacementAnnotation:
    """Information needed to visualize label and approach data."""

    placement_index: int
    label_position: Vector3
    label_face: str
    approach_direction: str
    approach_vector: Vector3
    approach_distance: float


class PlacementAnnotator:
    """Compute annotations for every placement in a layer."""

    def __init__(self, default_approach: float = 75.0, label_offset: float = 5.0) -> None:
        self.default_approach = ensure_positive(default_approach, name="default_approach")
        self.label_offset = label_offset

    def annotate(self, plan: LayerPlan) -> list[PlacementAnnotation]:
        if not plan.placements or plan.box is None:
            return []
        annotations: list[PlacementAnnotation] = []
        direction = plan.metadata.get("approach_direction", plan.start_corner)
        distance = float(plan.metadata.get("approach_distance", self.default_approach))
        for placement in plan.placements:
            override = (
                plan.approach_overrides.get(placement.block.lower())
                if plan.approach_overrides
                else None
            )
            annotation = self._annotate_single(
                placement,
                plan.box,
                direction=override.direction if override else direction,
                distance=override.distance if override else distance,
                label_face=plan.box.label_position,
            )
            annotations.append(annotation)
        return annotations

    def _annotate_single(
        self,
        placement: LayerPlacement,
        box: Box,
        *,
        direction: str,
        distance: float,
        label_face: str,
    ) -> PlacementAnnotation:
        ensure_positive(distance, name="approach_distance")
        sanitized_direction = direction.strip().upper() or "N"
        approach_vector = self._direction_to_vector(sanitized_direction, distance)
        label_position = self._label_world_position(placement, box, label_face)
        return PlacementAnnotation(
            placement_index=placement.sequence_index,
            label_position=label_position,
            label_face=label_face,
            approach_direction=sanitized_direction,
            approach_vector=approach_vector,
            approach_distance=distance,
        )

    def _direction_to_vector(self, direction: str, distance: float) -> Vector3:
        normalized = direction.strip().upper() or "N"
        dx, dy = _resolve_direction(normalized)
        return Vector3(x=dx * distance, y=dy * distance, z=0.0)

    def _label_world_position(self, placement: LayerPlacement, box: Box, face: str) -> Vector3:
        local = _face_vector(box, face, self.label_offset)
        rotated = _rotate_vector(local, placement.rotation)
        return Vector3(
            x=placement.position.x + rotated.x,
            y=placement.position.y + rotated.y,
            z=placement.position.z + rotated.z,
        )


def _resolve_direction(tag: str) -> tuple[float, float]:
    directions: Dict[str, tuple[float, float]] = {
        "N": (0.0, 1.0),
        "S": (0.0, -1.0),
        "E": (1.0, 0.0),
        "W": (-1.0, 0.0),
        "NE": (0.7071, 0.7071),
        "NW": (-0.7071, 0.7071),
        "SE": (0.7071, -0.7071),
        "SW": (-0.7071, -0.7071),
    }
    if tag not in directions:
        raise ValueError(f"Unsupported approach direction '{tag}'")
    return directions[tag]


def _face_vector(box: Box, face: str, label_offset: float) -> Vector3:
    half_width = box.dimensions.width / 2
    half_depth = box.dimensions.depth / 2
    half_height = box.dimensions.height / 2
    face_key = face.lower().strip()
    if face_key == "front":
        return Vector3(0.0, half_depth + label_offset, half_height)
    if face_key == "back":
        return Vector3(0.0, -(half_depth + label_offset), half_height)
    if face_key == "side" or face_key == "right":
        return Vector3(half_width + label_offset, 0.0, half_height)
    if face_key == "left":
        return Vector3(-(half_width + label_offset), 0.0, half_height)
    # Default to front face if unknown
    return Vector3(0.0, half_depth + label_offset, half_height)


def _rotate_vector(vector: Vector3, rotation_deg: int) -> Vector3:
    angle = radians(rotation_deg)
    cos_a = cos(angle)
    sin_a = sin(angle)
    x = vector.x * cos_a - vector.y * sin_a
    y = vector.x * sin_a + vector.y * cos_a
    return Vector3(x=x, y=y, z=vector.z)
