from verpal import (
    DataRepository,
    LayerRequest,
    LayerSequencePlanner,
    RecursiveFiveBlockPlanner,
    ReferenceFrame,
    Vector3,
)
from verpal.gui import (
    build_layer_view_model,
    build_metric_summary,
    compute_height_report,
    insert_manual_placement,
)


def _build_request(tmp_path):
    db_path = tmp_path / "verpal.db"
    repo = DataRepository(db_path)
    repo.initialize("data/seed_data.json")
    pallet = repo.get_pallet("EUR-EPAL")
    box = repo.get_box("BX-250")
    tool = repo.get_tool("TK-2")
    repo.close()
    return LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner="SW",
        reference_frame=ReferenceFrame(origin="NE", x_axis="W", y_axis="S"),
    )


def test_build_layer_view_model_restores_positions(tmp_path):
    request = _build_request(tmp_path)
    planner = RecursiveFiveBlockPlanner()
    plan = planner.plan_layer(request)
    view = build_layer_view_model(plan, request)
    assert view.pallet_width == request.pallet.dimensions.width
    assert view.pallet_depth == request.pallet.dimensions.depth
    assert len(view.placements) == len(plan.placements)
    for glyph in view.placements:
        assert -request.overhang_x <= glyph.center.x <= request.pallet.dimensions.width + request.overhang_x
        assert -request.overhang_y <= glyph.center.y <= request.pallet.dimensions.depth + request.overhang_y


def test_compute_height_report_handles_sequence(tmp_path):
    request = _build_request(tmp_path)
    planner = LayerSequencePlanner()
    sequence = planner.stack_layers(request, levels=3, corners=["SW", "NE"], z_step=None)
    rows = compute_height_report(request, sequence.layers[0], sequence)
    assert rows[0].label == "Layer 1"
    assert rows[1].label == "Layer 2"
    assert rows[-1].label == "Totale"
    expected_total = request.box.dimensions.height * 3
    assert abs(rows[-1].top - expected_total) < 1e-6


def test_metric_summary_includes_sequence_data(tmp_path):
    request = _build_request(tmp_path)
    sequence_planner = LayerSequencePlanner()
    sequence = sequence_planner.stack_layers(request, levels=2, corners=["SW"], z_step=None)
    lines = build_metric_summary(sequence.layers[0], sequence)
    labels = {line.label for line in lines}
    assert "Modalità" in labels
    assert "Strati" in labels
    assert "Peso totale" in labels
    total_line = next(line for line in lines if line.label == "Peso totale")
    assert total_line.value.endswith("kg")


def test_insert_manual_placement_adds_box(tmp_path):
    request = _build_request(tmp_path)
    planner = RecursiveFiveBlockPlanner()
    plan = planner.plan_layer(request)
    original_count = len(plan.placements)
    placement = insert_manual_placement(
        plan,
        request,
        center=Vector3(x=150.0, y=120.0, z=0.0),
        rotation=90,
        block="MANUALE",
    )
    assert len(plan.placements) == original_count + 1
    restored = request.reference_frame.restore(
        placement.position,
        pallet=request.pallet,
        overhang_x=request.overhang_x,
        overhang_y=request.overhang_y,
    )
    assert abs(restored.x - 150.0) < 1e-6
    assert abs(restored.y - 120.0) < 1e-6
    assert plan.blocks["MANUALE"] >= 1


def test_insert_manual_placement_updates_fill_ratio(tmp_path):
    request = _build_request(tmp_path)
    planner = RecursiveFiveBlockPlanner()
    plan = planner.plan_layer(request)
    initial_ratio = plan.fill_ratio
    insert_manual_placement(
        plan,
        request,
        center=Vector3(x=50.0, y=80.0, z=0.0),
        rotation=0,
        block="ADD", 
    )
    assert plan.fill_ratio >= initial_ratio
