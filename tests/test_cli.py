from argparse import Namespace

from verpal import DataRepository
import verpal.cli as cli


def test_run_catalog_outputs_table(tmp_path, capsys):
    args = Namespace(
        entity="pallets",
        db=tmp_path / "catalog.db",
        seed="data/seed_data.json",
    )
    cli.run_catalog(args)
    out = capsys.readouterr().out
    assert "EUR-EPAL" in out
    assert "Dimensioni (mm)" in out


def test_run_catalog_boxes(tmp_path, capsys):
    args = Namespace(
        entity="boxes",
        db=tmp_path / "catalog.db",
        seed="data/seed_data.json",
    )
    cli.run_catalog(args)
    out = capsys.readouterr().out
    assert "BX-400" in out
    assert "12.50kg" in out


def test_box_override_helper(tmp_path):
    repo = DataRepository(tmp_path / "override.db")
    repo.initialize("data/seed_data.json")
    args = Namespace(
        box="BX-250",
        box_width=320.0,
        box_depth=215.0,
        box_height=210.0,
        box_weight=8.9,
        label_position="front",
    )
    custom = cli._resolve_box(repo, args)
    assert custom.dimensions.width == 320.0
    assert custom.weight == 8.9
    assert custom.label_position == "front"
    repo.close()


def test_reference_frame_from_args():
    frame = cli._reference_frame_from_args("center", "ws")
    assert frame.origin == "CENTER"
    assert frame.axes_token == "WS"


def test_reference_frame_invalid_axes():
    try:
        cli._reference_frame_from_args("SW", "E")
    except ValueError as exc:
        assert "Formato assi" in str(exc)
    else:  # pragma: no cover - safety net
        raise AssertionError("Expected ValueError")


def test_run_analyze_single_layer(tmp_path, capsys):
    args = Namespace(
        pallet="EUR-EPAL",
        box="BX-250",
        tool="TK-2",
        corner="SW",
        layers=1,
        corners=None,
        z_step=None,
        origin="SW",
        axes="EN",
        db=tmp_path / "analyze.db",
        seed="data/seed_data.json",
        interleaf=None,
        interleaf_frequency=1,
    )
    cli.run_analyze(args)
    out = capsys.readouterr().out
    assert "Analisi strato singolo" in out
    assert "Centro di massa" in out


def test_run_analyze_sequence(tmp_path, capsys):
    args = Namespace(
        pallet="EUR-EPAL",
        box="BX-250",
        tool="TK-2",
        corner="SW",
        layers=2,
        corners=["SW", "NE"],
        z_step=None,
        origin="SW",
        axes="EN",
        db=tmp_path / "analyze_multi.db",
        seed="data/seed_data.json",
        interleaf=None,
        interleaf_frequency=1,
    )
    cli.run_analyze(args)
    out = capsys.readouterr().out
    assert "Analisi sequenza" in out
    assert "strati" in out


def test_run_plc_generates_file(tmp_path):
    args = Namespace(
        pallet="EUR-EPAL",
        box="BX-250",
        tool="TK-2",
        corner="SW",
        layers=1,
        corners=None,
        z_step=None,
        origin="SW",
        axes="EN",
        db=tmp_path / "plc.db",
        seed="data/seed_data.json",
        approach_distance=70.0,
        approach_direction="NE",
        approach_override=None,
        label_offset=5.0,
        target=tmp_path / "packet.s7",
        interleaf=None,
        interleaf_frequency=1,
    )
    cli.run_plc(args)
    text = (tmp_path / "packet.s7").read_text(encoding="utf-8")
    assert "#VERPAL-S7" in text
    assert "IDX;LAYER" in text
