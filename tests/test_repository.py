from kompongo import DataRepository


def test_repository_initialization(tmp_path):
    repo = DataRepository(tmp_path / "kompongo.db")
    repo.initialize("data/seed_data.json")
    pallet = repo.get_pallet("EUR-EPAL")
    box = repo.get_box("BX-400")
    tool = repo.get_tool("TK-2")
    assert pallet.dimensions.width == 1200
    assert box.weight == 12.5
    assert tool.max_boxes == 2
    repo.close()


def test_repository_lists_entities(tmp_path):
    repo = DataRepository(tmp_path / "kompongo.db")
    repo.initialize("data/seed_data.json")
    pallets = repo.list_pallets()
    boxes = repo.list_boxes()
    tools = repo.list_tools()
    assert [p.id for p in pallets] == ["EUR-EPAL", "IND-1000"]
    assert sorted(box.id for box in boxes) == ["BX-250", "BX-400"]
    assert tools[-1].pickup_offset.z == 60
    repo.close()
