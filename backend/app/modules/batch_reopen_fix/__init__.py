"""批次重开修复（batch_reopen_fix）

口径约定：
- 仅 ``released``（已签发）或 ``completed``（已完成）批次允许重开；未签发批次
  （``inspected`` / ``reopened`` 等）重开一律拒绝。
- 重开后原批次进入 ``reopened``（可修复态），其写入精选区的行 **标记失效**
  （``curated.active=0``，不物理删除，保留撤回原因与时间作为审计），其隔离区
  行同步标记失效；重开原因与撤回条数写入 ``batch_reopen_events``。
- 再入检采用 **新批次新一轮** 口径：重开链上每轮生成一个新批次（``round_no``
  递增、``reopened_from_id`` 指向上一轮批次），产生可独立核对的新结果；已撤回
  行不会假装仍在精选区——精选区存量只统计 ``active=1``。
"""

from __future__ import annotations

import json
from typing import Any

from app.db import connect
from app.repositories import batches as batch_repo
from app.repositories import curated as curated_repo
from app.repositories import quarantine as quarantine_repo
from app.repositories import reopen_events as events_repo
from app.seed import _now

# 允许重开的批次状态：已签发 / 已完成
REOPENABLE_STATUSES = ("released", "completed")
# 重开后批次所处的可修复态
REOPENED_STATUS = "reopened"


class ReopenError(ValueError):
    """重开请求不合法（批次不存在 / 状态不允许）。"""


def reopen_batch(batch_id: int, reason: str) -> dict[str, Any]:
    """重开一个已签发（或已完成）批次。

    步骤（单事务）：
    1. 校验批次存在且状态在 ``REOPENABLE_STATUSES`` 内；
    2. 撤回该批写入精选区且仍有效的行（标记失效），记录撤回条数；
    3. 同步失效该批写入隔离区且仍有效的行；
    4. 批次置为 ``reopened``，报告追加重开记录；
    5. 写 ``batch_reopen_events`` 审计事件。
    """
    reason = (reason or "").strip()
    if not reason:
        raise ReopenError("reopen reason is required")

    conn = connect()
    try:
        batch = batch_repo.get_batch(conn, batch_id)
        if batch is None:
            raise ReopenError(f"batch {batch_id} not found")
        if batch["status"] not in REOPENABLE_STATUSES:
            raise ReopenError(
                f"batch {batch_id} status={batch['status']} 不可重开；"
                f"仅 {'/'.join(REOPENABLE_STATUSES)} 批次允许重开"
            )

        now = _now()
        audit_reason = f"批次 #{batch_id} 重开撤回：{reason}"

        withdrawn = curated_repo.withdraw_batch(
            conn, batch_id=batch_id, reason=audit_reason, invalidated_at=now
        )
        superseded = quarantine_repo.supersede_batch(
            conn, batch_id=batch_id, reason=audit_reason, superseded_at=now
        )

        report = dict(batch["report"])
        reopen_record = {
            "reopened_at": now,
            "reason": reason,
            "curated_withdrawn_count": withdrawn,
            "quarantine_superseded_count": superseded,
            "round_no": batch["round_no"],
        }
        report.setdefault("reopen_history", []).append(reopen_record)
        report.setdefault("counts", {})["curated_withdrawn"] = withdrawn

        conn.execute(
            "UPDATE inspect_batches SET status=?, report_json=?, reopen_reason=?, reopened_at=? WHERE id=?",
            (REOPENED_STATUS, json.dumps(report, ensure_ascii=False), reason, now, batch_id),
        )

        events_repo.insert_event(
            conn,
            batch_id=batch_id,
            round_no=batch["round_no"],
            reason=reason,
            curated_withdrawn_count=withdrawn,
            quarantine_superseded_count=superseded,
            new_batch_id=None,
            created_at=now,
        )
        conn.commit()

        detail = batch_repo.get_batch(conn, batch_id)
        assert detail is not None
        detail["reopen_events"] = events_repo.list_for_batch(conn, batch_id)
        detail["curated_total"] = curated_repo.count_all(conn, batch["dataset_id"])
        detail["curated_withdrawn_total"] = len(curated_repo.list_withdrawn(conn))
        detail["quarantine_total"] = quarantine_repo.count_all(conn)
        return detail
    finally:
        conn.close()


def next_round_info(conn, batch_id: int) -> tuple[int, int | None, str | None]:
    """沿 ``reopened_from_id`` 链找到重开链的根批次（第 1 轮）。

    返回 (新一轮次号, 直接上一轮批次id, 本次重开原因)。
    轮次号取根批次 round_no + 链长，保证多轮重开后轮次严格递增。
    """
    current = batch_repo.get_batch(conn, batch_id)
    if current is None:
        raise ReopenError(f"batch {batch_id} not found")
    root = current
    depth = 0
    while root["reopened_from_id"] is not None:
        prev = batch_repo.get_batch(conn, root["reopened_from_id"])
        if prev is None:
            break
        root = prev
        depth += 1
    return root["round_no"] + depth + 1, current["id"], current["reopen_reason"]
