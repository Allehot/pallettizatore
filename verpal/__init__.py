"""VerPal palletization planning toolkit."""

from .annotations import PlacementAnnotation, PlacementAnnotator
from .models import (
    Box,
    Dimensions,
    ApproachConfig,
    LayerPlacement,
    LayerPlan,
    LayerRequest,
    LayerSequencePlan,
    OrientationMode,
    Pallet,
    PickupOffset,
    ReferenceFrame,
    Tool,
    Vector3,
)
from .planner import RecursiveFiveBlockPlanner
from .repository import DataRepository
from .collisions import CollisionChecker
from .snap import SnapPointGenerator
from .exporter import PlanExporter
from .sequence import LayerSequencePlanner
from .project import PalletProject, ProjectArchiver
from .metrics import (
    LayerMetrics,
    SequenceMetrics,
    compute_layer_metrics,
    compute_sequence_metrics,
)
from .gui import (
    HeightRow,
    LayerViewModel,
    PalletGuiApp,
    PlacementGlyph,
    build_layer_view_model,
    compute_height_report,
)

__all__ = [
    "ApproachConfig",
    "Box",
    "Dimensions",
    "LayerPlacement",
    "LayerPlan",
    "LayerRequest",
    "LayerSequencePlan",
    "OrientationMode",
    "Pallet",
    "PickupOffset",
    "Tool",
    "ReferenceFrame",
    "Vector3",
    "RecursiveFiveBlockPlanner",
    "LayerSequencePlanner",
    "DataRepository",
    "CollisionChecker",
    "SnapPointGenerator",
    "PlanExporter",
    "ProjectArchiver",
    "PalletProject",
    "LayerMetrics",
    "SequenceMetrics",
    "compute_layer_metrics",
    "compute_sequence_metrics",
    "PlacementAnnotator",
    "PlacementAnnotation",
    "PalletGuiApp",
    "LayerViewModel",
    "PlacementGlyph",
    "HeightRow",
    "build_layer_view_model",
    "compute_height_report",
]
