from __future__ import annotations

import sqlite3
from typing import Any


def list_rules(conn: sqlite3.Connection, dataset_id: int | None = None) -> list[dict[str, Any]]:
    if dataset_id is None:
        rows = conn.execute(
            "SELECT id, dataset_id, name, field, rule_type, severity, params_json, enabled FROM rules ORDER BY id"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, dataset_id, name, field, rule_type, severity, params_json, enabled "
            "FROM rules WHERE dataset_id=? ORDER BY id",
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_enabled(conn: sqlite3.Connection, rule_id: int, enabled: bool) -> None:
    conn.execute("UPDATE rules SET enabled=? WHERE id=?", (1 if enabled else 0, rule_id))
