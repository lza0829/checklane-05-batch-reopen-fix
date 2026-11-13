from __future__ import annotations

import json
from typing import Any

from app.config import FIXTURES_DIR
from app.db import connect
from app.engines.parse_fixture import parse_jsonl
from app.engines.rule_engine import decide_disposition, evaluate_row
from app.modules.batch_reopen_fix import REOPENED_STATUS, ReopenError, next_round_info
from app.repositories import batches as batch_repo
from app.repositories import curated as curated_repo
from app.repositories import datasets as dataset_repo
from app.repositories import quarantine as quarantine_repo
from app.repositories import reopen_events as events_repo
from app.repositories import rules as rules_repo
from app.seed import _now


def run_inspect(
    dataset_id: int,
    *,
    reopen_from_batch_id: int | None = None,
) -> dict[str, Any]:
    """执行一次入检。

    常规入检：``reopen_from_batch_id=None``，生成第 1 轮新批次。
    重开再入检：传入已处于 ``reopened`` 态的批次 id，沿其重开链生成 **新批次、
    新一轮**（``round_no`` 递增、``reopened_from_id`` 指回上一轮），新结果独立可核对；
    已撤回行不会被当作仍在精选区——精选区只统计 active=1，同键新一轮签发会整行覆盖。
    """
    conn = connect()
    try:
        ds = dataset_repo.get_dataset(conn, dataset_id)
        if not ds:
            raise ValueError(f"dataset {dataset_id} not found")
        if not ds["enabled"]:
            raise ValueError(f"dataset {dataset_id} disabled")

        round_no = 1
        reopened_from_id: int | None = None
        source_reopen_reason: str | None = None
        if reopen_from_batch_id is not None:
            source = batch_repo.get_batch(conn, reopen_from_batch_id)
            if source is None:
                raise ReopenError(f"batch {reopen_from_batch_id} not found")
            if source["dataset_id"] != dataset_id:
                raise ReopenError(
                    f"dataset 不匹配：批次 #{reopen_from_batch_id} 属于数据集 "
                    f"{source['dataset_id']}，请求的是 {dataset_id}"
                )
            if source["status"] != REOPENED_STATUS:
                raise ReopenError(
                    f"batch {reopen_from_batch_id} status={source['status']}，"
                    f"仅 {REOPENED_STATUS} 态批次可再入检"
                )
            round_no, reopened_from_id, source_reopen_reason = next_round_info(
                conn, reopen_from_batch_id
            )

        path = FIXTURES_DIR / ds["fixture_path"]
        rows = parse_jsonl(path)
        rules = [r for r in rules_repo.list_rules(conn, dataset_id) if r.get("enabled")]

        scanned = len(rows)
        passed = failed = quarantined = released = 0
        row_results: list[dict[str, Any]] = []
        now = _now()

        for idx, payload in enumerate(rows, start=1):
            hits = evaluate_row(payload, rules)
            disposition = decide_disposition(hits)
            entity_key = str(payload.get("entity_key") or "") or None
            if disposition == "quarantine":
                quarantined += 1
                failed += 1
            else:
                passed += 1
            row_results.append(
                {
                    "row_no": idx,
                    "entity_key": entity_key,
                    "payload": payload,
                    "disposition": disposition,
                    "rule_hits": hits,
                }
            )

        checks = [
            {
                "name": "scan_breakdown",
                "ok": scanned == passed + quarantined,
                "detail": f"scanned({scanned}) = passed({passed}) + quarantined({quarantined})",
            }
        ]

        report: dict[str, Any] = {
            "dataset_id": dataset_id,
            "dataset_name": ds["name"],
            "fixture_path": ds["fixture_path"],
            "rule_count": len(rules),
            "round_no": round_no,
            "reopened_from_id": reopened_from_id,
            "counts": {
                "scanned": scanned,
                "passed": passed,
                "failed": failed,
                "quarantined": quarantined,
                "released": 0,
            },
            "checks": checks,
        }
        if source_reopen_reason is not None:
            report["reopen_reason"] = source_reopen_reason

        batch_id = batch_repo.insert_batch(
            conn,
            dataset_id=dataset_id,
            status="inspected",
            scanned=scanned,
            passed=passed,
            failed=failed,
            quarantined=quarantined,
            released=0,
            report=report,
            created_at=now,
            round_no=round_no,
            reopened_from_id=reopened_from_id,
            reopen_reason=source_reopen_reason,
            reopened_at=now if reopened_from_id is not None else None,
        )

        for item in row_results:
            batch_repo.insert_row(
                conn,
                batch_id=batch_id,
                row_no=item["row_no"],
                entity_key=item["entity_key"],
                payload=item["payload"],
                disposition=item["disposition"],
                rule_hits=item["rule_hits"],
                round_no=round_no,
            )
            if item["disposition"] == "quarantine":
                reasons = "; ".join(
                    f"{h['name']}:{h['detail']}" for h in item["rule_hits"] if h.get("severity") == "error"
                )
                quarantine_repo.insert(
                    conn,
                    batch_id=batch_id,
                    dataset_id=dataset_id,
                    row_no=item["row_no"],
                    entity_key=item["entity_key"],
                    reason=reasons or "rule hit",
                    payload=item["payload"],
                    created_at=now,
                )
            else:
                # pass rows auto-release to curated (base chain)
                key = item["entity_key"] or f"row-{item['row_no']}"
                curated_repo.upsert(
                    conn,
                    dataset_id=dataset_id,
                    batch_id=batch_id,
                    entity_key=key,
                    payload=item["payload"],
                    released_at=now,
                )
                released += 1

        report["counts"]["released"] = released
        report["checks"].append(
            {
                "name": "release_matches_passed",
                "ok": released == passed,
                "detail": f"released({released}) = passed({passed})",
            }
        )
        report["checks"].append(
            {
                "name": "quarantine_table_matches",
                "ok": quarantine_repo.count_all(conn) >= quarantined,
                "detail": "quarantine rows persisted for this and prior batches (active only)",
            }
        )

        if reopened_from_id is not None:
            # 再入检互证：本轮签发条数必须能在精选区按本批次 active=1 找到对应行
            curated_from_this = conn.execute(
                "SELECT COUNT(*) AS c FROM curated WHERE batch_id=? AND active=1",
                (batch_id,),
            ).fetchone()["c"]
            report["checks"].append(
                {
                    "name": "reopen_round_curated_traceable",
                    "ok": curated_from_this == released,
                    "detail": (
                        f"第{round_no}轮批次 #{batch_id} 签发 {released} 行，"
                        f"精选区中本批 active 行 {curated_from_this} 行；"
                        f"上一轮撤回行 active=0 不计入存量"
                    ),
                }
            )

        conn.execute(
            """
            UPDATE inspect_batches
            SET released_count=?, report_json=?, status=?
            WHERE id=?
            """,
            (released, json.dumps(report, ensure_ascii=False), "released" if released else "inspected", batch_id),
        )

        if reopened_from_id is not None:
            # 回填重开审计事件的新批次 id，串起重开 → 再入检链路
            conn.execute(
                "UPDATE batch_reopen_events SET new_batch_id=? WHERE batch_id=? AND new_batch_id IS NULL",
                (batch_id, reopened_from_id),
            )

        conn.commit()

        detail = batch_repo.get_batch(conn, batch_id)
        assert detail is not None
        detail["rows"] = batch_repo.list_batch_rows(conn, batch_id)
        detail["reopen_events"] = events_repo.list_for_batch(conn, batch_id)
        detail["curated_total"] = curated_repo.count_all(conn, dataset_id)
        detail["quarantine_total"] = quarantine_repo.count_all(conn)
        return detail
    finally:
        conn.close()


def dashboard_stats() -> dict[str, Any]:
    conn = connect()
    try:
        datasets = conn.execute("SELECT COUNT(*) AS c FROM datasets").fetchone()["c"]
        rules = conn.execute("SELECT COUNT(*) AS c FROM rules WHERE enabled=1").fetchone()["c"]
        batches = conn.execute("SELECT COUNT(*) AS c FROM inspect_batches").fetchone()["c"]
        return {
            "dataset_count": datasets,
            "enabled_rule_count": rules,
            "batch_count": batches,
            "curated_count": curated_repo.count_all(conn),
            "quarantine_count": quarantine_repo.count_all(conn),
        }
    finally:
        conn.close()
