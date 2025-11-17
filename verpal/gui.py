"""Graphical interface helpers for VerPal."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .models import LayerPlan, LayerPlacement, LayerRequest, LayerSequencePlan, Vector3


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


def _import_tk() -> tuple[object, object, object]:  # pragma: no cover - runtime import
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Tkinter non disponibile. Installa il pacchetto python3-tk per usare l'interfaccia grafica."
        ) from exc
    return tk, messagebox, ttk


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
    """Tkinter GUI that visualizes the layer and 3D model."""

    def __init__(
        self,
        plan: LayerPlan,
        request: LayerRequest,
        *,
        sequence: LayerSequencePlan | None = None,
    ) -> None:
        self.plan = plan
        self.request = request
        self.sequence = sequence
        tk_module, messagebox, ttk = _import_tk()
        Figure, FigureCanvasTkAgg, Poly3DCollection = _import_matplotlib()
        self._messagebox = messagebox
        self._FigureCanvasTkAgg = FigureCanvasTkAgg
        self._Figure = Figure
        self._Poly3DCollection = Poly3DCollection
        DragCanvas = _build_canvas_class(tk_module)

        self.root = tk_module.Tk()
        self.root.title("VerPal - Configuratore Grafico")
        self.root.geometry("1200x640")
        self.root.minsize(960, 520)

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
            height=600,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(left)
        controls.grid(row=1, column=0, sticky="ew", pady=4)
        controls.columnconfigure(0, weight=1)
        ttk.Button(controls, text="Calcola quote", command=self._show_heights).grid(row=0, column=0, padx=4)
        ttk.Button(controls, text="Reset vista", command=self._reset_view).grid(row=0, column=1, padx=4)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.figure = self._Figure(figsize=(4, 4))
        self.ax = self.figure.add_subplot(111, projection="3d")
        self.canvas3d = self._FigureCanvasTkAgg(self.figure, master=right)
        self.canvas3d.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self.status_var = tk_module.StringVar()
        self.status_var.set("Trascina le scatole per riposizionarle.")
        ttk.Label(main, textvariable=self.status_var, anchor="w").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=2,
        )

        self._render_3d()

    def run(self) -> None:  # pragma: no cover - UI loop
        self.root.mainloop()

    def _on_canvas_change(self, _plan: LayerPlan) -> None:  # pragma: no cover - UI callback
        self.canvas.refresh()
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
        max_height = max((row.top for row in compute_height_report(self.request, self.plan, self.sequence)), default=0.0)
        self.ax.set_zlim(0, max_height + self.request.box.dimensions.height)

        layers: Sequence[LayerPlan]
        if self.sequence is not None:
            layers = self.sequence.layers
        else:
            layers = [self.plan]

        for layer in layers:
            for placement in layer.placements:
                self._draw_box(placement)
        self.canvas3d.draw()

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


__all__ = [
    "PlacementGlyph",
    "LayerViewModel",
    "HeightRow",
    "build_layer_view_model",
    "compute_height_report",
    "PalletGuiApp",
]
