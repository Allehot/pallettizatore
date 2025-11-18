from verpal import (
    CollisionChecker,
    DataRepository,
    LayerRequest,
    LayerSequencePlanner,
    ReferenceFrame,
)


def test_sequence_planner_stacks_layers(tmp_path):
    db_path = tmp_path / "verpal.db"
    repo = DataRepository(db_path)
    repo.initialize("data/seed_data.json")
    pallet = repo.get_pallet("EUR-EPAL")
    box = repo.get_box("BX-250")
    tool = repo.get_tool("TK-2")
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner="SW",
        reference_frame=ReferenceFrame(origin="CENTER", x_axis="W", y_axis="N"),
    )

    planner = LayerSequencePlanner()
    sequence = planner.stack_layers(
        request,
        levels=3,
        corners=["SW", "NE"],
        collision_checker=CollisionChecker(),
    )

    assert sequence.levels() == 3
    assert sequence.metadata["corners"] == "SW,NE"
    assert sequence.metadata["reference_origin"] == "CENTER"
    assert sequence.metadata["reference_axes"] == "WN"
    assert sequence.total_boxes() == len(sequence.layers[0].placements) * 3
    assert sequence.layers[1].start_corner == "NE"
    assert sequence.layers[2].start_corner == "SW"
    assert sequence.layers[1].placements[0].position.z > sequence.layers[0].placements[0].position.z
    for layer in sequence.layers:
        assert not layer.collisions

    repo.close()


def test_sequence_planner_with_interleaf(tmp_path):
    db_path = tmp_path / "verpal.db"
    repo = DataRepository(db_path)
    repo.initialize("data/seed_data.json")
    pallet = repo.get_pallet("EUR-EPAL")
    box = repo.get_box("BX-250")
    tool = repo.get_tool("TK-2")
    interleaf = repo.get_interleaf("IL-CARTON")
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner="SW",
        reference_frame=ReferenceFrame(),
    )

    planner = LayerSequencePlanner()
    sequence = planner.stack_layers(
        request,
        levels=2,
        interleaf=interleaf,
        interleaf_frequency=1,
    )

    assert sequence.interleaves
    assert sequence.interleaves[0].level == 1
    assert sequence.interleaves[0].interleaf.id == "IL-CARTON"
    assert sequence.layers[1].placements[0].position.z > sequence.layers[0].placements[0].position.z
    repo.close()
