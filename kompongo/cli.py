"""Command line interface for KomPonGo."""
from __future__ import annotations

import argparse
from typing import Dict

from .annotations import PlacementAnnotator
from .collisions import CollisionChecker
from .exporter import PlanExporter
from .models import ApproachConfig, LayerPlan, LayerRequest
from .planner import RecursiveFiveBlockPlanner
from .project import ProjectArchiver
from .repository import DataRepository
from .sequence import LayerSequencePlanner
from .snap import SnapPointGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KomPonGo planner")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_parser = sub.add_parser("plan", help="Compute a pallet layer")
    plan_parser.add_argument("--pallet", required=True, help="Pallet id")
    plan_parser.add_argument("--box", required=True, help="Box id")
    plan_parser.add_argument("--tool", required=True, help="Tool id")
    plan_parser.add_argument("--corner", default="SW", help="Start corner")
    plan_parser.add_argument("--db", default="kompongo.db", help="Database path")
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
    stack_parser.add_argument("--corners", nargs="*", help="Sequence of corners per level")
    stack_parser.add_argument("--layers", type=int, default=2, help="Number of layers to stack")
    stack_parser.add_argument("--z-step", type=float, help="Custom Z increment between layers")
    stack_parser.add_argument("--db", default="kompongo.db", help="Database path")
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
    archive_parser.add_argument("--name", default="KomPonGo Project", help="Nome progetto")
    archive_parser.add_argument("--pallet", required=True, help="Pallet id")
    archive_parser.add_argument("--box", required=True, help="Box id")
    archive_parser.add_argument("--tool", required=True, help="Tool id")
    archive_parser.add_argument("--corner", default="SW", help="Corner iniziale")
    archive_parser.add_argument("--corners", nargs="*", help="Corner per ogni livello (multi layer)")
    archive_parser.add_argument("--layers", type=int, default=1, help="Numero di strati")
    archive_parser.add_argument("--z-step", type=float, help="Incremento Z personalizzato tra gli strati")
    archive_parser.add_argument("--db", default="kompongo.db", help="Database path")
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
        choices=["pallets", "boxes", "tools"],
        help="Tipo di dati da mostrare",
    )
    catalog_parser.add_argument("--db", default="kompongo.db", help="Percorso database")
    catalog_parser.add_argument(
        "--seed",
        default="data/seed_data.json",
        help="Seed data path (crea il db se necessario)",
    )
    return parser


def _parse_overrides(values: list[str] | None) -> Dict[str, ApproachConfig]:
    overrides: Dict[str, ApproachConfig] = {}
    if not values:
        return overrides
    for value in values:
        try:
            block, payload = value.split("=", 1)
            direction, distance = payload.split(":", 1)
            overrides[block.strip().lower()] = ApproachConfig(
                direction=direction.strip().upper(),
                distance=float(distance),
            )
        except ValueError as exc:
            raise ValueError(
                f"Formato override non valido '{value}'. Usa blocco=DIREZIONE:DISTANZA"
            ) from exc
    return overrides


def _apply_approach(plan: LayerPlan, direction: str, distance: float, overrides: Dict[str, ApproachConfig]) -> None:
    plan.metadata["approach_direction"] = direction
    plan.metadata["approach_distance"] = f"{distance:.2f}"
    plan.approach_overrides = overrides.copy()


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
    if args.entity == "pallets":
        pallets = repo.list_pallets()
        rows = [
            (
                pallet.id,
                f"{pallet.dimensions.width:.0f}x{pallet.dimensions.depth:.0f}x{pallet.dimensions.height:.0f}",
                f"±X {pallet.max_overhang_x:.0f} | ±Y {pallet.max_overhang_y:.0f}",
            )
            for pallet in pallets
        ]
        headers = ("ID", "Dimensioni (mm)", "Sbordo max (mm)")
    elif args.entity == "boxes":
        boxes = repo.list_boxes()
        rows = [
            (
                box.id,
                f"{box.dimensions.width:.0f}x{box.dimensions.depth:.0f}x{box.dimensions.height:.0f}",
                f"{box.weight:.2f}kg",
                box.label_position or "-",
            )
            for box in boxes
        ]
        headers = ("ID", "Dimensioni (mm)", "Peso", "Etichetta")
    else:
        tools = repo.list_tools()
        rows = [
            (
                tool.id,
                tool.name,
                str(tool.max_boxes),
                ",".join(str(value) for value in tool.allowed_orientations) or "-",
                f"({tool.pickup_offset.x:.0f},{tool.pickup_offset.y:.0f},{tool.pickup_offset.z:.0f})",
            )
            for tool in tools
        ]
        headers = ("ID", "Nome", "# Scatole", "Orientazioni", "Offset (mm)")

    if rows:
        _print_table(headers, rows)
    else:
        print("Nessun dato disponibile")
    repo.close()


def run_plan(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    pallet = repo.get_pallet(args.pallet)
    box = repo.get_box(args.box)
    tool = repo.get_tool(args.tool)
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        pickup_offset=tool.pickup_offset,
        start_corner=args.corner,
    )

    plan = _calculate_layer(request)
    collisions = plan.collisions

    try:
        overrides = _parse_overrides(args.approach_override)
    except ValueError as exc:  # pragma: no cover - defensive user input
        raise SystemExit(str(exc)) from exc
    approach_direction = (args.approach_direction or args.corner).upper()
    _apply_approach(plan, approach_direction, args.approach_distance, overrides)

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
    pallet = repo.get_pallet(args.pallet)
    box = repo.get_box(args.box)
    tool = repo.get_tool(args.tool)
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        pickup_offset=tool.pickup_offset,
        start_corner=args.corner,
    )

    try:
        overrides = _parse_overrides(args.approach_override)
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
        _apply_approach(layer, layer_direction, args.approach_distance, overrides)

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

    repo.close()


def run_archive(args: argparse.Namespace) -> None:
    repo = DataRepository(args.db)
    repo.initialize(args.seed)
    pallet = repo.get_pallet(args.pallet)
    box = repo.get_box(args.box)
    tool = repo.get_tool(args.tool)
    request = LayerRequest(
        pallet=pallet,
        box=box,
        tool=tool,
        pickup_offset=tool.pickup_offset,
        start_corner=args.corner,
    )

    try:
        overrides = _parse_overrides(args.approach_override)
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
        )
        plan.metadata["approach_distance"] = f"{args.approach_distance:.2f}"
        plan.metadata["label_offset"] = f"{args.label_offset:.2f}"
        if args.approach_direction:
            plan.metadata["approach_direction"] = args.approach_direction.upper()
        for layer in plan.layers:
            layer_direction = (args.approach_direction or layer.start_corner).upper()
            _apply_approach(layer, layer_direction, args.approach_distance, overrides)
    else:
        plan = _calculate_layer(request)
        direction = (args.approach_direction or args.corner).upper()
        _apply_approach(plan, direction, args.approach_distance, overrides)

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


if __name__ == "__main__":  # pragma: no cover
    main()
