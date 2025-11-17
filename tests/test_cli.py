from argparse import Namespace

import kompongo.cli as cli


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
