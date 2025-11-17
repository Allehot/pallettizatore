from verpal.metrics import compute_layer_metrics, compute_sequence_metrics
from verpal.models import Box, Dimensions, LayerPlan, LayerPlacement, LayerSequencePlan, Vector3


def _build_layer(z_offset: float = 0.0) -> LayerPlan:
    box = Box(
        id="BX",
        dimensions=Dimensions(width=200.0, depth=100.0, height=50.0),
        weight=5.0,
        label_position="front",
    )
    placements = [
        LayerPlacement(
            box_id="BX",
            position=Vector3(100.0, 50.0, 25.0 + z_offset),
            rotation=0,
            block="center",
            sequence_index=0,
        ),
        LayerPlacement(
            box_id="BX",
            position=Vector3(300.0, 50.0, 25.0 + z_offset),
            rotation=0,
            block="center",
            sequence_index=1,
        ),
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


def test_compute_layer_metrics():
    plan = _build_layer()
    metrics = compute_layer_metrics(plan)
    assert metrics.total_boxes == 2
    assert metrics.total_weight == 10.0
    assert metrics.center_of_mass.x == 200.0
    assert metrics.center_of_mass.y == 50.0
    assert metrics.center_of_mass.z == 25.0
    assert metrics.footprint_width == 400.0
    assert metrics.footprint_depth == 100.0
    assert metrics.max_height == 50.0


def test_compute_sequence_metrics():
    layer_a = _build_layer(0.0)
    layer_b = _build_layer(50.0)
    sequence = LayerSequencePlan(layers=[layer_a, layer_b])
    metrics = compute_sequence_metrics(sequence)
    assert metrics.layers == 2
    assert metrics.total_boxes == 4
    assert metrics.total_weight == 20.0
    assert metrics.center_of_mass.z == 50.0
    assert metrics.max_height == 100.0
