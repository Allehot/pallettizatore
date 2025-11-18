"""Utilities to build measurement (quote) reports for pallet and boxes."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Box, Pallet, ReferenceFrame


@dataclass(frozen=True)
class QuoteMeasurement:
    """Single measurement entry expressed in millimeters."""

    label: str
    width_mm: float
    depth_mm: float
    height_mm: float
    angle_deg: float = 0.0

    def as_row(self) -> tuple[str, str, str, str]:
        return (
            self.label,
            f"{self.width_mm:.1f}",
            f"{self.depth_mm:.1f}",
            f"{self.height_mm:.1f}",
        )

    def as_dict(self) -> dict[str, float | str]:
        return {
            "label": self.label,
            "width_mm": self.width_mm,
            "depth_mm": self.depth_mm,
            "height_mm": self.height_mm,
            "angle_deg": self.angle_deg,
        }


@dataclass(frozen=True)
class QuoteReport:
    """Structured quote report for pallet and boxes."""

    pallet: QuoteMeasurement
    box: QuoteMeasurement
    origin: str
    axes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "axes": self.axes,
            "pallet": self.pallet.as_dict(),
            "box": self.box.as_dict(),
        }


def build_quote_report(pallet: Pallet, box: Box, frame: ReferenceFrame) -> QuoteReport:
    """Return quote data (in mm) with fixed annotation angle."""

    pallet_measure = QuoteMeasurement(
        label=f"Pallet {pallet.id}",
        width_mm=pallet.dimensions.width,
        depth_mm=pallet.dimensions.depth,
        height_mm=pallet.dimensions.height,
    )
    box_measure = QuoteMeasurement(
        label=f"Scatola {box.id}",
        width_mm=box.dimensions.width,
        depth_mm=box.dimensions.depth,
        height_mm=box.dimensions.height,
    )
    return QuoteReport(pallet=pallet_measure, box=box_measure, origin=frame.origin, axes=frame.axes_token)
