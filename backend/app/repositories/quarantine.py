from __future__ import annotations

import json
import sqlite3
from typing import Any


def insert(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    dataset_id: int,
    row_no: int,
    entity_key: str | None,
    reason: str,
    payload: dict[str, Any],
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO quarantine(batch_id, dataset_id, row_no, entity_key, reason, payload_json, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (batch_id, dataset_id, row_no, entity_key, reason, json.dumps(payload, ensure_ascii=False), created_at),
    )


def list_all(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, batch_id, dataset_id, row_no, entity_key, reason, payload_json, created_at
        FROM quarantine ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json"))
        out.append(d)
    return out


def count_all(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS c FROM quarantine").fetchone()["c"])
