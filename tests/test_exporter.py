import json

from verpal import (
    Box,
    Dimensions,
    Interleaf,
    InterleafPlacement,
    LayerPlacement,
    LayerPlan,
    LayerSequencePlan,
    PlanExporter,
    Vector3,
)


def build_layer() -> LayerPlan:
    box = Box(
        id="BX",
        dimensions=Dimensions(width=200, depth=150, height=100),
        weight=5.0,
        label_position="front",
    )
    placements = [
        LayerPlacement(box_id="BX", position=Vector3(x=10, y=20, z=0), rotation=0, block="center", sequence_index=0)
    ]
    return LayerPlan(
        placements=placements,
        orientation=0,
        fill_ratio=0.9,
        blocks={"center": 1},
        start_corner="SW",
        metadata={"rows": "1", "columns": "1", "approach_direction": "SW", "approach_distance": "80"},
        box=box,
    )


def test_exporter_serializes_layer(tmp_path):
    exporter = PlanExporter(tmp_path)
    plan = build_layer()
    path = exporter.to_file(plan, "layer.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["type"] == "layer"
    assert payload["fill_ratio"] == plan.fill_ratio
    assert len(payload["placements"]) == 1
    placement = payload["placements"][0]
    assert placement["label"]["face"] == plan.box.label_position
    assert placement["approach"]["direction"] == "SW"
    assert placement["approach"]["distance"] == 80.0


def test_exporter_serializes_sequence(tmp_path):
    exporter = PlanExporter(tmp_path)
    layer = build_layer()
    interleaf = Interleaf(id="IL", thickness=3.0, weight=0.5, material="carton")
    sequence = LayerSequencePlan(
        [layer, layer],
        metadata={"levels": "2"},
        interleaves=[InterleafPlacement(level=1, z_position=50.0, interleaf=interleaf)],
    )
    path = exporter.to_file(sequence, "sequence.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["type"] == "sequence"
    assert payload["levels"] == 2
    assert payload["total_boxes"] == 2
    assert len(payload["layers"]) == 2
    assert payload["interleaves"][0]["id"] == "IL"
