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
    """签发一行到精选区。

    同 (dataset_id, entity_key) 已存在 **有效** 行（active=1）时覆盖为最新结果；
    若历史行已被重开撤回（active=0），则插入一条新的有效行，撤回行原样保留作审计。
    唯一性由部分索引 ``ux_curated_active_key`` 保证：同键同时刻只有一条 active 行。
    """
    conn.execute(
        """
        INSERT INTO curated(dataset_id, batch_id, entity_key, payload_json, released_at, active)
        VALUES (?,?,?,?,?,1)
        ON CONFLICT(dataset_id, entity_key) WHERE active=1 DO UPDATE SET
          batch_id=excluded.batch_id,
          payload_json=excluded.payload_json,
          released_at=excluded.released_at
        """,
        (dataset_id, batch_id, entity_key, json.dumps(payload, ensure_ascii=False), released_at),
    )


def withdraw_batch(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    reason: str,
    invalidated_at: str,
) -> int:
    """撤回指定批次写入精选区且仍有效的行（标记失效，不物理删除）。返回撤回条数。"""
    cur = conn.execute(
        """
        UPDATE curated
        SET active=0, invalidated_at=?, invalidate_reason=?
        WHERE batch_id=? AND active=1
        """,
        (invalidated_at, reason, batch_id),
    )
    return int(cur.rowcount or 0)


def list_all(conn: sqlite3.Connection, dataset_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """精选区存量口径：只返回 active=1 的有效行。"""
    if dataset_id is None:
        rows = conn.execute(
            """
            SELECT id, dataset_id, batch_id, entity_key, payload_json, released_at,
                   active, invalidated_at, invalidate_reason
            FROM curated WHERE active=1 ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, dataset_id, batch_id, entity_key, payload_json, released_at,
                   active, invalidated_at, invalidate_reason
            FROM curated WHERE active=1 AND dataset_id=? ORDER BY id DESC LIMIT ?
            """,
            (dataset_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json"))
        out.append(d)
    return out


def list_withdrawn(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    """重开撤回审计：返回被标记失效的历史行（解释精选区为何变少）。"""
    rows = conn.execute(
        """
        SELECT id, dataset_id, batch_id, entity_key, payload_json, released_at,
               active, invalidated_at, invalidate_reason
        FROM curated WHERE active=0 ORDER BY invalidated_at DESC, id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json"))
        out.append(d)
    return out


def count_all(conn: sqlite3.Connection, dataset_id: int | None = None) -> int:
    """精选区存量计数口径：仅统计 active=1。"""
    if dataset_id is None:
        return int(conn.execute("SELECT COUNT(*) AS c FROM curated WHERE active=1").fetchone()["c"])
    return int(
        conn.execute(
            "SELECT COUNT(*) AS c FROM curated WHERE active=1 AND dataset_id=?", (dataset_id,)
        ).fetchone()["c"]
    )
