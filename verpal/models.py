"""Domain models for VerPal."""
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


@dataclass(frozen=True)
class ReferenceFrame:
    """Reference frame definition for placement coordinates."""

    origin: str = "SW"
    x_axis: str = "E"
    y_axis: str = "N"

    _VALID_ORIGINS = {"SW", "SE", "NW", "NE", "CENTER"}

    def __post_init__(self) -> None:
        origin = self.origin.upper()
        if origin == "C":
            origin = "CENTER"
        if origin not in self._VALID_ORIGINS:
            raise ValueError(
                f"Invalid origin '{self.origin}'. Use SW, SE, NW, NE or CENTER"
            )
        x_axis = self.x_axis.upper()
        y_axis = self.y_axis.upper()
        if x_axis not in {"E", "W"}:
            raise ValueError("x_axis must be 'E' or 'W'")
        if y_axis not in {"N", "S"}:
            raise ValueError("y_axis must be 'N' or 'S'")
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)

    @property
    def axes_token(self) -> str:
        return f"{self.x_axis}{self.y_axis}"

    def transform(
        self,
        position: Vector3,
        *,
        pallet: Pallet,
        overhang_x: float,
        overhang_y: float,
    ) -> Vector3:
        """Transform a position into the configured reference frame."""

        base_x = position.x - overhang_x
        base_y = position.y - overhang_y
        origin = self._origin_point(pallet)
        dx = base_x - origin.x
        dy = base_y - origin.y
        x_sign = 1 if self.x_axis == "E" else -1
        y_sign = 1 if self.y_axis == "N" else -1
        return Vector3(x=dx * x_sign, y=dy * y_sign, z=position.z)

    def restore(
        self,
        position: Vector3,
        *,
        pallet: Pallet,
        overhang_x: float,
        overhang_y: float,
    ) -> Vector3:
        """Restore a transformed position back to the usable pallet frame."""

        origin = self._origin_point(pallet)
        x_sign = 1 if self.x_axis == "E" else -1
        y_sign = 1 if self.y_axis == "N" else -1
        base_x = origin.x + (position.x / x_sign)
        base_y = origin.y + (position.y / y_sign)
        return Vector3(x=base_x + overhang_x, y=base_y + overhang_y, z=position.z)

    def _origin_point(self, pallet: Pallet) -> Vector3:
        width = pallet.dimensions.width
        depth = pallet.dimensions.depth
        if self.origin == "SW":
            return Vector3(0.0, 0.0, 0.0)
        if self.origin == "SE":
            return Vector3(width, 0.0, 0.0)
        if self.origin == "NW":
            return Vector3(0.0, depth, 0.0)
        if self.origin == "NE":
            return Vector3(width, depth, 0.0)
        if self.origin == "CENTER":
            return Vector3(width / 2, depth / 2, 0.0)
        raise ValueError(f"Unsupported origin '{self.origin}'")


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
    reference_frame: ReferenceFrame = field(default_factory=ReferenceFrame)

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
