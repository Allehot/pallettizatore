"""Helpers to model multi-grip (presa multipla) configurations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import Pallet, Vector3


@dataclass(frozen=True)
class GripperFinger:
    """Single finger (pinza) positioned in the multi-grip layout."""

    index: int
    row: int
    col: int
    center: Vector3
    width: float
    depth: float
    height: float

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "row": self.row,
            "col": self.col,
            "center": {"x": self.center.x, "y": self.center.y, "z": self.center.z},
            "width_mm": self.width,
            "depth_mm": self.depth,
            "height_mm": self.height,
        }


@dataclass(frozen=True)
class MultiGripDefinition:
    rows: int
    cols: int
    spacing_x: float
    spacing_y: float
    finger_width: float
    finger_depth: float
    finger_height: float
    boxes_per_finger: int = 1

    def validate(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("rows e cols devono essere positivi")
        if self.spacing_x < 0 or self.spacing_y < 0:
            raise ValueError("Lo spacing deve essere maggiore o uguale a zero")
        if self.finger_width <= 0 or self.finger_depth <= 0 or self.finger_height <= 0:
            raise ValueError("Dimensioni dita non valide")
        if self.boxes_per_finger <= 0:
            raise ValueError("boxes_per_finger deve essere positivo")

    def envelope(self) -> tuple[float, float]:
        width = self.finger_width + (self.cols - 1) * max(self.spacing_x, 0.0)
        depth = self.finger_depth + (self.rows - 1) * max(self.spacing_y, 0.0)
        return width, depth

    def total_boxes(self) -> int:
        return self.rows * self.cols * self.boxes_per_finger


@dataclass(frozen=True)
class MultiGripLayout:
    definition: MultiGripDefinition
    fingers: List[GripperFinger]

    def envelope(self) -> tuple[float, float]:
        return self.definition.envelope()

    def to_dict(self) -> dict[str, object]:
        return {
            "rows": self.definition.rows,
            "cols": self.definition.cols,
            "spacing_x_mm": self.definition.spacing_x,
            "spacing_y_mm": self.definition.spacing_y,
            "finger_width_mm": self.definition.finger_width,
            "finger_depth_mm": self.definition.finger_depth,
            "finger_height_mm": self.definition.finger_height,
            "boxes_per_finger": self.definition.boxes_per_finger,
            "total_boxes": self.definition.total_boxes(),
            "fingers": [finger.as_dict() for finger in self.fingers],
        }


def build_layout(definition: MultiGripDefinition, origin: Vector3 | None = None) -> MultiGripLayout:
    """Return the list of fingers centered around the provided origin."""

    definition.validate()
    origin = origin or Vector3(0.0, 0.0, 0.0)
    envelope_w, envelope_d = definition.envelope()
    start_x = origin.x - envelope_w / 2
    start_y = origin.y - envelope_d / 2
    fingers: List[GripperFinger] = []
    index = 1
    for row in range(definition.rows):
        for col in range(definition.cols):
            center_x = start_x + definition.finger_width / 2 + col * max(definition.spacing_x, 0.0)
            center_y = start_y + definition.finger_depth / 2 + row * max(definition.spacing_y, 0.0)
            finger = GripperFinger(
                index=index,
                row=row + 1,
                col=col + 1,
                center=Vector3(center_x, center_y, origin.z),
                width=definition.finger_width,
                depth=definition.finger_depth,
                height=definition.finger_height,
            )
            fingers.append(finger)
            index += 1
    return MultiGripLayout(definition=definition, fingers=fingers)


def evaluate_envelope(layout: MultiGripLayout, pallet: Pallet, overhang_x: float, overhang_y: float) -> list[str]:
    """Return warnings if the grip envelope violates pallet boundaries."""

    warnings: list[str] = []
    width, depth = layout.envelope()
    limit_x = pallet.dimensions.width + overhang_x * 2
    limit_y = pallet.dimensions.depth + overhang_y * 2
    if width > limit_x:
        warnings.append(
            "Ingombro pinza oltre il limite lungo X: {:.1f}mm > {:.1f}mm".format(width, limit_x)
        )
    if depth > limit_y:
        warnings.append(
            "Ingombro pinza oltre il limite lungo Y: {:.1f}mm > {:.1f}mm".format(depth, limit_y)
        )
    return warnings


def detect_finger_collisions(layout: MultiGripLayout) -> list[str]:
    """Return warnings whenever two finger footprints overlap."""

    warnings: list[str] = []
    for idx, current in enumerate(layout.fingers):
        c_bounds = _finger_bounds(current)
        for contender in layout.fingers[idx + 1 :]:
            if _rects_overlap(c_bounds, _finger_bounds(contender)):
                warnings.append(
                    f"Collisione dita tra F{current.index} e F{contender.index}"
                )
    return warnings


def evaluate_tool_clearance(
    layout: MultiGripLayout,
    tool_width: float | None,
    tool_depth: float | None,
) -> list[str]:
    """Warn if the layout envelope exceeds the usable tool window."""

    warnings: list[str] = []
    width, depth = layout.envelope()
    if tool_width is not None and width > tool_width:
        warnings.append(
            "Ingombro pinza oltre il limite tool lungo X: {:.1f}mm > {:.1f}mm".format(
                width, tool_width
            )
        )
    if tool_depth is not None and depth > tool_depth:
        warnings.append(
            "Ingombro pinza oltre il limite tool lungo Y: {:.1f}mm > {:.1f}mm".format(
                depth, tool_depth
            )
        )
    return warnings


def _finger_bounds(finger: GripperFinger) -> tuple[float, float, float, float]:
    half_w = finger.width / 2
    half_d = finger.depth / 2
    return (
        finger.center.x - half_w,
        finger.center.x + half_w,
        finger.center.y - half_d,
        finger.center.y + half_d,
    )


def _rects_overlap(
    a_bounds: tuple[float, float, float, float],
    b_bounds: tuple[float, float, float, float],
) -> bool:
    ax0, ax1, ay0, ay1 = a_bounds
    bx0, bx1, by0, by1 = b_bounds
    no_overlap = ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0
    return not no_overlap
