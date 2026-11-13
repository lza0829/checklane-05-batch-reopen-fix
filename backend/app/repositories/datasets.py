from __future__ import annotations

import sqlite3
from typing import Any


def list_datasets(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, fixture_path, entity_type, enabled, note FROM datasets ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_dataset(conn: sqlite3.Connection, dataset_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, name, fixture_path, entity_type, enabled, note FROM datasets WHERE id=?",
        (dataset_id,),
    ).fetchone()
    return dict(row) if row else None
