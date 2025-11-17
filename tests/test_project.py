from verpal import (
    Box,
    Dimensions,
    LayerPlacement,
    LayerPlan,
    LayerSequencePlan,
    Pallet,
    PickupOffset,
    PlanExporter,
    ProjectArchiver,
    Tool,
    Vector3,
)


def _sample_objects():
    pallet = Pallet("P1", Dimensions(1200, 800, 150), 20, 15)
    box = Box("B1", Dimensions(200, 150, 100), 5.0, "N")
    tool = Tool("T1", "TestTool", 2, (0, 90), pickup_offset=PickupOffset(10, 0, 0))
    return pallet, box, tool


def _sample_plan(box):
    placements = [
        LayerPlacement("B1", Vector3(0, 0, 0), 0, "center", 0),
        LayerPlacement("B1", Vector3(200, 0, 0), 0, "center", 1),
    ]
    return LayerPlan(
        placements=placements,
        orientation=0,
        fill_ratio=0.5,
        blocks={"center": 2},
        start_corner="SW",
        metadata={},
        box=box,
    )


def test_project_archiver_roundtrip(tmp_path):
    pallet, box, tool = _sample_objects()
    plan = _sample_plan(box)
    archiver = ProjectArchiver(PlanExporter(base_path=tmp_path))
    project = archiver.build(
        name="Demo",
        plan=plan,
        pallet=pallet,
        box=box,
        tool=tool,
        metadata={"cliente": "ACME"},
    )
    target = tmp_path / "demo.kpg"
    archiver.save(project, target)

    restored = archiver.load(target)
    assert restored.metadata["cliente"] == "ACME"
    payload = restored.plan_data()
    assert payload["type"] == "layer"
    assert payload["placements"][0]["x"] == 0
    assert restored.summary["total_boxes"] == 2


def test_project_archiver_sequence_summary(tmp_path):
    pallet, box, tool = _sample_objects()
    plan = _sample_plan(box)
    second = _sample_plan(box)
    for placement in second.placements:
        placement.position = Vector3(placement.position.x, placement.position.y, placement.position.z + 100)
    sequence = LayerSequencePlan(layers=[plan, second], metadata={"note": "stacked"})

    archiver = ProjectArchiver(PlanExporter(base_path=tmp_path))
    project = archiver.build(
        name="Stack",
        plan=sequence,
        pallet=pallet,
        box=box,
        tool=tool,
    )
    assert project.summary["layers"] == 2
    assert project.summary["total_boxes"] == 4
    assert project.summary["max_height_mm"] >= 100
    assert project.plan_type == "sequence"
