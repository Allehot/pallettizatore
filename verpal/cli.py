"""Command line interface for VerPal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .approach import apply_approach, parse_approach_overrides

from .annotations import PlacementAnnotator
from .collisions import CollisionChecker
from .exporter import PlanExporter
from .metrics import compute_layer_metrics, compute_sequence_metrics
from .models import (
    Box,
    Dimensions,
    Interleaf,
    LayerPlan,
    LayerSequencePlan,
    LayerRequest,
    Pallet,
    ReferenceFrame,
)
from .plc import SiemensPLCExporter
from .planner import RecursiveFiveBlockPlanner
from .project import ProjectArchiver
from .render3d import export_sequence_to_obj, list_color_palettes
from .repository import DataRepository
from .sequence import LayerSequencePlanner
from .snap import SnapPointGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VerPal planner")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_parser = sub.add_parser("plan", help="Compute a pallet layer")
    plan_parser.add_argument("--pallet", required=True, help="Pallet id")
    plan_parser.add_argument("--box", required=True, help="Box id")
    plan_parser.add_argument("--tool", required=True, help="Tool id")
    plan_parser.add_argument("--corner", default="SW", help="Start corner")
    _add_reference_args(plan_parser)
    _add_pallet_override_args(plan_parser)
    _add_box_override_args(plan_parser)
    plan_parser.add_argument("--db", default="verpal.db", help="Database path")
    plan_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")
    plan_parser.add_argument("--export", help="Output filename")
    plan_parser.add_argument(
        "--approach-distance",
        type=float,
        default=75.0,
        help="Ampiezza (mm) del vettore di accostamento",
    )
    plan_parser.add_argument(
        "--approach-direction",
        help="Direzione di accostamento (N, S, E, W, NE, NW, SE, SW)",
    )
    plan_parser.add_argument(
        "--approach-override",
        action="append",
        help="Override blocchi nel formato blocco=DIREZIONE:DISTANZA",
    )
    plan_parser.add_argument(
        "--label-offset",
        type=float,
        default=5.0,
        help="Offset della posizione etichetta rispetto al lato della scatola",
    )

    stack_parser = sub.add_parser("stack", help="Compute a multi-layer pallet")
    stack_parser.add_argument("--pallet", required=True, help="Pallet id")
    stack_parser.add_argument("--box", required=True, help="Box id")
    stack_parser.add_argument("--tool", required=True, help="Tool id")
    stack_parser.add_argument("--corner", default="SW", help="Default start corner")
    _add_reference_args(stack_parser)
    _add_pallet_override_args(stack_parser)
    _add_box_override_args(stack_parser)
    stack_parser.add_argument("--corners", nargs="*", help="Sequence of corners per level")
    stack_parser.add_argument("--layers", type=int, default=2, help="Number of layers to stack")
    stack_parser.add_argument("--z-step", type=float, help="Custom Z increment between layers")
    _add_interleaf_args(stack_parser)
    stack_parser.add_argument("--db", default="verpal.db", help="Database path")
    stack_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")
    stack_parser.add_argument("--export", help="Output filename")
    stack_parser.add_argument(
        "--approach-distance",
        type=float,
        default=75.0,
        help="Ampiezza (mm) del vettore di accostamento",
    )
    stack_parser.add_argument(
        "--approach-direction",
        help="Direzione di accostamento (N, S, E, W, NE, NW, SE, SW)",
    )
    stack_parser.add_argument(
        "--approach-override",
        action="append",
        help="Override blocchi nel formato blocco=DIREZIONE:DISTANZA",
    )
    stack_parser.add_argument(
        "--label-offset",
        type=float,
        default=5.0,
        help="Offset della posizione etichetta rispetto al lato della scatola",
    )

    archive_parser = sub.add_parser("archive", help="Crea un archivio completo del progetto")
    archive_parser.add_argument("--name", default="VerPal Project", help="Nome progetto")
    archive_parser.add_argument("--pallet", required=True, help="Pallet id")
    archive_parser.add_argument("--box", required=True, help="Box id")
    archive_parser.add_argument("--tool", required=True, help="Tool id")
    archive_parser.add_argument("--corner", default="SW", help="Corner iniziale")
    _add_reference_args(archive_parser)
    _add_pallet_override_args(archive_parser)
    _add_box_override_args(archive_parser)
    archive_parser.add_argument("--corners", nargs="*", help="Corner per ogni livello (multi layer)")
    archive_parser.add_argument("--layers", type=int, default=1, help="Numero di strati")
    archive_parser.add_argument("--z-step", type=float, help="Incremento Z personalizzato tra gli strati")
    _add_interleaf_args(archive_parser)
    archive_parser.add_argument("--db", default="verpal.db", help="Database path")
    archive_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")
    archive_parser.add_argument("--archive", required=True, help="File di output (.zip)")
    archive_parser.add_argument(
        "--approach-distance",
        type=float,
        default=75.0,
        help="Ampiezza (mm) del vettore di accostamento",
    )
    archive_parser.add_argument(
        "--approach-direction",
        help="Direzione di accostamento (N, S, E, W, NE, NW, SE, SW)",
    )
    archive_parser.add_argument(
        "--approach-override",
        action="append",
        help="Override blocchi nel formato blocco=DIREZIONE:DISTANZA",
    )
    archive_parser.add_argument(
        "--label-offset",
        type=float,
        default=5.0,
        help="Offset della posizione etichetta rispetto al lato della scatola",
    )
    archive_parser.add_argument(
        "--note",
        action="append",
        default=[],
        help="Nota aggiuntiva per l'archivio (chiave=valore)",
    )

    catalog_parser = sub.add_parser("catalog", help="Elenca i dati disponibili nel database")
    catalog_parser.add_argument(
        "entity",
        choices=["pallets", "boxes", "tools", "interleaves"],
        help="Tipo di dati da mostrare",
    )
    catalog_parser.add_argument("--db", default="verpal.db", help="Percorso database")
    catalog_parser.add_argument(
        "--seed",
        default="data/seed_data.json",
        help="Seed data path (crea il db se necessario)",
    )
    catalog_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Formato di output (tabella leggibile o JSON)",
    )
    catalog_parser.add_argument(
        "--filter",
        help="Filtra i risultati per ID/nome (match case-insensitive)",
    )
    catalog_parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostra anche un riepilogo numerico dei dati",
    )

    render_parser = sub.add_parser(
        "render",
        help="Esporta un modello 3D (Wavefront OBJ/MTL) dello strato o sequenza",
    )
    render_parser.add_argument("--pallet", required=True, help="Pallet id")
    render_parser.add_argument("--box", required=True, help="Box id")
    render_parser.add_argument("--tool", required=True, help="Tool id")
    render_parser.add_argument("--corner", default="SW", help="Corner iniziale")
    render_parser.add_argument("--layers", type=int, default=1, help="Numero di strati")
    render_parser.add_argument("--corners", nargs="*", help="Corner per ogni livello")
    render_parser.add_argument("--z-step", type=float, help="Incremento Z personalizzato")
    render_parser.add_argument(
        "--explode-gap",
        type=float,
        default=0.0,
        help="Distacco verticale extra tra gli strati esportati (mm)",
    )
    render_parser.add_argument(
        "--skip-pallet",
        action="store_true",
        help="Non includere il solido del pallet nel modello",
    )
    render_parser.add_argument("--output", required=True, help="Percorso file OBJ")
    render_parser.add_argument(
        "--mtl",
        help="Percorso file MTL (default accanto al file OBJ)",
    )
    render_parser.add_argument(
        "--palette",
        choices=list_color_palettes(),
        default="classic",
        help="Palette colori da utilizzare per i layer",
    )
    render_parser.add_argument(
        "--no-materials",
        action="store_true",
        help="Disabilita la generazione del file MTL e delle info colore",
    )
    _add_reference_args(render_parser)
    _add_pallet_override_args(render_parser)
    _add_box_override_args(render_parser)
    _add_interleaf_args(render_parser)
    render_parser.add_argument("--db", default="verpal.db", help="Percorso database")
    render_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")

    gui_parser = sub.add_parser(
        "gui",
        help="Avvia l'interfaccia grafica con drag&drop e vista 3D",
    )
    gui_parser.add_argument(
        "--pallet",
        help="Pallet id (opzionale: in assenza verrà usato il primo disponibile)",
    )
    gui_parser.add_argument(
        "--box",
        help="Box id (opzionale: in assenza verrà usato il primo disponibile)",
    )
    gui_parser.add_argument(
        "--tool",
        help="Tool id (opzionale: in assenza verrà usato il primo disponibile)",
    )
    gui_parser.add_argument("--corner", default="SW", help="Corner di partenza")
    gui_parser.add_argument("--layers", type=int, default=1, help="Numero di strati da visualizzare")
    gui_parser.add_argument("--corners", nargs="*", help="Sequenza dei corner per ogni livello")
    gui_parser.add_argument("--z-step", type=float, help="Incremento Z personalizzato")
    _add_reference_args(gui_parser)
    _add_pallet_override_args(gui_parser)
    _add_box_override_args(gui_parser)
    _add_interleaf_args(gui_parser)
    gui_parser.add_argument(
        "--approach-distance",
        type=float,
        default=75.0,
        help="Ampiezza (mm) del vettore di accostamento predefinito",
    )
    gui_parser.add_argument(
        "--approach-direction",
        help="Direzione di accostamento fissa (lascia vuoto per seguire il corner)",
    )
    gui_parser.add_argument(
        "--approach-override",
        action="append",
        help="Override blocchi nel formato blocco=DIREZIONE:DISTANZA",
    )
    gui_parser.add_argument(
        "--label-offset",
        type=float,
        default=5.0,
        help="Offset etichetta rispetto al lato della scatola",
    )
    gui_parser.add_argument("--db", default="verpal.db", help="Percorso database")
    gui_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")

    analyze_parser = sub.add_parser(
        "analyze",
        help="Calcola le metriche complessive di uno o più strati",
    )
    analyze_parser.add_argument("--pallet", required=True, help="Pallet id")
    analyze_parser.add_argument("--box", required=True, help="Box id")
    analyze_parser.add_argument("--tool", required=True, help="Tool id")
    analyze_parser.add_argument("--corner", default="SW", help="Corner iniziale")
    analyze_parser.add_argument("--layers", type=int, default=1, help="Numero di strati")
    analyze_parser.add_argument("--corners", nargs="*", help="Corner per ogni livello")
    analyze_parser.add_argument("--z-step", type=float, help="Incremento Z personalizzato")
    _add_reference_args(analyze_parser)
    _add_pallet_override_args(analyze_parser)
    _add_box_override_args(analyze_parser)
    _add_interleaf_args(analyze_parser)
    analyze_parser.add_argument("--db", default="verpal.db", help="Percorso database")
    analyze_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")

    plc_parser = sub.add_parser(
        "plc",
        help="Genera un file compatibile con PLC Siemens con le posizioni di deposito",
    )
    plc_parser.add_argument("--pallet", required=True, help="Pallet id")
    plc_parser.add_argument("--box", required=True, help="Box id")
    plc_parser.add_argument("--tool", required=True, help="Tool id")
    plc_parser.add_argument("--corner", default="SW", help="Corner iniziale")
    plc_parser.add_argument("--layers", type=int, default=1, help="Numero di strati")
    plc_parser.add_argument("--corners", nargs="*", help="Corner per ogni livello")
    plc_parser.add_argument("--z-step", type=float, help="Incremento Z personalizzato")
    _add_reference_args(plc_parser)
    _add_pallet_override_args(plc_parser)
    _add_box_override_args(plc_parser)
    _add_interleaf_args(plc_parser)
    plc_parser.add_argument("--target", required=True, help="File di destinazione (es. packet.s7)")
    plc_parser.add_argument("--db", default="verpal.db", help="Percorso database")
    plc_parser.add_argument("--seed", default="data/seed_data.json", help="Seed data path")
    plc_parser.add_argument(
        "--approach-distance",
        type=float,
        default=75.0,
        help="Ampiezza (mm) del vettore di accostamento",
    )
    plc_parser.add_argument(
        "--approach-direction",
        help="Direzione di accostamento (N, S, E, W, NE, NW, SE, SW)",
    )
    plc_parser.add_argument(
        "--approach-override",
        action="append",
        help="Override blocchi nel formato blocco=DIREZIONE:DISTANZA",
    )
    plc_parser.add_argument(
        "--label-offset",
        type=float,
        default=5.0,
        help="Offset della posizione etichetta rispetto al lato della scatola",
    )
    return parser


def _add_reference_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--origin",
        default="SW",
        help="Origine del sistema di riferimento (SW, SE, NW, NE, CENTER)",
    )
    parser.add_argument(
        "--axes",
        default="EN",
        help="Orientamento assi (X: E/W, Y: N/S es. EN, ES, WN, WS)",
    )


def _add_pallet_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pallet-width", type=float, help="Larghezza pallet personalizzata (mm)")
    parser.add_argument("--pallet-depth", type=float, help="Profondità pallet personalizzata (mm)")
    parser.add_argument("--pallet-height", type=float, help="Altezza pallet personalizzata (mm)")
    parser.add_argument("--overhang-x", type=float, help="Sbordo massimo lungo X (mm)")
    parser.add_argument("--overhang-y", type=float, help="Sbordo massimo lungo Y (mm)")


def _add_box_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--box-width", type=float, help="Larghezza scatola personalizzata (mm)")
    parser.add_argument("--box-depth", type=float, help="Profondità scatola personalizzata (mm)")
    parser.add_argument("--box-height", type=float, help="Altezza scatola personalizzata (mm)")
    parser.add_argument("--box-weight", type=float, help="Peso scatola personalizzato (kg)")
    parser.add_argument("--label-position", help="Faccia etichetta personalizzata (front/side/etc)")


def _add_interleaf_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--interleaf", help="ID dell'interfalda da inserire tra gli strati")
    parser.add_argument(
        "--interleaf-frequency",
        type=int,
        default=1,
        help="Inserisci l'interfalda ogni N strati (default 1)",
    )


def _resolve_pallet(repo: DataRepository, args: argparse.Namespace) -> Pallet:
    pallet = repo.get_pallet(args.pallet)
    width = _positive_value(getattr(args, "pallet_width", None), pallet.dimensions.width, "pallet_width")
    depth = _positive_value(getattr(args, "pallet_depth", None), pallet.dimensions.depth, "pallet_depth")
    height = _positive_value(getattr(args, "pallet_height", None), pallet.dimensions.height, "pallet_height")
    overhang_x = _non_negative_value(getattr(args, "overhang_x", None), pallet.max_overhang_x, "overhang_x")
    overhang_y = _non_negative_value(getattr(args, "overhang_y", None), pallet.max_overhang_y, "overhang_y")
    return Pallet(
        id=pallet.id,
        dimensions=Dimensions(width=width, depth=depth, height=height),
        max_overhang_x=overhang_x,
        max_overhang_y=overhang_y,
    )


def _resolve_box(repo: DataRepository, args: argparse.Namespace) -> Box:
    box = repo.get_box(args.box)
    width = _positive_value(getattr(args, "box_width", None), box.dimensions.width, "box_width")
    depth = _positive_value(getattr(args, "box_depth", None), box.dimensions.depth, "box_depth")
    height = _positive_value(getattr(args, "box_height", None), box.dimensions.height, "box_height")
    weight = _positive_value(getattr(args, "box_weight", None), box.weight, "box_weight")
    label = getattr(args, "label_position", None) or box.label_position
    return Box(
        id=box.id,
        dimensions=Dimensions(width=width, depth=depth, height=height),
        weight=weight,
        label_position=label,
    )


def _resolve_interleaf(repo: DataRepository, args: argparse.Namespace) -> Interleaf | None:
    interleaf_id = getattr(args, "interleaf", None)
    if not interleaf_id:
        return None
    return repo.get_interleaf(interleaf_id)


def _positive_value(value: float | None, fallback: float, name: str) -> float:
    if value is None:
        return fallback
    if value <= 0:
        raise ValueError(f"{name} deve essere maggiore di zero")
    return value


def _non_negative_value(value: float | None, fallback: float, name: str) -> float:
    if value is None:
        return fallback
    if value < 0:
        raise ValueError(f"{name} deve essere maggiore o uguale a zero")
    return value


def _reference_frame_from_args(origin: str, axes: str) -> ReferenceFrame:
    axes_token = (axes or "EN").strip().upper()
    if len(axes_token) != 2:
        raise ValueError("Formato assi non valido. Usa due lettere (E/W + N/S)")
    return ReferenceFrame(origin=origin.strip(), x_axis=axes_token[0], y_axis=axes_token[1])


def _calculate_layer(request: LayerRequest) -> LayerPlan:
    planner = RecursiveFiveBlockPlanner()
    plan = planner.plan_layer(request)
    collisions = CollisionChecker().validate(plan, request)
    plan.collisions = [c.description for c in collisions]
    return plan


def _build_notes(values: list[str]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            notes[f"note_{len(notes)+1}"] = raw
            continue
        key, value = raw.split("=", 1)
        notes[key.strip()] = value.strip()
    return notes


def _print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    format_str = "  ".join(f"{{:<{width}}}" for width in widths)
    print(format_str.format(*headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(format_str.format(*row))


def run_catalog(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    records: list[dict]
    rows: list[tuple[str, ...]]
    show_stats = bool(getattr(args, "stats", False))
    if args.entity == "pallets":
        pallets = repo.list_pallets()
        records = [
            {
                "id": pallet.id,
                "width_mm": pallet.dimensions.width,
                "depth_mm": pallet.dimensions.depth,
                "height_mm": pallet.dimensions.height,
                "max_overhang_x_mm": pallet.max_overhang_x,
                "max_overhang_y_mm": pallet.max_overhang_y,
            }
            for pallet in pallets
        ]
        records = _apply_catalog_filter(records, args.filter, ("id",))
        rows = [
            (
                record["id"],
                f"{record['width_mm']:.0f}x{record['depth_mm']:.0f}x{record['height_mm']:.0f}",
                f"±X {record['max_overhang_x_mm']:.0f} | ±Y {record['max_overhang_y_mm']:.0f}",
            )
            for record in records
        ]
        headers = ("ID", "Dimensioni (mm)", "Sbordo max (mm)")
    elif args.entity == "boxes":
        boxes = repo.list_boxes()
        records = [
            {
                "id": box.id,
                "width_mm": box.dimensions.width,
                "depth_mm": box.dimensions.depth,
                "height_mm": box.dimensions.height,
                "weight_kg": box.weight,
                "label_position": box.label_position,
            }
            for box in boxes
        ]
        records = _apply_catalog_filter(records, args.filter, ("id", "label_position"))
        rows = [
            (
                record["id"],
                f"{record['width_mm']:.0f}x{record['depth_mm']:.0f}x{record['height_mm']:.0f}",
                f"{record['weight_kg']:.2f}kg",
                record["label_position"] or "-",
            )
            for record in records
        ]
        headers = ("ID", "Dimensioni (mm)", "Peso", "Etichetta")
    elif args.entity == "tools":
        tools = repo.list_tools()
        records = [
            {
                "id": tool.id,
                "name": tool.name,
                "max_boxes": tool.max_boxes,
                "allowed_orientations": list(tool.allowed_orientations),
                "pickup_offset_mm": {
                    "x": tool.pickup_offset.x,
                    "y": tool.pickup_offset.y,
                    "z": tool.pickup_offset.z,
                },
            }
            for tool in tools
        ]
        records = _apply_catalog_filter(records, args.filter, ("id", "name", "allowed_orientations"))
        rows = [
            (
                record["id"],
                record["name"],
                str(record["max_boxes"]),
                ",".join(str(value) for value in record["allowed_orientations"]) or "-",
                "({x:.0f},{y:.0f},{z:.0f})".format(**record["pickup_offset_mm"]),
            )
            for record in records
        ]
        headers = ("ID", "Nome", "# Scatole", "Orientazioni", "Offset (mm)")
    else:
        interleaves = repo.list_interleaves()
        records = [
            {
                "id": interleaf.id,
                "thickness_mm": interleaf.thickness,
                "weight_kg": interleaf.weight,
                "material": interleaf.material,
            }
            for interleaf in interleaves
        ]
        records = _apply_catalog_filter(records, args.filter, ("id", "material"))
        rows = [
            (
                record["id"],
                f"{record['thickness_mm']:.1f}mm",
                f"{record['weight_kg']:.2f}kg",
                record["material"],
            )
            for record in records
        ]
        headers = ("ID", "Spessore", "Peso", "Materiale")

    summary = _catalog_summary(args.entity, records) if show_stats else None

    if args.format == "json":
        payload: dict | list
        if summary is None:
            payload = records
        else:
            payload = {"records": records, "stats": summary}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if rows:
            _print_table(headers, rows)
        else:
            print("Nessun dato disponibile")
        if summary:
            print("\nStatistiche catalogo:")
            for key, value in summary.items():
                if key == "count":
                    label = "Totale elementi"
                else:
                    label = key.replace("_", " ").capitalize()
                print(f"  - {label}: {_format_stat_value(value)}")
    repo.close()


def _catalog_summary(entity: str, records: list[dict]) -> dict[str, float | int]:
    summary: dict[str, float | int] = {"count": len(records)}
    if not records:
        return summary
    if entity == "pallets":
        summary.update(
            {
                "avg_width_mm": _mean(record["width_mm"] for record in records),
                "avg_depth_mm": _mean(record["depth_mm"] for record in records),
                "avg_overhang_x_mm": _mean(record["max_overhang_x_mm"] for record in records),
            }
        )
    elif entity == "boxes":
        summary.update(
            {
                "avg_weight_kg": _mean(record["weight_kg"] for record in records),
                "avg_height_mm": _mean(record["height_mm"] for record in records),
            }
        )
    elif entity == "tools":
        unique_orientations = {
            str(orientation)
            for record in records
            for orientation in record.get("allowed_orientations", [])
        }
        summary.update(
            {
                "avg_capacity": _mean(record["max_boxes"] for record in records),
                "unique_orientations": len(unique_orientations),
            }
        )
    else:
        summary.update(
            {
                "avg_thickness_mm": _mean(record["thickness_mm"] for record in records),
                "avg_weight_kg": _mean(record["weight_kg"] for record in records),
            }
        )
    return summary


def _mean(values: Iterable[float]) -> float:
    data = list(values)
    if not data:
        return 0.0
    return sum(data) / len(data)


def _format_stat_value(value: float | int) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _apply_catalog_filter(
    records: list[dict],
    needle: str | None,
    fields: tuple[str, ...],
) -> list[dict]:
    if not needle:
        return records
    lowered = needle.strip().lower()
    if not lowered:
        return records
    filtered: list[dict] = []
    for record in records:
        if _record_matches(record, lowered, fields):
            filtered.append(record)
    return filtered


def _record_matches(record: dict, needle: str, fields: tuple[str, ...]) -> bool:
    for field in fields:
        value = record.get(field)
        if value is None:
            continue
        values: list[str]
        if isinstance(value, (list, tuple, set)):
            values = [str(entry).lower() for entry in value]
        else:
            values = [str(value).lower()]
        for text in values:
            if needle in text:
                return True
    return False


def run_plc(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    try:
        pallet = _resolve_pallet(repo, args)
        box = _resolve_box(repo, args)
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    tool = repo.get_tool(args.tool)
    try:
        interleaf = _resolve_interleaf(repo, args)
    except KeyError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        repo.close()
        raise SystemExit(str(exc)) from exc

    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner=args.corner,
        reference_frame=reference_frame,
    )

    try:
        overrides = parse_approach_overrides(args.approach_override)
    except ValueError as exc:  # pragma: no cover - defensive user input
        repo.close()
        raise SystemExit(str(exc)) from exc

    annotator = PlacementAnnotator(
        default_approach=args.approach_distance,
        label_offset=args.label_offset,
    )

    plan: LayerPlan | LayerSequencePlan
    if args.layers > 1:
        sequence_planner = LayerSequencePlanner()
        collision_checker = CollisionChecker()
        plan = sequence_planner.stack_layers(
            request,
            levels=args.layers,
            corners=args.corners,
            z_step=args.z_step,
            collision_checker=collision_checker,
            approach_overrides=overrides,
            interleaf=interleaf,
            interleaf_frequency=args.interleaf_frequency,
        )
        for layer in plan.layers:
            layer_direction = (args.approach_direction or layer.start_corner).upper()
            apply_approach(layer, layer_direction, args.approach_distance, overrides)
    else:
        plan = _calculate_layer(request)
        direction = (args.approach_direction or args.corner).upper()
        apply_approach(plan, direction, args.approach_distance, overrides)

    exporter = SiemensPLCExporter(annotator=annotator)
    path = exporter.to_file(plan, args.target)
    print(f"File PLC salvato in {path}")
    if isinstance(plan, LayerSequencePlan) and plan.interleaves:
        print(f"Include {len(plan.interleaves)} interfalde nel profilo Z")
    repo.close()


def run_plan(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    try:
        pallet = _resolve_pallet(repo, args)
        box = _resolve_box(repo, args)
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    tool = repo.get_tool(args.tool)
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner=args.corner,
        reference_frame=reference_frame,
    )

    plan = _calculate_layer(request)
    collisions = plan.collisions

    try:
        overrides = parse_approach_overrides(args.approach_override)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc
    approach_direction = (args.approach_direction or args.corner).upper()
    apply_approach(plan, approach_direction, args.approach_distance, overrides)

    print(f"Computed orientation: {plan.orientation}°")
    print(f"Fill ratio: {plan.fill_ratio:.2%}")
    print("Blocks:")
    for block in plan.describe_blocks():
        print(f"  - {block}")
    print(f"Placements: {len(plan.placements)}")
    if collisions:
        print("Collisions detected:")
        for collision in collisions:
            print(f"  - {collision}")
    else:
        print("No collisions detected")

    generator = SnapPointGenerator()
    width, depth = (
        box.dimensions.width if plan.orientation == 0 else box.dimensions.depth,
        box.dimensions.depth if plan.orientation == 0 else box.dimensions.width,
    )
    snap_points = generator.generate(plan, width, depth)
    print(f"Generated snap points for {len(snap_points)} placements")

    annotator = PlacementAnnotator(
        default_approach=args.approach_distance,
        label_offset=args.label_offset,
    )
    annotations = annotator.annotate(plan)
    if annotations:
        print("Preview label & approach data:")
        for annotation in annotations[: min(3, len(annotations))]:
            label = annotation.label_position
            vector = annotation.approach_vector
            print(
                "  - placement #{idx}: label=({lx:.1f},{ly:.1f},{lz:.1f}) | approach {dir} {dist:.1f}mm vector=({vx:.1f},{vy:.1f},{vz:.1f})"
                .format(
                    idx=annotation.placement_index,
                    lx=label.x,
                    ly=label.y,
                    lz=label.z,
                    dir=annotation.approach_direction,
                    dist=annotation.approach_distance,
                    vx=vector.x,
                    vy=vector.y,
                    vz=vector.z,
                )
            )
    else:
        print("No annotations available (missing box metadata)")

    if args.export:
        exporter = PlanExporter(annotator=annotator)
        path = exporter.to_file(plan, args.export)
        print(f"Plan exported to {path}")

    repo.close()


def run_stack(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    try:
        pallet = _resolve_pallet(repo, args)
        box = _resolve_box(repo, args)
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    tool = repo.get_tool(args.tool)
    try:
        interleaf = _resolve_interleaf(repo, args)
    except KeyError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner=args.corner,
        reference_frame=reference_frame,
    )

    try:
        overrides = parse_approach_overrides(args.approach_override)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc

    sequence_planner = LayerSequencePlanner()
    collision_checker = CollisionChecker()
    sequence = sequence_planner.stack_layers(
        request,
        levels=args.layers,
        corners=args.corners,
        z_step=args.z_step,
        collision_checker=collision_checker,
        approach_overrides=overrides,
        interleaf=interleaf,
        interleaf_frequency=args.interleaf_frequency,
    )

    annotator = PlacementAnnotator(
        default_approach=args.approach_distance,
        label_offset=args.label_offset,
    )
    sequence.metadata["approach_distance"] = f"{args.approach_distance:.2f}"
    sequence.metadata["label_offset"] = f"{args.label_offset:.2f}"
    if args.approach_direction:
        sequence.metadata["approach_direction"] = args.approach_direction.upper()

    print(
        f"Computed {sequence.levels()} layers totaling {sequence.total_boxes()} boxes (max height {sequence.max_height():.2f}mm)"
    )
    for idx, layer in enumerate(sequence.layers, start=1):
        print(
            f"Layer {idx}: corner={layer.start_corner} orientation={layer.orientation} fill={layer.fill_ratio:.2%}"
        )
        layer_direction = (args.approach_direction or layer.start_corner).upper()
        apply_approach(layer, layer_direction, args.approach_distance, overrides)

        annotations = annotator.annotate(layer)
        if annotations:
            first = annotations[0]
            label = first.label_position
            vector = first.approach_vector
            print(
                "    label preview: ({lx:.1f},{ly:.1f},{lz:.1f}) approach {dir} {dist:.1f}mm vector=({vx:.1f},{vy:.1f},{vz:.1f})"
                .format(
                    lx=label.x,
                    ly=label.y,
                    lz=label.z,
                    dir=first.approach_direction,
                    dist=first.approach_distance,
                    vx=vector.x,
                    vy=vector.y,
                    vz=vector.z,
                )
            )
        if layer.collisions:
            for collision in layer.collisions:
                print(f"  - collision: {collision}")
        else:
            print("  - no collisions")

    if args.export:
        exporter = PlanExporter(annotator=annotator)
        path = exporter.to_file(sequence, args.export)
        print(f"Sequence exported to {path}")

    if sequence.interleaves:
        print(
            "Interfalde inserite:",
            ", ".join(
                f"dopo layer {entry.level} (+{entry.interleaf.thickness:.1f}mm)"
                for entry in sequence.interleaves
            ),
        )

    repo.close()


def run_render(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    try:
        pallet = _resolve_pallet(repo, args)
        box = _resolve_box(repo, args)
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    tool = repo.get_tool(args.tool)
    try:
        interleaf = _resolve_interleaf(repo, args)
    except KeyError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        repo.close()
        raise SystemExit(str(exc)) from exc

    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner=args.corner,
        reference_frame=reference_frame,
    )
    sequence_planner = LayerSequencePlanner()
    collision_checker = CollisionChecker()
    sequence = sequence_planner.stack_layers(
        request,
        levels=args.layers,
        corners=args.corners,
        z_step=args.z_step,
        collision_checker=collision_checker,
        interleaf=interleaf,
        interleaf_frequency=args.interleaf_frequency,
    )

    material_path: str | Path | None
    if getattr(args, "no_materials", False):
        material_path = None
    else:
        material_path = args.mtl or Path(args.output).with_suffix(".mtl")

    try:
        result = export_sequence_to_obj(
            sequence,
            request,
            args.output,
            include_pallet=not args.skip_pallet,
            explode_gap=args.explode_gap,
            palette=args.palette,
            material_path=material_path,
        )
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc

    repo.close()
    print(
        "Modello 3D generato: {path} (box={boxes}, facce totali={faces}, vertici={verts})".format(
            path=result.path,
            boxes=result.boxes,
            faces=result.faces,
            verts=result.vertices,
        )
    )
    if result.material_path:
        print(f"File materiali salvato in {result.material_path}")


def run_archive(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    try:
        pallet = _resolve_pallet(repo, args)
        box = _resolve_box(repo, args)
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    tool = repo.get_tool(args.tool)
    try:
        interleaf = _resolve_interleaf(repo, args)
    except KeyError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner=args.corner,
        reference_frame=reference_frame,
    )

    try:
        overrides = parse_approach_overrides(args.approach_override)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc

    annotator = PlacementAnnotator(
        default_approach=args.approach_distance,
        label_offset=args.label_offset,
    )
    exporter = PlanExporter(annotator=annotator)
    archiver = ProjectArchiver(exporter=exporter)

    if args.layers > 1:
        sequence_planner = LayerSequencePlanner()
        collision_checker = CollisionChecker()
        plan = sequence_planner.stack_layers(
            request,
            levels=args.layers,
            corners=args.corners,
            z_step=args.z_step,
            collision_checker=collision_checker,
            approach_overrides=overrides,
            interleaf=interleaf,
            interleaf_frequency=args.interleaf_frequency,
        )
        plan.metadata["approach_distance"] = f"{args.approach_distance:.2f}"
        plan.metadata["label_offset"] = f"{args.label_offset:.2f}"
        if args.approach_direction:
            plan.metadata["approach_direction"] = args.approach_direction.upper()
        for layer in plan.layers:
            layer_direction = (args.approach_direction or layer.start_corner).upper()
            apply_approach(layer, layer_direction, args.approach_distance, overrides)
    else:
        plan = _calculate_layer(request)
        direction = (args.approach_direction or args.corner).upper()
        apply_approach(plan, direction, args.approach_distance, overrides)

    notes = _build_notes(args.note)
    project = archiver.build(
        name=args.name,
        plan=plan,
        pallet=pallet,
        box=box,
        tool=tool,
        metadata=notes,
    )
    path = archiver.save(project, args.archive)
    print(f"Archivio creato: {path}")
    print(
        f"  - layers: {project.summary.get('layers')} total_boxes: {project.summary.get('total_boxes')} max_height: {project.summary.get('max_height_mm')}mm"
    )
    repo.close()


def run_gui(args: argparse.Namespace) -> None:
    try:
        from .gui import PalletGuiApp
    except RuntimeError as exc:  # pragma: no cover - optional dependency
        raise SystemExit(str(exc)) from exc

    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    pallets = repo.list_pallets()
    boxes = repo.list_boxes()
    tools = repo.list_tools()
    interleaves = repo.list_interleaves()

    def _default_selection(items, requested, label):
        if not items:
            repo.close()
            raise SystemExit(f"Nessun {label} disponibile nel database.")
        if requested is None:
            return items[0].id
        for item in items:
            if item.id == requested:
                return requested
        repo.close()
        raise SystemExit(f"{label} '{requested}' non trovato nel database.")

    default_pallet_id = _default_selection(pallets, args.pallet, "pallet")
    default_box_id = _default_selection(boxes, args.box, "box")
    default_tool_id = _default_selection(tools, args.tool, "tool")

    if args.interleaf:
        if not any(interleaf.id == args.interleaf for interleaf in interleaves):
            repo.close()
            raise SystemExit(f"Interfalda '{args.interleaf}' non trovata nel database.")
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        repo.close()
        raise SystemExit(str(exc)) from exc
    try:
        app = PalletGuiApp(
            pallets=pallets,
            boxes=boxes,
            tools=tools,
            interleaves=interleaves,
            reference_frame=reference_frame,
            default_pallet_id=default_pallet_id,
            default_box_id=default_box_id,
            default_tool_id=default_tool_id,
            default_corner=args.corner,
            default_layers=args.layers,
            default_corners=args.corners,
            default_z_step=args.z_step,
            default_interleaf_id=args.interleaf,
            default_interleaf_frequency=args.interleaf_frequency,
            default_approach_direction=args.approach_direction,
            default_approach_distance=args.approach_distance,
            default_label_offset=args.label_offset,
            default_approach_overrides=args.approach_override,
        )
    except RuntimeError as exc:  # pragma: no cover - optional dependency
        repo.close()
        raise SystemExit(str(exc)) from exc

    repo.close()
    app.run()


def run_analyze(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    try:
        pallet = _resolve_pallet(repo, args)
        box = _resolve_box(repo, args)
    except ValueError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    tool = repo.get_tool(args.tool)
    try:
        interleaf = _resolve_interleaf(repo, args)
    except KeyError as exc:
        repo.close()
        raise SystemExit(str(exc)) from exc
    try:
        reference_frame = _reference_frame_from_args(args.origin, args.axes)
    except ValueError as exc:  # pragma: no cover - defensive user input
        repo.close()
        raise SystemExit(str(exc)) from exc

    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        start_corner=args.corner,
        reference_frame=reference_frame,
    )

    if args.layers > 1:
        sequence_planner = LayerSequencePlanner()
        sequence = sequence_planner.stack_layers(
            request,
            levels=args.layers,
            corners=args.corners,
            z_step=args.z_step,
            collision_checker=CollisionChecker(),
            interleaf=interleaf,
            interleaf_frequency=args.interleaf_frequency,
        )
        metrics = compute_sequence_metrics(sequence)
        print(
            "Analisi sequenza: {layers} strati, {boxes} scatole, peso totale {weight:.2f}kg".format(
                layers=metrics.layers,
                boxes=metrics.total_boxes,
                weight=metrics.total_weight,
            )
        )
    else:
        plan = _calculate_layer(request)
        metrics = compute_layer_metrics(plan)
        print(
            "Analisi strato singolo: {boxes} scatole, peso totale {weight:.2f}kg, fill {fill:.2%}".format(
                boxes=metrics.total_boxes,
                weight=metrics.total_weight,
                fill=plan.fill_ratio,
            )
        )

    print(
        "Centro di massa: ({:.1f}, {:.1f}, {:.1f}) mm".format(
            metrics.center_of_mass.x,
            metrics.center_of_mass.y,
            metrics.center_of_mass.z,
        )
    )
    print(
        "Ingombro: {:.1f} x {:.1f} mm".format(
            metrics.footprint_width,
            metrics.footprint_depth,
        )
    )
    print(f"Altezza massima: {metrics.max_height:.1f} mm")
    repo.close()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "plan":
        run_plan(args)
    elif args.command == "stack":
        run_stack(args)
    elif args.command == "archive":
        run_archive(args)
    elif args.command == "catalog":
        run_catalog(args)
    elif args.command == "gui":
        run_gui(args)
    elif args.command == "analyze":
        run_analyze(args)
    elif args.command == "plc":
        run_plc(args)
    elif args.command == "render":
        run_render(args)


if __name__ == "__main__":  # pragma: no cover
    main()
