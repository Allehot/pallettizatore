"""Simple relational repository backed by SQLite."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Box, Dimensions, Interleaf, Pallet, PickupOffset, Tool


class DataRepository:
    def __init__(self, db_path: str | Path = "verpal.db") -> None:
        self.db_path = Path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def initialize(self, seed_path: str | Path) -> None:
        seed = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pallets (
                    id TEXT PRIMARY KEY,
                    width REAL,
                    depth REAL,
                    height REAL,
                    max_overhang_x REAL,
                    max_overhang_y REAL
                );
                CREATE TABLE IF NOT EXISTS boxes (
                    id TEXT PRIMARY KEY,
                    width REAL,
                    depth REAL,
                    height REAL,
                    weight REAL,
                    label_position TEXT
                );
                CREATE TABLE IF NOT EXISTS tools (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    max_boxes INTEGER,
                    orientations TEXT,
                    offset_x REAL,
                    offset_y REAL,
                    offset_z REAL
                );
                CREATE TABLE IF NOT EXISTS interleaves (
                    id TEXT PRIMARY KEY,
                    thickness REAL,
                    weight REAL,
                    material TEXT
                );
                """
            )
        if self._is_populated("pallets"):
            return
        with self.connection:
            self.connection.executemany(
                "INSERT OR REPLACE INTO pallets VALUES (:id,:width,:depth,:height,:max_overhang_x,:max_overhang_y)",
                seed["pallets"],
            )
            self.connection.executemany(
                "INSERT OR REPLACE INTO boxes VALUES (:id,:width,:depth,:height,:weight,:label_position)",
                seed["boxes"],
            )
            self.connection.executemany(
                "INSERT OR REPLACE INTO tools VALUES (:id,:name,:max_boxes,:orientations,:offset_x,:offset_y,:offset_z)",
                seed["tools"],
            )
            self.connection.executemany(
                "INSERT OR REPLACE INTO interleaves VALUES (:id,:thickness,:weight,:material)",
                seed.get("interleaves", []),
            )

    def _is_populated(self, table: str) -> bool:
        cur = self.connection.execute(f"SELECT COUNT(1) FROM {table}")
        return cur.fetchone()[0] > 0

    def get_pallet(self, pallet_id: str) -> Pallet:
        row = self.connection.execute("SELECT * FROM pallets WHERE id=?", (pallet_id,)).fetchone()
        if row is None:
            raise KeyError(f"Pallet {pallet_id} not found")
        return Pallet(
            id=row["id"],
            dimensions=Dimensions(row["width"], row["depth"], row["height"]),
            max_overhang_x=row["max_overhang_x"],
            max_overhang_y=row["max_overhang_y"],
        )

    def list_pallets(self) -> list[Pallet]:
        rows = self.connection.execute("SELECT * FROM pallets ORDER BY id").fetchall()
        return [
            Pallet(
                id=row["id"],
                dimensions=Dimensions(row["width"], row["depth"], row["height"]),
                max_overhang_x=row["max_overhang_x"],
                max_overhang_y=row["max_overhang_y"],
            )
            for row in rows
        ]

    def get_box(self, box_id: str) -> Box:
        row = self.connection.execute("SELECT * FROM boxes WHERE id=?", (box_id,)).fetchone()
        if row is None:
            raise KeyError(f"Box {box_id} not found")
        return Box(
            id=row["id"],
            dimensions=Dimensions(row["width"], row["depth"], row["height"]),
            weight=row["weight"],
            label_position=row["label_position"],
        )

    def list_boxes(self) -> list[Box]:
        rows = self.connection.execute("SELECT * FROM boxes ORDER BY id").fetchall()
        return [
            Box(
                id=row["id"],
                dimensions=Dimensions(row["width"], row["depth"], row["height"]),
                weight=row["weight"],
                label_position=row["label_position"],
            )
            for row in rows
        ]

    def get_tool(self, tool_id: str) -> Tool:
        row = self.connection.execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()
        if row is None:
            raise KeyError(f"Tool {tool_id} not found")
        orientations = [int(value) for value in row["orientations"].split(",") if value]
        return Tool(
            id=row["id"],
            name=row["name"],
            max_boxes=row["max_boxes"],
            allowed_orientations=orientations,
            pickup_offset=PickupOffset(row["offset_x"], row["offset_y"], row["offset_z"]),
        )

    def list_tools(self) -> list[Tool]:
        rows = self.connection.execute("SELECT * FROM tools ORDER BY id").fetchall()
        return [
            Tool(
                id=row["id"],
                name=row["name"],
                max_boxes=row["max_boxes"],
                allowed_orientations=[
                    int(value) for value in row["orientations"].split(",") if value
                ],
                pickup_offset=PickupOffset(row["offset_x"], row["offset_y"], row["offset_z"]),
            )
            for row in rows
        ]

    def get_interleaf(self, interleaf_id: str) -> Interleaf:
        row = self.connection.execute("SELECT * FROM interleaves WHERE id=?", (interleaf_id,)).fetchone()
        if row is None:
            raise KeyError(f"Interleaf {interleaf_id} not found")
        return Interleaf(
            id=row["id"],
            thickness=row["thickness"],
            weight=row["weight"],
            material=row["material"],
        )

    def list_interleaves(self) -> list[Interleaf]:
        rows = self.connection.execute("SELECT * FROM interleaves ORDER BY id").fetchall()
        return [
            Interleaf(
                id=row["id"],
                thickness=row["thickness"],
                weight=row["weight"],
                material=row["material"],
            )
            for row in rows
        ]

    def close(self) -> None:
        self.connection.close()
