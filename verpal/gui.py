"""Graphical interface helpers for VerPal."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .annotations import PlacementAnnotator, PlacementAnnotation
from .approach import apply_approach, parse_approach_overrides
from .collisions import CollisionChecker
from .exporter import PlanExporter
from .metrics import compute_layer_metrics, compute_sequence_metrics
from .models import (
    ApproachConfig,
    Box,
    Interleaf,
    LayerPlan,
    LayerPlacement,
    LayerRequest,
    LayerSequencePlan,
    Pallet,
    ReferenceFrame,
    Tool,
    Vector3,
)
from .plc import SiemensPLCExporter
from .planner import RecursiveFiveBlockPlanner
from .sequence import LayerSequencePlanner


@dataclass(frozen=True)
class PlacementGlyph:
    """Representation of a placement projected on a 2D canvas."""

    placement_index: int
    block: str
    center: Vector3
    width: float
    depth: float
    rotation: int
    color: str


@dataclass(frozen=True)
class LayerViewModel:
    """Snapshot of a layer converted to drawable primitives."""

    pallet_width: float
    pallet_depth: float
    overhang_x: float
    overhang_y: float
    placements: list[PlacementGlyph]


@dataclass(frozen=True)
class HeightRow:
    label: str
    base: float
    top: float


@dataclass(frozen=True)
class MetricLine:
    """Single entry used to show metric summaries inside the GUI."""

    label: str
    value: str


_COLOR_PALETTE = [
    "#3c6e71",
    "#f4a259",
    "#8ab17d",
    "#f26419",
    "#355070",
    "#6d597a",
    "#b56576",
    "#eaac8b",
]


def build_layer_view_model(plan: LayerPlan, request: LayerRequest) -> LayerViewModel:
    """Convert the layer plan into drawable glyphs."""

    frame = request.reference_frame
    placements: list[PlacementGlyph] = []
    for idx, placement in enumerate(plan.placements):
        physical = frame.restore(
            placement.position,
            pallet=request.pallet,
            overhang_x=request.overhang_x,
            overhang_y=request.overhang_y,
        )
        width, depth = _box_footprint(request.box.dimensions.width, request.box.dimensions.depth, placement.rotation)
        placements.append(
            PlacementGlyph(
                placement_index=idx,
                block=placement.block,
                center=physical,
                width=width,
                depth=depth,
                rotation=placement.rotation,
                color=_color_for_block(placement.block, idx),
            )
        )
    return LayerViewModel(
        pallet_width=request.pallet.dimensions.width,
        pallet_depth=request.pallet.dimensions.depth,
        overhang_x=request.overhang_x,
        overhang_y=request.overhang_y,
        placements=placements,
    )


def compute_height_report(
    request: LayerRequest,
    plan: LayerPlan,
    sequence: LayerSequencePlan | None = None,
) -> list[HeightRow]:
    """Return the base/top quota for each layer in the plan."""

    rows: list[HeightRow] = []
    layers: Iterable[LayerPlan]
    if sequence is not None:
        layers = sequence.layers
    else:
        layers = [plan]

    for idx, layer in enumerate(layers, start=1):
        base = _layer_base(layer)
        top = base + request.box.dimensions.height
        rows.append(HeightRow(label=f"Layer {idx}", base=base, top=top))

    if rows:
        total_top = max(row.top for row in rows)
        rows.append(HeightRow(label="Totale", base=0.0, top=total_top))
    return rows


def build_metric_summary(
    plan: LayerPlan,
    sequence: LayerSequencePlan | None = None,
) -> list[MetricLine]:
    """Return formatted metric rows for the active layer or sequence."""

    if sequence is not None:
        metrics = compute_sequence_metrics(sequence)
        lines: list[MetricLine] = [
            MetricLine("Modalità", "Sequenza multistrato"),
            MetricLine("Strati", str(metrics.layers)),
            MetricLine("Scatole totali", str(metrics.total_boxes)),
        ]
    else:
        metrics = compute_layer_metrics(plan)
        lines = [
            MetricLine("Modalità", "Layer singolo"),
            MetricLine("Scatole totali", str(metrics.total_boxes)),
        ]
    lines.append(MetricLine("Peso totale", f"{metrics.total_weight:.2f} kg"))
    lines.append(
        MetricLine(
            "Centro di massa",
            "x={:.1f} y={:.1f} z={:.1f} mm".format(
                metrics.center_of_mass.x,
                metrics.center_of_mass.y,
                metrics.center_of_mass.z,
            ),
        )
    )
    lines.append(
        MetricLine(
            "Ingombro",
            "{:.1f} x {:.1f} mm".format(
                metrics.footprint_width,
                metrics.footprint_depth,
            ),
        )
    )
    lines.append(MetricLine("Altezza max", f"{metrics.max_height:.1f} mm"))
    return lines


def _box_footprint(width: float, depth: float, rotation: int) -> tuple[float, float]:
    if rotation % 180 == 0:
        return width, depth
    return depth, width


def _layer_base(layer: LayerPlan) -> float:
    if not layer.placements:
        return 0.0
    return min(placement.position.z for placement in layer.placements)


def _color_for_block(block: str, idx: int) -> str:
    if not _COLOR_PALETTE:
        return "#3c6e71"
    token = block or str(idx)
    return _COLOR_PALETTE[hash(token) % len(_COLOR_PALETTE)]


def _import_tk() -> tuple[object, object, object, object]:  # pragma: no cover - runtime import
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Tkinter non disponibile. Installa il pacchetto python3-tk per usare l'interfaccia grafica."
        ) from exc
    return tk, messagebox, ttk, filedialog


def _import_matplotlib() -> tuple[object, object, object]:  # pragma: no cover - runtime import
    try:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Matplotlib è richiesto per la visualizzazione 3D. Installa il pacchetto 'matplotlib'."
        ) from exc
    return Figure, FigureCanvasTkAgg, Poly3DCollection


def _build_canvas_class(tk_module):  # pragma: no cover - GUI wiring
    class DragDropCanvas(tk_module.Canvas):
        def __init__(
            self,
            master,
            plan: LayerPlan,
            request: LayerRequest,
            *,
            on_change: Callable[[LayerPlan], None] | None = None,
            on_status: Callable[[str], None] | None = None,
            **kwargs,
        ) -> None:
            super().__init__(master, background="#f7f7f7", highlightthickness=0, **kwargs)
            self.plan = plan
            self.request = request
            self._on_change = on_change
            self._on_status = on_status
            self._drag_tag: str | None = None
            self._drag_start: tuple[int, int] | None = None
            self._margin = 24
            self._scale = 1.0
            self._draw()
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<B1-Motion>", self._on_drag)
            self.bind("<ButtonRelease-1>", self._on_release)

        def refresh(self) -> None:
            self._draw()

        def _draw(self) -> None:
            self.delete("all")
            self.view_model = build_layer_view_model(self.plan, self.request)
            usable_width = self.view_model.pallet_width + self.view_model.overhang_x * 2
            usable_depth = self.view_model.pallet_depth + self.view_model.overhang_y * 2
            width = int(self.winfo_reqwidth() or 640)
            height = int(self.winfo_reqheight() or 480)
            self._scale = min(
                (width - self._margin * 2) / usable_width if usable_width else 1.0,
                (height - self._margin * 2) / usable_depth if usable_depth else 1.0,
            )
            if self._scale <= 0:
                self._scale = 1.0

            pallet_x1 = self._mm_to_px(0.0, axis="x")
            pallet_y1 = self._mm_to_px(0.0, axis="y")
            pallet_x2 = self._mm_to_px(self.view_model.pallet_width, axis="x")
            pallet_y2 = self._mm_to_px(self.view_model.pallet_depth, axis="y")
            self.create_rectangle(
                pallet_x1,
                pallet_y1,
                pallet_x2,
                pallet_y2,
                outline="#9aa5b1",
                fill="#dfe7ec",
                tags=("pallet",),
            )

            for glyph in self.view_model.placements:
                tag = f"placement-{glyph.placement_index}"
                x1 = self._mm_to_px(glyph.center.x - glyph.width / 2, axis="x")
                y1 = self._mm_to_px(glyph.center.y - glyph.depth / 2, axis="y")
                x2 = self._mm_to_px(glyph.center.x + glyph.width / 2, axis="x")
                y2 = self._mm_to_px(glyph.center.y + glyph.depth / 2, axis="y")
                self.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=glyph.color,
                    outline="#374151",
                    tags=("placement", tag),
                )
                self.create_text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2,
                    text=str(glyph.placement_index + 1),
                    fill="#ffffff",
                    tags=("placement", tag),
                )

        def _on_press(self, event) -> None:
            current = self.find_withtag("current")
            if not current:
                return
            tags = self.gettags(current[0])
            placement_tag = next((tag for tag in tags if tag.startswith("placement-")), None)
            if not placement_tag:
                return
            self._drag_tag = placement_tag
            self._drag_start = (event.x, event.y)

        def _on_drag(self, event) -> None:
            if not self._drag_tag or not self._drag_start:
                return
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self.move(self._drag_tag, dx, dy)
            self._drag_start = (event.x, event.y)

        def _on_release(self, event) -> None:
            if not self._drag_tag:
                return
            bbox = self.bbox(self._drag_tag)
            if not bbox:
                return
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            placement_index = int(self._drag_tag.split("-", 1)[1])
            placement = self.plan.placements[placement_index]
            new_x = self._px_to_mm(center_x, axis="x")
            new_y = self._px_to_mm(center_y, axis="y")
            clamped_x = max(-self.request.overhang_x, min(self.view_model.pallet_width + self.request.overhang_x, new_x))
            clamped_y = max(-self.request.overhang_y, min(self.view_model.pallet_depth + self.request.overhang_y, new_y))
            updated = Vector3(x=clamped_x, y=clamped_y, z=placement.position.z)
            transformed = self.request.reference_frame.transform(
                updated,
                pallet=self.request.pallet,
                overhang_x=self.request.overhang_x,
                overhang_y=self.request.overhang_y,
            )
            placement.position = Vector3(transformed.x, transformed.y, transformed.z)
            if self._on_status is not None:
                self._on_status(
                    "Placement #{idx} -> X={x:.1f}mm Y={y:.1f}mm".format(
                        idx=placement_index + 1,
                        x=clamped_x,
                        y=clamped_y,
                    )
                )
            if self._on_change is not None:
                self._on_change(self.plan)
            self._drag_tag = None
            self._drag_start = None

        def _mm_to_px(self, value: float, *, axis: str) -> float:
            offset = self.request.overhang_x if axis == "x" else self.request.overhang_y
            return self._margin + (value + offset) * self._scale

        def _px_to_mm(self, value: float, *, axis: str) -> float:
            offset = self.request.overhang_x if axis == "x" else self.request.overhang_y
            return (value - self._margin) / self._scale - offset

    return DragDropCanvas


class PalletGuiApp:
    """Tkinter GUI that visualizes the layer, 3D model and repository data."""

    _NO_INTERLEAF_VALUE = "(nessuna interfalda)"

    def __init__(
        self,
        *,
        pallets: Sequence[Pallet],
        boxes: Sequence[Box],
        tools: Sequence[Tool],
        interleaves: Sequence[Interleaf],
        reference_frame: ReferenceFrame,
        default_pallet_id: str,
        default_box_id: str,
        default_tool_id: str,
        default_corner: str = "SW",
        default_layers: int = 1,
        default_corners: Sequence[str] | None = None,
        default_z_step: float | None = None,
        default_interleaf_id: str | None = None,
        default_interleaf_frequency: int = 1,
        default_approach_direction: str | None = None,
        default_approach_distance: float = 75.0,
        default_label_offset: float = 5.0,
        default_approach_overrides: Sequence[str] | None = None,
    ) -> None:
        self.pallets = list(pallets)
        self.boxes = list(boxes)
        self.tools = list(tools)
        self.interleaves = list(interleaves)
        self.reference_frame = reference_frame
        self._layer_planner = RecursiveFiveBlockPlanner()
        self._sequence_planner = LayerSequencePlanner(self._layer_planner)
        self._collision_checker = CollisionChecker()
        self._default_approach_distance = default_approach_distance
        self._default_label_offset = default_label_offset
        self._annotator = PlacementAnnotator(
            default_approach=default_approach_distance,
            label_offset=default_label_offset,
        )
        self._annotations: list[PlacementAnnotation] = []

        tk_module, messagebox, ttk, filedialog = _import_tk()
        Figure, FigureCanvasTkAgg, Poly3DCollection = _import_matplotlib()
        self._messagebox = messagebox
        self._filedialog = filedialog
        self._FigureCanvasTkAgg = FigureCanvasTkAgg
        self._Figure = Figure
        self._Poly3DCollection = Poly3DCollection
        DragCanvas = _build_canvas_class(tk_module)
        self._plc_exporter = SiemensPLCExporter()

        self.root = tk_module.Tk()
        self.root.title("VerPal - Configuratore Grafico")
        self.root.geometry("1280x720")
        self.root.minsize(1024, 560)

        self.pallet_var = tk_module.StringVar(value=default_pallet_id)
        self.box_var = tk_module.StringVar(value=default_box_id)
        self.tool_var = tk_module.StringVar(value=default_tool_id)
        self.corner_var = tk_module.StringVar(value=default_corner.upper())
        self.layers_var = tk_module.IntVar(value=max(1, default_layers))
        self.corners_var = tk_module.StringVar(value=" ".join(default_corners or []))
        self.z_step_var = tk_module.StringVar(
            value="" if default_z_step is None else f"{default_z_step:.3f}"
        )
        self.interleaf_var = tk_module.StringVar(
            value=default_interleaf_id or self._NO_INTERLEAF_VALUE
        )
        self.interleaf_frequency_var = tk_module.IntVar(
            value=max(1, default_interleaf_frequency)
        )
        direction_default = (
            (default_approach_direction or "").strip().upper()
        )
        self.approach_direction_var = tk_module.StringVar(value=direction_default)
        self.approach_distance_var = tk_module.StringVar(
            value=f"{default_approach_distance:.1f}"
        )
        self.label_offset_var = tk_module.StringVar(
            value=f"{default_label_offset:.1f}"
        )
        override_text = " ".join(default_approach_overrides or [])
        self.approach_override_var = tk_module.StringVar(value=override_text)

        try:
            self.request, self.plan, self.sequence = self._build_plan()
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        main = ttk.Frame(self.root)
        main.pack(fill=tk_module.BOTH, expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.canvas = DragCanvas(
            left,
            plan=self.plan,
            request=self.request,
            on_change=self._on_canvas_change,
            on_status=self._update_status,
            width=720,
            height=640,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(left)
        controls.grid(row=1, column=0, sticky="ew", pady=4)
        controls.columnconfigure(0, weight=1)
        ttk.Button(controls, text="Calcola quote", command=self._show_heights).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(controls, text="Reset vista", command=self._reset_view).grid(
            row=0, column=1, padx=4
        )

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=0)
        right.rowconfigure(2, weight=1)
        right.rowconfigure(3, weight=0)
        right.columnconfigure(0, weight=1)

        config = ttk.LabelFrame(right, text="Dati disponibili nel DB")
        config.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        for i in range(2):
            config.columnconfigure(i, weight=1)

        ttk.Label(config, text="Pallet").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        pallet_combo = ttk.Combobox(
            config,
            textvariable=self.pallet_var,
            values=[pallet.id for pallet in self.pallets],
            state="readonly",
        )
        pallet_combo.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        pallet_combo.bind("<<ComboboxSelected>>", self._on_inputs_changed)

        ttk.Label(config, text="Scatola").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        box_combo = ttk.Combobox(
            config,
            textvariable=self.box_var,
            values=[box.id for box in self.boxes],
            state="readonly",
        )
        box_combo.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        box_combo.bind("<<ComboboxSelected>>", self._on_inputs_changed)

        ttk.Label(config, text="Tool").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        tool_combo = ttk.Combobox(
            config,
            textvariable=self.tool_var,
            values=[tool.id for tool in self.tools],
            state="readonly",
        )
        tool_combo.grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        tool_combo.bind("<<ComboboxSelected>>", self._on_inputs_changed)

        ttk.Label(config, text="Corner iniziale").grid(
            row=3, column=0, sticky="w", padx=2, pady=2
        )
        corner_combo = ttk.Combobox(
            config,
            textvariable=self.corner_var,
            values=["SW", "SE", "NW", "NE"],
            state="readonly",
        )
        corner_combo.grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        corner_combo.bind("<<ComboboxSelected>>", self._on_inputs_changed)

        ttk.Label(config, text="Numero strati").grid(
            row=4, column=0, sticky="w", padx=2, pady=2
        )
        layers_spin = tk_module.Spinbox(
            config,
            from_=1,
            to=50,
            textvariable=self.layers_var,
            width=6,
            command=self._on_inputs_changed,
        )
        layers_spin.grid(row=4, column=1, sticky="w", padx=2, pady=2)
        layers_spin.bind("<Return>", self._on_inputs_changed)

        ttk.Label(config, text="Sequenza corner").grid(
            row=5, column=0, sticky="w", padx=2, pady=2
        )
        corners_entry = ttk.Entry(config, textvariable=self.corners_var)
        corners_entry.grid(row=5, column=1, sticky="ew", padx=2, pady=2)
        corners_entry.bind("<Return>", self._on_inputs_changed)
        corners_entry.bind("<FocusOut>", self._on_inputs_changed)

        ttk.Label(config, text="Step Z (mm)").grid(row=6, column=0, sticky="w", padx=2, pady=2)
        z_entry = ttk.Entry(config, textvariable=self.z_step_var)
        z_entry.grid(row=6, column=1, sticky="ew", padx=2, pady=2)
        z_entry.bind("<Return>", self._on_inputs_changed)
        z_entry.bind("<FocusOut>", self._on_inputs_changed)

        ttk.Label(config, text="Interfalda").grid(row=7, column=0, sticky="w", padx=2, pady=2)
        interleaf_values = [self._NO_INTERLEAF_VALUE] + [
            interleaf.id for interleaf in self.interleaves
        ]
        interleaf_combo = ttk.Combobox(
            config,
            textvariable=self.interleaf_var,
            values=interleaf_values,
            state="readonly",
        )
        interleaf_combo.grid(row=7, column=1, sticky="ew", padx=2, pady=2)
        interleaf_combo.bind("<<ComboboxSelected>>", self._on_inputs_changed)

        ttk.Label(config, text="Freq. interfalda").grid(
            row=8, column=0, sticky="w", padx=2, pady=2
        )
        interleaf_spin = tk_module.Spinbox(
            config,
            from_=1,
            to=50,
            textvariable=self.interleaf_frequency_var,
            width=6,
            command=self._on_inputs_changed,
        )
        interleaf_spin.grid(row=8, column=1, sticky="w", padx=2, pady=2)
        interleaf_spin.bind("<Return>", self._on_inputs_changed)

        ttk.Button(config, text="Ricalcola schema", command=self._on_inputs_changed).grid(
            row=9, column=0, columnspan=2, sticky="ew", padx=2, pady=(8, 2)
        )

        approach = ttk.LabelFrame(right, text="Accostamento e annotazioni")
        approach.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        for i in range(2):
            approach.columnconfigure(i, weight=1)
        ttk.Label(approach, text="Direzione (lascia vuoto per usare il corner)").grid(
            row=0, column=0, sticky="w", padx=2, pady=2
        )
        direction_combo = ttk.Combobox(
            approach,
            textvariable=self.approach_direction_var,
            values=["", "N", "S", "E", "W", "NE", "NW", "SE", "SW"],
        )
        direction_combo.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        direction_combo.bind("<<ComboboxSelected>>", self._on_inputs_changed)
        direction_combo.bind("<Return>", self._on_inputs_changed)

        ttk.Label(approach, text="Distanza accostamento (mm)").grid(
            row=1, column=0, sticky="w", padx=2, pady=2
        )
        distance_entry = ttk.Entry(approach, textvariable=self.approach_distance_var)
        distance_entry.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        distance_entry.bind("<Return>", self._on_inputs_changed)
        distance_entry.bind("<FocusOut>", self._on_inputs_changed)

        ttk.Label(approach, text="Offset etichetta (mm)").grid(
            row=2, column=0, sticky="w", padx=2, pady=2
        )
        label_entry = ttk.Entry(approach, textvariable=self.label_offset_var)
        label_entry.grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        label_entry.bind("<Return>", self._on_inputs_changed)
        label_entry.bind("<FocusOut>", self._on_inputs_changed)

        ttk.Label(approach, text="Override blocchi (es. center=E:110)").grid(
            row=3, column=0, sticky="w", padx=2, pady=2
        )
        override_entry = ttk.Entry(approach, textvariable=self.approach_override_var)
        override_entry.grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        override_entry.bind("<Return>", self._on_inputs_changed)
        override_entry.bind("<FocusOut>", self._on_inputs_changed)

        ttk.Button(approach, text="Anteprima etichette", command=self._show_annotations).grid(
            row=4, column=0, sticky="ew", padx=2, pady=(4, 2)
        )
        ttk.Button(approach, text="Verifica collisioni", command=self._check_collisions).grid(
            row=4, column=1, sticky="ew", padx=2, pady=(4, 2)
        )

        info_panel = ttk.Frame(right)
        info_panel.grid(row=2, column=0, sticky="nsew", padx=4)
        info_panel.rowconfigure(0, weight=1)
        info_panel.rowconfigure(1, weight=0)
        info_panel.columnconfigure(0, weight=1)

        self.figure = self._Figure(figsize=(4, 4))
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.canvas3d = self._FigureCanvasTkAgg(self.figure, master=info_panel)
        self.canvas3d.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        placements = ttk.LabelFrame(info_panel, text="Dettagli posizionamenti")
        placements.grid(row=1, column=0, sticky="ew", pady=4)
        placements.columnconfigure(0, weight=1)
        columns = ("idx", "block", "center", "rotation", "approach", "label")
        self.placement_tree = ttk.Treeview(
            placements,
            columns=columns,
            show="headings",
            height=6,
        )
        headings = {
            "idx": "#",
            "block": "Blocco",
            "center": "Centro (mm)",
            "rotation": "Rotazione",
            "approach": "Accostamento",
            "label": "Etichetta (mm)",
        }
        for column, title in headings.items():
            self.placement_tree.heading(column, text=title)
            self.placement_tree.column(column, width=110 if column != "center" else 220)
        self.placement_tree.grid(row=0, column=0, sticky="ew")
        tree_scroll = ttk.Scrollbar(placements, orient="vertical", command=self.placement_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.placement_tree.configure(yscrollcommand=tree_scroll.set)

        metrics_frame = ttk.LabelFrame(right, text="Metriche e export")
        metrics_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.columnconfigure(1, weight=1)
        self.metrics_var = tk_module.StringVar()
        ttk.Label(metrics_frame, textvariable=self.metrics_var, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=2, pady=2
        )
        ttk.Button(metrics_frame, text="Esporta JSON", command=self._export_json).grid(
            row=1, column=0, sticky="ew", padx=2, pady=2
        )
        ttk.Button(metrics_frame, text="Esporta PLC", command=self._export_plc).grid(
            row=1, column=1, sticky="ew", padx=2, pady=2
        )

        self.status_var = tk_module.StringVar()
        self.status_var.set(
            "Configura pallet, scatole, falde e parametri di accostamento dalla barra destra."
        )
        ttk.Label(main, textvariable=self.status_var, anchor="w").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=2,
        )

        self._refresh_annotations()
        self._refresh_metrics()
        self._render_3d()

    def run(self) -> None:  # pragma: no cover - UI loop
        self.root.mainloop()

    def _on_canvas_change(self, _plan: LayerPlan) -> None:  # pragma: no cover - UI callback
        self.canvas.refresh()
        self._refresh_annotations()
        self._refresh_metrics()
        self._render_3d()

    def _update_status(self, message: str) -> None:  # pragma: no cover - UI callback
        self.status_var.set(message)

    def _show_heights(self) -> None:  # pragma: no cover - UI callback
        rows = compute_height_report(self.request, self.plan, self.sequence)
        if not rows:
            self._messagebox.showinfo("Quote", "Nessuna quota disponibile")
            return
        lines = [f"{row.label}: base={row.base:.1f}mm top={row.top:.1f}mm" for row in rows]
        self._messagebox.showinfo("Quote", "\n".join(lines))

    def _show_annotations(self) -> None:  # pragma: no cover - UI callback
        if not self._annotations:
            self._messagebox.showinfo(
                "Annotazioni",
                "Nessuna informazione di etichetta disponibile per lo strato attivo.",
            )
            return
        lines = []
        for annotation in self._annotations:
            label_pos = self._restore_position(annotation.label_position)
            lines.append(
                "Placement #{idx}: label=({lx:.1f},{ly:.1f},{lz:.1f})mm | {dir} {dist:.1f}mm".format(
                    idx=annotation.placement_index + 1,
                    lx=label_pos.x,
                    ly=label_pos.y,
                    lz=label_pos.z,
                    dir=annotation.approach_direction,
                    dist=annotation.approach_distance,
                )
            )
        self._messagebox.showinfo("Annotazioni", "\n".join(lines))

    def _check_collisions(self) -> None:  # pragma: no cover - UI callback
        collisions = self._collision_checker.validate(self.plan, self.request)
        if not collisions:
            self._messagebox.showinfo("Collisioni", "Nessuna collisione rilevata")
            self.status_var.set("Nessuna collisione o sbordo rilevato")
            return
        lines = [collision.description for collision in collisions]
        self._messagebox.showwarning("Collisioni", "\n".join(lines))
        self.status_var.set(f"Trovate {len(lines)} collisioni")

    def _reset_view(self) -> None:  # pragma: no cover - UI callback
        self.canvas.refresh()
        self._render_3d()
        self.status_var.set("Vista ripristinata")

    def _render_3d(self) -> None:  # pragma: no cover - UI drawing
        self.ax.clear()
        dims = self.request.pallet.dimensions
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Y (mm)")
        self.ax.set_zlabel("Z (mm)")
        self.ax.set_xlim(0, dims.width)
        self.ax.set_ylim(0, dims.depth)
        max_height = max(
            (
                row.top
                for row in compute_height_report(self.request, self.plan, self.sequence)
            ),
            default=0.0,
        )
        self.ax.set_zlim(0, max_height + self.request.box.dimensions.height)

        layers: Sequence[LayerPlan]
        if self.sequence is not None:
            layers = self.sequence.layers
        else:
            layers = [self.plan]

        for layer in layers:
            for placement in layer.placements:
                self._draw_box(placement)
        for annotation in self._annotations:
            label_pos = self._restore_position(annotation.label_position)
            self.ax.scatter(
                label_pos.x,
                label_pos.y,
                label_pos.z,
                color="#e63946",
                s=12,
            )
            vector = annotation.approach_vector
            self.ax.quiver(
                label_pos.x,
                label_pos.y,
                label_pos.z,
                vector.x,
                vector.y,
                vector.z,
                color="#e63946",
                arrow_length_ratio=0.2,
            )
        self.canvas3d.draw()

    def _build_plan(self) -> tuple[LayerRequest, LayerPlan, LayerSequencePlan | None]:
        request = self._build_request()
        layers = max(1, int(self.layers_var.get() or 1))
        corners = [token.upper() for token in self.corners_var.get().split() if token]
        z_step = self._parse_float(self.z_step_var.get())
        interleaf = self._selected_interleaf()
        interleaf_frequency = max(1, int(self.interleaf_frequency_var.get() or 1))
        if layers > 1:
            sequence = self._sequence_planner.stack_layers(
                request,
                levels=layers,
                corners=corners or None,
                z_step=z_step,
                collision_checker=self._collision_checker,
                interleaf=interleaf,
                interleaf_frequency=interleaf_frequency,
            )
            plan = sequence.layers[0]
        else:
            sequence = None
            plan = self._layer_planner.plan_layer(request)
        direction, distance, overrides, custom_direction = self._resolve_approach_settings()
        label_offset = self._label_offset_value()
        self._annotator = PlacementAnnotator(
            default_approach=distance,
            label_offset=label_offset,
        )
        if sequence is not None:
            sequence.metadata["approach_distance"] = f"{distance:.2f}"
            if custom_direction:
                sequence.metadata["approach_direction"] = direction
            for layer in sequence.layers:
                layer_direction = direction if custom_direction else layer.start_corner.upper()
                apply_approach(layer, layer_direction, distance, overrides)
        else:
            apply_approach(plan, direction, distance, overrides)
        return request, plan, sequence

    def _build_request(self) -> LayerRequest:
        pallet = self._find_by_id(self.pallets, self.pallet_var.get(), "Pallet")
        box = self._find_by_id(self.boxes, self.box_var.get(), "Scatola")
        tool = self._find_by_id(self.tools, self.tool_var.get(), "Tool")
        return LayerRequest(
            pallet=pallet,
            box=box,
            tool=tool,
            start_corner=(self.corner_var.get() or "SW").upper(),
            reference_frame=self.reference_frame,
        )

    def _selected_interleaf(self) -> Interleaf | None:
        value = self.interleaf_var.get()
        if not value or value == self._NO_INTERLEAF_VALUE:
            return None
        return self._find_by_id(self.interleaves, value, "Interfalda")

    def _resolve_approach_settings(self) -> tuple[str, float, dict[str, ApproachConfig], bool]:
        raw_direction = (self.approach_direction_var.get() or "").strip().upper()
        custom_direction = bool(raw_direction)
        direction = raw_direction or (self.corner_var.get() or "SW").upper()
        distance = self._approach_distance_value()
        overrides = parse_approach_overrides(self.approach_override_var.get())
        return direction, distance, overrides, custom_direction

    def _approach_distance_value(self) -> float:
        value = self._parse_float(self.approach_distance_var.get())
        if value is None:
            value = self._default_approach_distance
        if value <= 0:
            raise ValueError("La distanza di accostamento deve essere positiva")
        return value

    def _label_offset_value(self) -> float:
        value = self._parse_float(self.label_offset_var.get())
        if value is None:
            return self._default_label_offset
        return value

    def _on_inputs_changed(self, *_):  # pragma: no cover - UI callback
        try:
            request, plan, sequence = self._build_plan()
        except ValueError as exc:
            self._messagebox.showerror("Impossibile calcolare lo strato", str(exc))
            return
        self.request = request
        self.plan = plan
        self.sequence = sequence
        self.canvas.request = request
        self.canvas.plan = plan
        self.canvas.refresh()
        self._refresh_annotations()
        self._refresh_metrics()
        self._render_3d()
        self.status_var.set(
            "Schema aggiornato per pallet {p} e scatola {b}".format(
                p=self.request.pallet.id,
                b=self.request.box.id,
            )
        )

    def _find_by_id(self, collection, item_id: str, label: str):
        for item in collection:
            if item.id == item_id:
                return item
        raise ValueError(f"{label} '{item_id}' non trovato")

    def _parse_float(self, raw: str | float | None) -> float | None:
        if raw is None:
            return None
        if isinstance(raw, float):
            return raw
        text = str(raw).strip()
        if not text:
            return None
        return float(text)

    def _draw_box(self, placement: LayerPlacement) -> None:  # pragma: no cover - UI drawing
        physical = self.request.reference_frame.restore(
            placement.position,
            pallet=self.request.pallet,
            overhang_x=self.request.overhang_x,
            overhang_y=self.request.overhang_y,
        )
        width, depth = _box_footprint(
            self.request.box.dimensions.width,
            self.request.box.dimensions.depth,
            placement.rotation,
        )
        height = self.request.box.dimensions.height
        x0 = physical.x - width / 2
        y0 = physical.y - depth / 2
        z0 = placement.position.z

        vertices = [
            (x0, y0, z0),
            (x0 + width, y0, z0),
            (x0 + width, y0 + depth, z0),
            (x0, y0 + depth, z0),
            (x0, y0, z0 + height),
            (x0 + width, y0, z0 + height),
            (x0 + width, y0 + depth, z0 + height),
            (x0, y0 + depth, z0 + height),
        ]
        faces = [
            [vertices[i] for i in [0, 1, 2, 3]],
            [vertices[i] for i in [4, 5, 6, 7]],
            [vertices[i] for i in [0, 1, 5, 4]],
            [vertices[i] for i in [1, 2, 6, 5]],
            [vertices[i] for i in [2, 3, 7, 6]],
            [vertices[i] for i in [3, 0, 4, 7]],
        ]
        color = _color_for_block(placement.block, placement.sequence_index)
        poly = self._Poly3DCollection(faces, facecolors=color, edgecolors="#111827", linewidths=0.5, alpha=0.6)
        self.ax.add_collection3d(poly)

    def _restore_position(self, point: Vector3) -> Vector3:
        return self.request.reference_frame.restore(
            point,
            pallet=self.request.pallet,
            overhang_x=self.request.overhang_x,
            overhang_y=self.request.overhang_y,
        )

    def _refresh_annotations(self) -> None:
        if not hasattr(self, "placement_tree"):
            return
        if self.plan.box is None:
            self._annotations = []
        else:
            self._annotations = self._annotator.annotate(self.plan)
        for child in self.placement_tree.get_children():
            self.placement_tree.delete(child)
        if not self._annotations:
            return
        for placement, annotation in zip(self.plan.placements, self._annotations):
            center = self._restore_position(placement.position)
            label_pos = self._restore_position(annotation.label_position)
            self.placement_tree.insert(
                "",
                "end",
                values=(
                    str(placement.sequence_index + 1),
                    placement.block or "-",
                    "x={:.1f} y={:.1f} z={:.1f}".format(center.x, center.y, center.z),
                    f"{placement.rotation}°",
                    "{dir} {dist:.1f}mm".format(
                        dir=annotation.approach_direction,
                        dist=annotation.approach_distance,
                    ),
                    "x={:.1f} y={:.1f} z={:.1f}".format(
                        label_pos.x,
                        label_pos.y,
                        label_pos.z,
                    ),
                ),
            )

    def _refresh_metrics(self) -> None:
        lines = build_metric_summary(self.plan, self.sequence)
        if not lines:
            self.metrics_var.set("Nessuna metrica disponibile")
        else:
            self.metrics_var.set("\n".join(f"{line.label}: {line.value}" for line in lines))

    def _active_plan(self) -> LayerPlan | LayerSequencePlan:
        return self.sequence if self.sequence is not None else self.plan

    def _export_json(self) -> None:  # pragma: no cover - UI callback
        filename = self._choose_export_path("json")
        if not filename:
            return
        path = Path(filename)
        target = self._active_plan()
        exporter = PlanExporter(base_path=path.parent)
        exporter.to_file(target, path.name)
        self._messagebox.showinfo("Export JSON", f"File salvato in {path}")
        self.status_var.set(f"JSON salvato in {path}")

    def _export_plc(self) -> None:  # pragma: no cover - UI callback
        filename = self._choose_export_path("s7")
        if not filename:
            return
        path = Path(filename)
        self._plc_exporter.to_file(self._active_plan(), path)
        self._messagebox.showinfo("Export PLC", f"File PLC salvato in {path}")
        self.status_var.set(f"PLC salvato in {path}")

    def _choose_export_path(self, extension: str) -> str | None:  # pragma: no cover - UI helper
        return self._filedialog.asksaveasfilename(
            defaultextension=f".{extension}",
            filetypes=[(extension.upper(), f"*.{extension}"), ("Tutti i file", "*.*")],
            title="Seleziona il file di destinazione",
        )


__all__ = [
    "PlacementGlyph",
    "LayerViewModel",
    "HeightRow",
    "MetricLine",
    "build_layer_view_model",
    "compute_height_report",
    "build_metric_summary",
    "PalletGuiApp",
]
