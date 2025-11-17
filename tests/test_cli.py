from argparse import Namespace

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
    )
    cli.run_analyze(args)
    out = capsys.readouterr().out
    assert "Analisi sequenza" in out
    assert "strati" in out
