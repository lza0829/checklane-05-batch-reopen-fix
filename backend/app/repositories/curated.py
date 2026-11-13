from __future__ import annotations

import json
import sqlite3
from typing import Any


def upsert(
    conn: sqlite3.Connection,
    *,
    dataset_id: int,
    batch_id: int,
    entity_key: str,
    payload: dict[str, Any],
    released_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO curated(dataset_id, batch_id, entity_key, payload_json, released_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(dataset_id, entity_key) DO UPDATE SET
          batch_id=excluded.batch_id,
          payload_json=excluded.payload_json,
          released_at=excluded.released_at
        """,
        (dataset_id, batch_id, entity_key, json.dumps(payload, ensure_ascii=False), released_at),
    )


def list_all(conn: sqlite3.Connection, dataset_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    if dataset_id is None:
        rows = conn.execute(
            "SELECT id, dataset_id, batch_id, entity_key, payload_json, released_at FROM curated ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, dataset_id, batch_id, entity_key, payload_json, released_at FROM curated WHERE dataset_id=? ORDER BY id DESC LIMIT ?",
            (dataset_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json"))
        out.append(d)
    return out


def count_all(conn: sqlite3.Connection, dataset_id: int | None = None) -> int:
    if dataset_id is None:
        return int(conn.execute("SELECT COUNT(*) AS c FROM curated").fetchone()["c"])
    return int(
        conn.execute("SELECT COUNT(*) AS c FROM curated WHERE dataset_id=?", (dataset_id,)).fetchone()["c"]
    )
