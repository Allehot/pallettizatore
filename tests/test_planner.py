from verpal import (
    CollisionChecker,
    DataRepository,
    LayerRequest,
    RecursiveFiveBlockPlanner,
    ReferenceFrame,
)


def test_planner_generates_layer(tmp_path):
    db_path = tmp_path / "verpal.db"
    repo = DataRepository(db_path)
    repo.initialize("data/seed_data.json")
    pallet = repo.get_pallet("EUR-EPAL")
    box = repo.get_box("BX-250")
    tool = repo.get_tool("TK-2")
    request = LayerRequest(pallet=pallet, box=box, tool=tool, start_corner="SW")
    planner = RecursiveFiveBlockPlanner()
    plan = planner.plan_layer(request)
    assert len(plan.placements) > 0
    collisions = CollisionChecker().validate(plan, request)
    assert not collisions
    repo.close()


def test_reference_frame_transformation(tmp_path):
    db_path = tmp_path / "verpal.db"
    repo = DataRepository(db_path)
    repo.initialize("data/seed_data.json")
    pallet = repo.get_pallet("EUR-EPAL")
    box = repo.get_box("BX-250")
    tool = repo.get_tool("TK-2")
    planner = RecursiveFiveBlockPlanner()

    default_request = LayerRequest(pallet=pallet, box=box, tool=tool, start_corner="SW")
    default_plan = planner.plan_layer(default_request)

    custom_request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner="SW",
        reference_frame=ReferenceFrame(origin="NE", x_axis="W", y_axis="S"),
    )
    custom_plan = planner.plan_layer(custom_request)

    assert default_plan.metadata["reference_origin"] == "SW"
    assert custom_plan.metadata["reference_origin"] == "NE"
    assert custom_plan.metadata["reference_axes"] == "WS"
    assert default_plan.placements[0].position.x != custom_plan.placements[0].position.x
    assert default_plan.placements[0].position.y != custom_plan.placements[0].position.y
    repo.close()
