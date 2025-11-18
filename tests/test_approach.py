import pytest

from verpal.approach import apply_approach, parse_approach_overrides
from verpal.models import ApproachConfig, LayerPlan


def _empty_plan() -> LayerPlan:
    return LayerPlan(
        placements=[],
        orientation=0,
        fill_ratio=0.0,
        blocks={},
        start_corner="SW",
        metadata={},
    )


def test_parse_overrides_accepts_string_payload():
    overrides = parse_approach_overrides("center=E:110,edge=NE:85")
    assert overrides["center"].direction == "E"
    assert pytest.approx(overrides["edge"].distance) == 85


def test_parse_overrides_rejects_invalid_payload():
    with pytest.raises(ValueError):
        parse_approach_overrides("invalid")


def test_apply_approach_updates_metadata_and_dict_copy():
    plan = _empty_plan()
    overrides = {"center": ApproachConfig(direction="E", distance=90.0)}
    apply_approach(plan, "NE", 75.0, overrides)
    assert plan.metadata["approach_direction"] == "NE"
    assert plan.metadata["approach_distance"].startswith("75")
    assert plan.approach_overrides is not overrides
    assert plan.approach_overrides["center"].distance == 90.0
