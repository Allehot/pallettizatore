from verpal import (
    ApproachConfig,
    Box,
    Dimensions,
    LayerPlan,
    LayerPlacement,
    PlacementAnnotator,
    Vector3,
)


def build_plan(label_face: str = "front") -> LayerPlan:
    box = Box(
        id="BX",
        dimensions=Dimensions(width=200, depth=150, height=120),
        weight=7.0,
        label_position=label_face,
    )
    placement = LayerPlacement(
        box_id=box.id,
        position=Vector3(x=100, y=50, z=0),
        rotation=0,
        block="center",
        sequence_index=0,
    )
    plan = LayerPlan(
        placements=[placement],
        orientation=0,
        fill_ratio=0.9,
        blocks={"center": 1},
        start_corner="SW",
        metadata={"approach_direction": "NE", "approach_distance": "60"},
        box=box,
    )
    return plan


def test_annotator_generates_label_and_vector():
    plan = build_plan()
    annotator = PlacementAnnotator(label_offset=0.0)
    annotations = annotator.annotate(plan)
    assert len(annotations) == 1
    annotation = annotations[0]
    assert annotation.approach_direction == "NE"
    assert annotation.approach_distance == 60.0
    assert annotation.label_position.y > plan.placements[0].position.y
    assert annotation.label_position.z == plan.box.dimensions.height / 2


def test_annotator_respects_overrides():
    plan = build_plan("side")
    plan.approach_overrides["center"] = ApproachConfig(direction="S", distance=35)
    annotator = PlacementAnnotator(label_offset=10.0)
    annotations = annotator.annotate(plan)
    annotation = annotations[0]
    assert annotation.approach_direction == "S"
    assert annotation.approach_distance == 35
    # Side label should primarily shift along X
    assert annotation.label_position.x > plan.placements[0].position.x
