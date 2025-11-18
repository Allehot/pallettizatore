from verpal.plc import SiemensPLCExporter
from verpal.models import Box, Dimensions, LayerPlacement, LayerPlan, Vector3


def _plan() -> LayerPlan:
    box = Box(
        id="BX",
        dimensions=Dimensions(width=200.0, depth=100.0, height=150.0),
        weight=5.0,
        label_position="front",
    )
    placements = [
        LayerPlacement(
            box_id="BX",
            position=Vector3(100.0, 80.0, 75.0),
            rotation=0,
            block="center",
            sequence_index=0,
        ),
        LayerPlacement(
            box_id="BX",
            position=Vector3(300.0, 80.0, 75.0),
            rotation=90,
            block="edge",
            sequence_index=1,
        ),
    ]
    return LayerPlan(
        placements=placements,
        orientation=0,
        fill_ratio=0.8,
        blocks={"center": 1, "edge": 1},
        start_corner="SW",
        metadata={"approach_direction": "NE", "approach_distance": "70"},
        box=box,
    )


def test_plc_exporter_serializes_layer(tmp_path):
    exporter = SiemensPLCExporter()
    plan = _plan()
    path = exporter.to_file(plan, tmp_path / "packet.s7")
    payload = path.read_text(encoding="utf-8")
    assert "#VERPAL-S7" in payload
    assert "layers=1" in payload
    assert payload.count("IDX;") == 1
    assert "center" in payload
    assert "edge" in payload
