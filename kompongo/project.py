"""Project archiving utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile, BadZipFile

from .exporter import PlanExporter
from .models import Box, Dimensions, LayerPlan, LayerSequencePlan, Pallet, Tool


@dataclass
class PalletProject:
    """Serializable container with metadata and payload for a pallet project."""

    name: str
    plan_type: str
    pallet: dict[str, Any]
    box: dict[str, Any]
    tool: dict[str, Any]
    summary: dict[str, Any]
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    plan_payload: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "plan_type": self.plan_type,
            "pallet": self.pallet,
            "box": self.box,
            "tool": self.tool,
            "summary": self.summary,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], payload: str) -> "PalletProject":
        return cls(
            name=data["name"],
            plan_type=data["plan_type"],
            pallet=data["pallet"],
            box=data["box"],
            tool=data["tool"],
            summary=data.get("summary", {}),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            plan_payload=payload,
        )

    def plan_data(self) -> dict[str, Any]:
        """Return the JSON payload as dictionary."""
        return json.loads(self.plan_payload)


class ProjectArchiver:
    """Create and restore KomPonGo project archives."""

    def __init__(self, exporter: PlanExporter | None = None) -> None:
        self.exporter = exporter or PlanExporter()

    def build(
        self,
        *,
        name: str,
        plan: LayerPlan | LayerSequencePlan,
        pallet: Pallet,
        box: Box,
        tool: Tool,
        metadata: dict[str, str] | None = None,
    ) -> PalletProject:
        payload = self.exporter.to_payload(plan).decode("utf-8")
        plan_type = "sequence" if isinstance(plan, LayerSequencePlan) else "layer"
        summary = self._summary(plan)
        project = PalletProject(
            name=name,
            plan_type=plan_type,
            pallet=self._pallet_payload(pallet),
            box=self._box_payload(box),
            tool=self._tool_payload(tool),
            summary=summary,
            metadata=metadata or {},
            plan_payload=payload,
        )
        return project

    def save(self, project: PalletProject, target: str | Path) -> Path:
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(path, "w") as archive:
            archive.writestr("metadata.json", json.dumps(project.to_dict(), indent=2))
            archive.writestr("plan.json", project.plan_payload)
        return path

    def load(self, archive_path: str | Path) -> PalletProject:
        try:
            with ZipFile(archive_path, "r") as archive:
                metadata = json.loads(archive.read("metadata.json").decode("utf-8"))
                payload = archive.read("plan.json").decode("utf-8")
        except (FileNotFoundError, KeyError, BadZipFile) as exc:
            raise ValueError(f"Archivio non valido: {archive_path}") from exc
        return PalletProject.from_dict(metadata, payload)

    def _summary(self, plan: LayerPlan | LayerSequencePlan) -> dict[str, Any]:
        if isinstance(plan, LayerSequencePlan):
            return {
                "layers": plan.levels(),
                "total_boxes": plan.total_boxes(),
                "max_height_mm": round(plan.max_height(), 3),
            }
        placements = plan.placements
        max_height = max((placement.position.z for placement in placements), default=0.0)
        return {
            "layers": 1,
            "total_boxes": len(placements),
            "max_height_mm": round(max_height, 3),
        }

    def _pallet_payload(self, pallet: Pallet) -> dict[str, Any]:
        return {
            "id": pallet.id,
            "dimensions": self._dimensions_payload(pallet.dimensions),
            "max_overhang_x": pallet.max_overhang_x,
            "max_overhang_y": pallet.max_overhang_y,
        }

    def _box_payload(self, box: Box) -> dict[str, Any]:
        return {
            "id": box.id,
            "dimensions": self._dimensions_payload(box.dimensions),
            "weight": box.weight,
            "label_position": box.label_position,
        }

    def _tool_payload(self, tool: Tool) -> dict[str, Any]:
        return {
            "id": tool.id,
            "name": tool.name,
            "max_boxes": tool.max_boxes,
            "allowed_orientations": list(tool.allowed_orientations),
            "pickup_offset": {
                "x": tool.pickup_offset.x,
                "y": tool.pickup_offset.y,
                "z": tool.pickup_offset.z,
            },
        }

    def _dimensions_payload(self, dimensions: Dimensions) -> dict[str, Any]:
        return {
            "width": dimensions.width,
            "depth": dimensions.depth,
            "height": dimensions.height,
        }
