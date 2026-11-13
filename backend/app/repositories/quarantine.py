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
        INSERT INTO quarantine(batch_id, dataset_id, row_no, entity_key, reason, payload_json, created_at, active)
        VALUES (?,?,?,?,?,?,?,1)
        """,
        (batch_id, dataset_id, row_no, entity_key, reason, json.dumps(payload, ensure_ascii=False), created_at),
    )


def supersede_batch(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    reason: str,
    superseded_at: str,
) -> int:
    """批次重开时，将该批写入隔离区且仍有效的行标记失效。返回条数。

    再入检会按新一轮结果重新落隔离区；旧行保留可审计，不再计入隔离区存量。
    """
    cur = conn.execute(
        """
        UPDATE quarantine
        SET active=0, superseded_at=?, supersede_reason=?
        WHERE batch_id=? AND active=1
        """,
        (superseded_at, reason, batch_id),
    )
    return int(cur.rowcount or 0)


def list_all(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    """隔离区存量口径：只返回 active=1 的有效行。"""
    rows = conn.execute(
        """
        SELECT id, batch_id, dataset_id, row_no, entity_key, reason, payload_json,
               created_at, active, superseded_at, supersede_reason
        FROM quarantine WHERE active=1 ORDER BY id DESC LIMIT ?
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
    return int(conn.execute("SELECT COUNT(*) AS c FROM quarantine WHERE active=1").fetchone()["c"])
