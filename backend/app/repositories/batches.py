from __future__ import annotations

import json
import sqlite3
from typing import Any


def insert_batch(
    conn: sqlite3.Connection,
    *,
    dataset_id: int,
    status: str,
    scanned: int,
    passed: int,
    failed: int,
    quarantined: int,
    released: int,
    report: dict[str, Any],
    created_at: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO inspect_batches(
          dataset_id, status, scanned_count, passed_count, failed_count,
          quarantined_count, released_count, report_json, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            dataset_id,
            status,
            scanned,
            passed,
            failed,
            quarantined,
            released,
            json.dumps(report, ensure_ascii=False),
            created_at,
        ),
    )
    return int(cur.lastrowid)


def insert_row(
    conn: sqlite3.Connection,
    *,
    batch_id: int,
    row_no: int,
    entity_key: str | None,
    payload: dict[str, Any],
    disposition: str,
    rule_hits: list[dict[str, Any]],
) -> None:
    conn.execute(
        """
        INSERT INTO inspect_rows(batch_id, row_no, entity_key, payload_json, disposition, rule_hits_json)
        VALUES (?,?,?,?,?,?)
        """,
        (
            batch_id,
            row_no,
            entity_key,
            json.dumps(payload, ensure_ascii=False),
            disposition,
            json.dumps(rule_hits, ensure_ascii=False),
        ),
    )


def list_batches(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, dataset_id, status, scanned_count, passed_count, failed_count,
               quarantined_count, released_count, report_json, created_at
        FROM inspect_batches ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["report"] = json.loads(d.pop("report_json"))
        out.append(d)
    return out


def get_batch(conn: sqlite3.Connection, batch_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, dataset_id, status, scanned_count, passed_count, failed_count,
               quarantined_count, released_count, report_json, created_at
        FROM inspect_batches WHERE id=?
        """,
        (batch_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["report"] = json.loads(d.pop("report_json"))
    return d


def list_batch_rows(conn: sqlite3.Connection, batch_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, batch_id, row_no, entity_key, payload_json, disposition, rule_hits_json
        FROM inspect_rows WHERE batch_id=? ORDER BY row_no
        """,
        (batch_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json"))
        d["rule_hits"] = json.loads(d.pop("rule_hits_json"))
        out.append(d)
    return out
