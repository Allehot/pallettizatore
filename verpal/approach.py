"""Approach helpers shared between CLI and GUI."""
from __future__ import annotations

import re
from typing import Dict, Sequence

from .models import ApproachConfig, LayerPlan


def parse_approach_overrides(raw: Sequence[str] | str | None) -> Dict[str, ApproachConfig]:
    """Parse block-level approach overrides from CLI or GUI inputs."""

    values: list[str]
    if raw is None:
        values = []
    elif isinstance(raw, str):
        tokens = re.split(r"[;,\s]+", raw.strip())
        values = [token for token in tokens if token]
    else:
        values = list(raw)
    overrides: Dict[str, ApproachConfig] = {}
    for value in values:
        try:
            block, payload = value.split("=", 1)
            direction, distance = payload.split(":", 1)
        except ValueError as exc:  # pragma: no cover - defensive parsing
            raise ValueError(
                f"Formato override non valido '{value}'. Usa blocco=DIREZIONE:DISTANZA"
            ) from exc
        overrides[block.strip().lower()] = ApproachConfig(
            direction=direction.strip().upper(),
            distance=float(distance),
        )
    return overrides


def apply_approach(
    plan: LayerPlan,
    direction: str,
    distance: float,
    overrides: Dict[str, ApproachConfig],
) -> None:
    """Persist approach metadata and overrides on a plan."""

    plan.metadata["approach_direction"] = direction
    plan.metadata["approach_distance"] = f"{distance:.2f}"
    plan.approach_overrides = overrides.copy()


__all__ = ["parse_approach_overrides", "apply_approach"]
