"""Metrics utilities for VerPal plans."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from .models import Box, Dimensions, LayerPlan, LayerPlacement, LayerSequencePlan, Vector3


@dataclass(frozen=True)
class LayerMetrics:
    """Aggregate statistics for a single layer."""

    total_boxes: int
    total_weight: float
    center_of_mass: Vector3
    footprint_width: float
    footprint_depth: float
    max_height: float


@dataclass(frozen=True)
class SequenceMetrics(LayerMetrics):
    """Aggregate statistics for a stack of layers."""

    layers: int


def compute_layer_metrics(plan: LayerPlan) -> LayerMetrics:
    """Compute aggregate metrics for a single layer plan."""

    entries: list[tuple[LayerPlacement, Box | None]] = [
        (placement, plan.box)
        for placement in plan.placements
    ]
    total_boxes, total_weight, center, width, depth, height = _accumulate(entries)
    return LayerMetrics(
        total_boxes=total_boxes,
        total_weight=total_weight,
        center_of_mass=center,
        footprint_width=width,
        footprint_depth=depth,
        max_height=height,
    )


def compute_sequence_metrics(sequence: LayerSequencePlan) -> SequenceMetrics:
    """Compute aggregate metrics for a stacked sequence of layers."""

    entries: list[tuple[LayerPlacement, Box | None]] = []
    box_count = 0
    for layer in sequence.layers:
        box_count += len(layer.placements)
        entries.extend((placement, layer.box) for placement in layer.placements)
    for entry in sequence.interleaves:
        pseudo_box = Box(
            id=f"interleaf-{entry.interleaf.id}",
            dimensions=Dimensions(width=0.0, depth=0.0, height=entry.interleaf.thickness),
            weight=entry.interleaf.weight,
            label_position="top",
        )
        pseudo_placement = LayerPlacement(
            box_id=pseudo_box.id,
            position=Vector3(
                x=0.0,
                y=0.0,
                z=entry.z_position + entry.interleaf.thickness / 2,
            ),
            rotation=0,
            block="interleaf",
            sequence_index=-entry.level,
        )
        entries.append((pseudo_placement, pseudo_box))
    total_boxes, total_weight, center, width, depth, height = _accumulate(entries)
    return SequenceMetrics(
        total_boxes=box_count,
        total_weight=total_weight,
        center_of_mass=center,
        footprint_width=width,
        footprint_depth=depth,
        max_height=height,
        layers=len(sequence.layers),
    )


def _accumulate(entries: Iterable[Tuple[LayerPlacement, Box | None]]):
    entries = list(entries)
    if not entries:
        return 0, 0.0, Vector3(0.0, 0.0, 0.0), 0.0, 0.0, 0.0

    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")
    min_bottom = float("inf")
    max_top = float("-inf")
    weighted_x = 0.0
    weighted_y = 0.0
    weighted_z = 0.0
    total_weight = 0.0
    fallback_count = len(entries)

    for placement, box in entries:
        width, depth, height, weight = _placement_factors(box, placement.rotation)
        half_w = width / 2
        half_d = depth / 2
        half_h = height / 2
        min_x = min(min_x, placement.position.x - half_w)
        max_x = max(max_x, placement.position.x + half_w)
        min_y = min(min_y, placement.position.y - half_d)
        max_y = max(max_y, placement.position.y + half_d)
        min_bottom = min(min_bottom, placement.position.z - half_h)
        max_top = max(max_top, placement.position.z + half_h)
        weighted_x += placement.position.x * weight
        weighted_y += placement.position.y * weight
        weighted_z += placement.position.z * weight
        total_weight += weight

    if total_weight <= 0:
        # Fall back to the arithmetic mean if weights are missing
        avg_x = sum(placement.position.x for placement, _ in entries) / fallback_count
        avg_y = sum(placement.position.y for placement, _ in entries) / fallback_count
        avg_z = sum(placement.position.z for placement, _ in entries) / fallback_count
    else:
        avg_x = weighted_x / total_weight
        avg_y = weighted_y / total_weight
        avg_z = weighted_z / total_weight

    center = Vector3(avg_x, avg_y, avg_z)
    footprint_width = max(0.0, max_x - min_x)
    footprint_depth = max(0.0, max_y - min_y)
    max_height = max(0.0, max_top - min_bottom)
    return len(entries), total_weight, center, footprint_width, footprint_depth, max_height


def _placement_factors(box: Box | None, rotation: int) -> tuple[float, float, float, float]:
    if box is None:
        return 0.0, 0.0, 0.0, 0.0
    dims = box.dimensions
    if rotation % 180 == 0:
        width = dims.width
        depth = dims.depth
    else:
        width = dims.depth
        depth = dims.width
    return width, depth, dims.height, box.weight
