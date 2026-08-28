from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from modules.supplies.models import (
    SupplementaryMaterial,
    SupplementaryMaterialCreate,
    SupplementaryMaterialUpdate,
)
from modules.supplies.seed import INITIAL_SUPPLEMENTARY_MATERIALS


class DuplicateSupplementaryMaterialError(ValueError):
    pass


class SupplementaryMaterialRepository:
    """SQLite repository for supplementary-material master data."""

    _SEED_VERSION = "2026-08-28-v1"

    def __init__(self, database_path: Path, *, seed_initial: bool = False) -> None:
        self.database_path = Path(database_path)
        self._lock = RLock()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
        if seed_initial:
            self._seed_initial_materials()

    def list(self, query: str | None = None) -> list[SupplementaryMaterial]:
        normalized_query = (query or "").strip()
        with self._lock, self._connect() as connection:
            if normalized_query:
                pattern = f"%{normalized_query}%"
                rows = connection.execute(
                    """
                    SELECT id, material_number, english_name, chinese_name, eid, created_at, updated_at
                    FROM supplementary_materials
                    WHERE material_number LIKE ? COLLATE NOCASE
                       OR english_name LIKE ? COLLATE NOCASE
                       OR chinese_name LIKE ? COLLATE NOCASE
                       OR eid LIKE ? COLLATE NOCASE
                    ORDER BY material_number COLLATE NOCASE ASC
                    """,
                    (pattern, pattern, pattern, pattern),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, material_number, english_name, chinese_name, eid, created_at, updated_at
                    FROM supplementary_materials
                    ORDER BY material_number COLLATE NOCASE ASC
                    """
                ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, material_id: str) -> SupplementaryMaterial | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, material_number, english_name, chinese_name, eid, created_at, updated_at
                FROM supplementary_materials WHERE id = ?
                """,
                (material_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def create(self, payload: SupplementaryMaterialCreate) -> SupplementaryMaterial:
        now = datetime.now(timezone.utc)
        material = SupplementaryMaterial(
            id=f"supply_{uuid4().hex[:12]}",
            **payload.model_dump(),
            created_at=now,
            updated_at=now,
        )
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO supplementary_materials
                        (id, material_number, english_name, chinese_name, eid, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._values(material),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateSupplementaryMaterialError(
                f"物料编号已存在: {material.material_number}"
            ) from exc
        return material

    def update(
        self,
        material_id: str,
        payload: SupplementaryMaterialUpdate,
    ) -> SupplementaryMaterial | None:
        changes = {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if value is not None
        }
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, material_number, english_name, chinese_name, eid, created_at, updated_at
                FROM supplementary_materials WHERE id = ?
                """,
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            current = self._from_row(row)
            updated = current.model_copy(update={**changes, "updated_at": datetime.now(timezone.utc)})
            try:
                connection.execute(
                    """
                    UPDATE supplementary_materials
                    SET material_number = ?, english_name = ?, chinese_name = ?, eid = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        updated.material_number,
                        updated.english_name,
                        updated.chinese_name,
                        updated.eid,
                        updated.updated_at.isoformat(),
                        material_id,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateSupplementaryMaterialError(
                    f"物料编号已存在: {updated.material_number}"
                ) from exc
        return updated

    def delete(self, material_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM supplementary_materials WHERE id = ?", (material_id,)
            )
        return cursor.rowcount > 0

    def _initialize_database(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS supplementary_materials (
                    id TEXT PRIMARY KEY,
                    material_number TEXT NOT NULL UNIQUE,
                    english_name TEXT NOT NULL DEFAULT '',
                    chinese_name TEXT NOT NULL DEFAULT '',
                    eid TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS supplementary_material_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def _seed_initial_materials(self) -> None:
        with self._lock, self._connect() as connection:
            seeded = connection.execute(
                "SELECT value FROM supplementary_material_meta WHERE key = 'seed_version'"
            ).fetchone()
            if seeded is not None:
                return
            now = datetime.now(timezone.utc).isoformat()
            for material_number, english_name, chinese_name, eid in INITIAL_SUPPLEMENTARY_MATERIALS:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO supplementary_materials
                        (id, material_number, english_name, chinese_name, eid, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"supply_{uuid4().hex[:12]}",
                        material_number,
                        english_name,
                        chinese_name,
                        eid,
                        now,
                        now,
                    ),
                )
            connection.execute(
                "INSERT INTO supplementary_material_meta (key, value) VALUES ('seed_version', ?)",
                (self._SEED_VERSION,),
            )

    @staticmethod
    def _values(material: SupplementaryMaterial) -> tuple[str, ...]:
        return (
            material.id,
            material.material_number,
            material.english_name,
            material.chinese_name,
            material.eid,
            material.created_at.isoformat(),
            material.updated_at.isoformat(),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> SupplementaryMaterial:
        return SupplementaryMaterial.model_validate(dict(row))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection
