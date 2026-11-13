from __future__ import annotations

import sqlite3
from typing import Any


def insert_event(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    round_no: int,
    reason: str,
    curated_withdrawn_count: int,
    quarantine_superseded_count: int,
    new_batch_id: int | None,
    created_at: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO batch_reopen_events(
          batch_id, round_no, reason, curated_withdrawn_count,
          quarantine_superseded_count, new_batch_id, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            batch_id,
            round_no,
            reason,
            curated_withdrawn_count,
            quarantine_superseded_count,
            new_batch_id,
            created_at,
        ),
    )
    return int(cur.lastrowid)


def list_for_batch(conn: sqlite3.Connection, batch_id: int) -> list[dict[str, Any]]:
    """某一批次（或其重开链）上的重开事件，按时间正序便于审计。"""
    rows = conn.execute(
        """
        SELECT e.id, e.batch_id, e.round_no, e.reason, e.curated_withdrawn_count,
               e.quarantine_superseded_count, e.new_batch_id, e.created_at
        FROM batch_reopen_events e
        WHERE e.batch_id=? OR e.new_batch_id=?
        ORDER BY e.id
        """,
        (batch_id, batch_id),
    ).fetchall()
    return [dict(r) for r in rows]


def list_all(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, batch_id, round_no, reason, curated_withdrawn_count,
               quarantine_superseded_count, new_batch_id, created_at
        FROM batch_reopen_events ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_all(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS c FROM batch_reopen_events").fetchone()["c"])
