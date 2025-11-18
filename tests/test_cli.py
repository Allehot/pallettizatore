import json
from argparse import Namespace

from verpal import DataRepository
import verpal.cli as cli


def test_run_catalog_outputs_table(tmp_path, capsys):
    args = Namespace(
        entity="pallets",
        db=tmp_path / "catalog.db",
        seed="data/seed_data.json",
        format="table",
        filter=None,
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
        format="table",
        filter=None,
    )
    cli.run_catalog(args)
    out = capsys.readouterr().out
    assert "BX-400" in out
    assert "12.50kg" in out


def test_run_catalog_json(tmp_path, capsys):
    args = Namespace(
        entity="pallets",
        db=tmp_path / "catalog.db",
        seed="data/seed_data.json",
        format="json",
        filter=None,
    )
    cli.run_catalog(args)
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0]["id"] == "EUR-EPAL"
    assert payload[0]["width_mm"] > 1000


def test_run_catalog_json_boxes(tmp_path, capsys):
    args = Namespace(
        entity="boxes",
        db=tmp_path / "catalog.db",
        seed="data/seed_data.json",
        format="json",
        filter=None,
    )
    cli.run_catalog(args)
    payload = json.loads(capsys.readouterr().out)
    assert any(entry["label_position"] == "front" for entry in payload)


def test_run_catalog_filter_table(tmp_path, capsys):
    args = Namespace(
        entity="pallets",
        db=tmp_path / "catalog_filter.db",
        seed="data/seed_data.json",
        format="table",
        filter="ind",
    )
    cli.run_catalog(args)
    out = capsys.readouterr().out
    assert "IND-1000" in out
    assert "EUR-EPAL" not in out


def test_run_catalog_filter_json(tmp_path, capsys):
    args = Namespace(
        entity="tools",
        db=tmp_path / "catalog_filter_json.db",
        seed="data/seed_data.json",
        format="json",
        filter="tk-4",
    )
    cli.run_catalog(args)
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["id"] == "TK-4"


def test_run_catalog_stats_table(tmp_path, capsys):
    args = Namespace(
        entity="boxes",
        db=tmp_path / "catalog_stats.db",
        seed="data/seed_data.json",
        format="table",
        filter=None,
        stats=True,
    )
    cli.run_catalog(args)
    out = capsys.readouterr().out
    assert "Statistiche catalogo" in out
    assert "Totale elementi" in out


def test_run_catalog_stats_json(tmp_path, capsys):
    args = Namespace(
        entity="pallets",
        db=tmp_path / "catalog_stats_json.db",
        seed="data/seed_data.json",
        format="json",
        filter=None,
        stats=True,
    )
    cli.run_catalog(args)
    payload = json.loads(capsys.readouterr().out)
    assert "records" in payload
    assert "stats" in payload
    assert payload["stats"]["count"] >= 1


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


def test_run_render_creates_obj(tmp_path):
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
        db=tmp_path / "render.db",
        seed="data/seed_data.json",
        interleaf=None,
        interleaf_frequency=1,
        output=tmp_path / "layer.obj",
        skip_pallet=False,
        explode_gap=0.0,
        palette="classic",
        mtl=None,
        no_materials=True,
    )
    cli.run_render(args)
    text = (tmp_path / "layer.obj").read_text(encoding="utf-8")
    assert "# VERPAL OBJ" in text
    assert "v " in text
    assert "f " in text


def test_run_render_creates_materials(tmp_path):
    args = Namespace(
        pallet="EUR-EPAL",
        box="BX-250",
        tool="TK-2",
        corner="SW",
        layers=2,
        corners=None,
        z_step=None,
        origin="SW",
        axes="EN",
        db=tmp_path / "render_palette.db",
        seed="data/seed_data.json",
        interleaf=None,
        interleaf_frequency=1,
        output=tmp_path / "colored.obj",
        skip_pallet=False,
        explode_gap=15.0,
        palette="sunset",
        mtl=tmp_path / "colored.mtl",
        no_materials=False,
    )
    cli.run_render(args)
    obj_text = (tmp_path / "colored.obj").read_text(encoding="utf-8")
    mtl_text = (tmp_path / "colored.mtl").read_text(encoding="utf-8")
    assert "mtllib colored.mtl" in obj_text
    assert "usemtl layer_1" in obj_text
    assert "usemtl pallet" in obj_text
    assert "newmtl layer_1" in mtl_text
    assert "newmtl pallet" in mtl_text
