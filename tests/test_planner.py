from kompongo import (
    CollisionChecker,
    DataRepository,
    LayerRequest,
    RecursiveFiveBlockPlanner,
)


def test_planner_generates_layer(tmp_path):
    db_path = tmp_path / "kompongo.db"
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
