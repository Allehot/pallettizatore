"""Domain models for KomPonGo."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class Dimensions:
    width: float
    depth: float
    height: float


@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float = 0.0


@dataclass(frozen=True)
class PickupOffset:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass(frozen=True)
class Box:
    id: str
    dimensions: Dimensions
    weight: float
    label_position: str


@dataclass(frozen=True)
class Pallet:
    id: str
    dimensions: Dimensions
    max_overhang_x: float
    max_overhang_y: float


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    max_boxes: int
    allowed_orientations: Sequence[int]
    pickup_offset: PickupOffset = field(default_factory=PickupOffset)


class OrientationMode(str, Enum):
    WIDTH = "width"
    DEPTH = "depth"
    BOTH = "both"


@dataclass(frozen=True)
class ApproachConfig:
    direction: str
    distance: float


@dataclass
class LayerRequest:
    pallet: Pallet
    box: Box
    tool: Tool
    start_corner: str = "SW"
    orientation_mode: OrientationMode = OrientationMode.BOTH
    max_overhang_x: float | None = None
    max_overhang_y: float | None = None
    pickup_offset: PickupOffset = field(default_factory=PickupOffset)

    def allowed_orientations(self) -> Iterable[int]:
        """Return the orientations allowed for the calculation."""
        if self.orientation_mode == OrientationMode.WIDTH:
            return (0,)
        if self.orientation_mode == OrientationMode.DEPTH:
            return (90,)
        return (0, 90)

    @property
    def overhang_x(self) -> float:
        return self.max_overhang_x if self.max_overhang_x is not None else self.pallet.max_overhang_x

    @property
    def overhang_y(self) -> float:
        return self.max_overhang_y if self.max_overhang_y is not None else self.pallet.max_overhang_y


@dataclass
class LayerPlacement:
    box_id: str
    position: Vector3
    rotation: int
    block: str
    sequence_index: int


@dataclass
class LayerPlan:
    placements: List[LayerPlacement]
    orientation: int
    fill_ratio: float
    blocks: dict[str, int]
    start_corner: str
    metadata: dict[str, str]
    collisions: List[str] = field(default_factory=list)
    box: Box | None = None
    approach_overrides: Dict[str, ApproachConfig] = field(default_factory=dict)

    def ordered_placements(self) -> List[LayerPlacement]:
        """Return placements ordered according to the start corner preference."""
        order = self.start_corner.upper()
        x_reverse = "E" in order
        y_reverse = "N" in order
        return sorted(
            self.placements,
            key=lambda p: (
                -p.position.y if y_reverse else p.position.y,
                -p.position.x if x_reverse else p.position.x,
                p.sequence_index,
            ),
        )

    def describe_blocks(self) -> Sequence[str]:
        return [f"{name}: {count}" for name, count in sorted(self.blocks.items())]


@dataclass
class LayerSequencePlan:
    """Collection of multiple layers stacked on the same pallet."""

    layers: List[LayerPlan]
    metadata: dict[str, str] = field(default_factory=dict)

    def total_boxes(self) -> int:
        return sum(len(layer.placements) for layer in self.layers)

    def levels(self) -> int:
        return len(self.layers)

    def max_height(self) -> float:
        """Return the highest z position reached by the sequence."""
        highest = 0.0
        for layer in self.layers:
            if not layer.placements:
                continue
            layer_height = max(placement.position.z for placement in layer.placements)
            highest = max(highest, layer_height)
        return highest


def ensure_positive(value: float, *, name: str) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value
