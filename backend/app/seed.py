import json
import sqlite3
from datetime import datetime, timezone

from app.config import DATA_DIR
from app.db import connect


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if not _has_column(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS datasets(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          fixture_path TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          note TEXT
        );
        CREATE TABLE IF NOT EXISTS rules(
          id INTEGER PRIMARY KEY,
          dataset_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          field TEXT NOT NULL,
          rule_type TEXT NOT NULL,
          severity TEXT NOT NULL,
          params_json TEXT NOT NULL DEFAULT '{}',
          enabled INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(dataset_id) REFERENCES datasets(id)
        );
        CREATE TABLE IF NOT EXISTS inspect_batches(
          id INTEGER PRIMARY KEY,
          dataset_id INTEGER NOT NULL,
          status TEXT NOT NULL,
          scanned_count INTEGER NOT NULL DEFAULT 0,
          passed_count INTEGER NOT NULL DEFAULT 0,
          failed_count INTEGER NOT NULL DEFAULT 0,
          quarantined_count INTEGER NOT NULL DEFAULT 0,
          released_count INTEGER NOT NULL DEFAULT 0,
          report_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          round_no INTEGER NOT NULL DEFAULT 1,
          reopened_from_id INTEGER,
          reopen_reason TEXT,
          reopened_at TEXT,
          FOREIGN KEY(dataset_id) REFERENCES datasets(id),
          FOREIGN KEY(reopened_from_id) REFERENCES inspect_batches(id)
        );
        CREATE TABLE IF NOT EXISTS inspect_rows(
          id INTEGER PRIMARY KEY,
          batch_id INTEGER NOT NULL,
          row_no INTEGER NOT NULL,
          entity_key TEXT,
          payload_json TEXT NOT NULL,
          disposition TEXT NOT NULL,
          rule_hits_json TEXT NOT NULL,
          round_no INTEGER NOT NULL DEFAULT 1,
          FOREIGN KEY(batch_id) REFERENCES inspect_batches(id)
        );
        CREATE TABLE IF NOT EXISTS quarantine(
          id INTEGER PRIMARY KEY,
          batch_id INTEGER NOT NULL,
          dataset_id INTEGER NOT NULL,
          row_no INTEGER NOT NULL,
          entity_key TEXT,
          reason TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          superseded_at TEXT,
          supersede_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS curated(
          id INTEGER PRIMARY KEY,
          dataset_id INTEGER NOT NULL,
          batch_id INTEGER NOT NULL,
          entity_key TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          released_at TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          invalidated_at TEXT,
          invalidate_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS batch_reopen_events(
          id INTEGER PRIMARY KEY,
          batch_id INTEGER NOT NULL,
          round_no INTEGER NOT NULL,
          reason TEXT NOT NULL,
          curated_withdrawn_count INTEGER NOT NULL DEFAULT 0,
          quarantine_superseded_count INTEGER NOT NULL DEFAULT 0,
          new_batch_id INTEGER,
          created_at TEXT NOT NULL,
          FOREIGN KEY(batch_id) REFERENCES inspect_batches(id),
          FOREIGN KEY(new_batch_id) REFERENCES inspect_batches(id)
        );
        """
    )
    # 迁移：为早期库补齐重开链路所需列
    _ensure_column(conn, "inspect_batches", "round_no", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "inspect_batches", "reopened_from_id", "INTEGER")
    _ensure_column(conn, "inspect_batches", "reopen_reason", "TEXT")
    _ensure_column(conn, "inspect_batches", "reopened_at", "TEXT")
    _ensure_column(conn, "inspect_rows", "round_no", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "quarantine", "active", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "quarantine", "superseded_at", "TEXT")
    _ensure_column(conn, "quarantine", "supersede_reason", "TEXT")
    _ensure_column(conn, "curated", "active", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(conn, "curated", "invalidated_at", "TEXT")
    _ensure_column(conn, "curated", "invalidate_reason", "TEXT")
    # 列补齐后再建依赖 active 列的索引（旧库迁移时表上原本没有这些列）
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_curated_active ON curated(active)"
    )
    # 同键同一时刻只允许一条有效（active=1）精选行；失效行保留审计，不参与唯一约束
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_curated_active_key "
        "ON curated(dataset_id, entity_key) WHERE active=1"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_quarantine_active ON quarantine(active)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_batches_reopened_from ON inspect_batches(reopened_from_id)"
    )
    # 早期库的 curated 带全表 UNIQUE(dataset_id, entity_key)，会阻止撤回行与新有效行共存；
    # 重建为仅约束 active=1 的部分唯一索引。
    schema_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='curated'"
    ).fetchone()["sql"]
    if "UNIQUE(dataset_id, entity_key)" in schema_sql or "UNIQUE (dataset_id, entity_key)" in schema_sql:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS curated_new(
              id INTEGER PRIMARY KEY,
              dataset_id INTEGER NOT NULL,
              batch_id INTEGER NOT NULL,
              entity_key TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              released_at TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              invalidated_at TEXT,
              invalidate_reason TEXT
            );
            INSERT INTO curated_new
              SELECT id, dataset_id, batch_id, entity_key, payload_json, released_at,
                     active, invalidated_at, invalidate_reason FROM curated;
            DROP TABLE curated;
            ALTER TABLE curated_new RENAME TO curated;
            CREATE UNIQUE INDEX ux_curated_active_key
              ON curated(dataset_id, entity_key) WHERE active=1;
            CREATE INDEX idx_curated_active ON curated(active);
            """
        )
    n = conn.execute("SELECT COUNT(*) AS c FROM datasets").fetchone()["c"]
    if n == 0:
        conn.execute(
            "INSERT INTO datasets(name, fixture_path, entity_type, enabled, note) VALUES (?,?,?,?,?)",
            ("Orders Snapshot", "orders_snapshot.jsonl", "order", 1, "含缺失与类型错误行，演示入检"),
        )
        conn.execute(
            "INSERT INTO datasets(name, fixture_path, entity_type, enabled, note) VALUES (?,?,?,?,?)",
            ("Inventory Snapshot", "inventory_snapshot.jsonl", "sku", 1, "库存快照第二路"),
        )
        conn.executemany(
            "INSERT INTO rules(dataset_id, name, field, rule_type, severity, params_json, enabled) VALUES (?,?,?,?,?,?,?)",
            [
                (1, "sku 必填", "sku", "required", "error", "{}", 1),
                (1, "price 须为数字", "price", "type_number", "error", "{}", 1),
                (1, "qty 须为整数", "qty", "type_int", "warn", "{}", 1),
                (2, "sku 必填", "sku", "required", "error", "{}", 1),
                (2, "on_hand 须为整数", "on_hand", "type_int", "error", "{}", 1),
            ],
        )
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?)",
            ("release_mode", "pass_only"),
        )
    conn.commit()
    conn.close()
