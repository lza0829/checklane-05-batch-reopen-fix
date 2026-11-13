import importlib

import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import app.config
    import app.db
    import app.seed
    import app.services.inspect_service as svc
    import app.modules.batch_reopen_fix as reopen_mod
    from app.repositories import curated as curated_repo
    from app.repositories import quarantine as quarantine_repo
    from app.repositories import reopen_events as events_repo
    from app.repositories import batches as batch_repo

    importlib.reload(app.config)
    importlib.reload(app.db)
    importlib.reload(app.seed)
    importlib.reload(reopen_mod)
    # inspect_service 依赖 batch_reopen_fix，必须在其后 reload，
    # 否则两边引用的 ReopenError 类对象不是同一个
    importlib.reload(svc)
    app.seed.init_db()

    class _Env:
        pass

    e = _Env()
    e.svc = svc
    e.reopen_mod = reopen_mod
    e.curated_repo = curated_repo
    e.quarantine_repo = quarantine_repo
    e.events_repo = events_repo
    e.batch_repo = batch_repo
    e.connect = app.db.connect
    return e


def _counts(conn, curated_repo, quarantine_repo, events_repo, dataset_id=1):
    return {
        "curated_active": curated_repo.count_all(conn, dataset_id),
        "curated_withdrawn": len(curated_repo.list_withdrawn(conn)),
        "quarantine_active": quarantine_repo.count_all(conn),
        "reopen_events": events_repo.count_all(conn),
    }


def test_full_sign_reopen_reinspect_flow(env):
    """签发 → 重开撤回 → 再入检：状态、精选区、隔离区、报告计数前后互证。"""
    conn = env.connect()
    try:
        before = _counts(conn, env.curated_repo, env.quarantine_repo, env.events_repo)
        assert before == {
            "curated_active": 0,
            "curated_withdrawn": 0,
            "quarantine_active": 0,
            "reopen_events": 0,
        }

        # —— 第一轮入检并签发 ——
        b1 = env.svc.run_inspect(1)
        assert b1["status"] == "released"
        assert b1["round_no"] == 1
        assert b1["reopened_from_id"] is None
        assert b1["scanned_count"] == 6
        assert b1["passed_count"] == 4
        assert b1["quarantined_count"] == 2
        assert b1["released_count"] == 4

        after_release = _counts(conn, env.curated_repo, env.quarantine_repo, env.events_repo)
        assert after_release["curated_active"] == 4
        assert after_release["curated_withdrawn"] == 0
        assert after_release["quarantine_active"] == 2
        # 精选区列表口径与计数口径一致
        assert len(env.curated_repo.list_all(conn, 1)) == 4

        # —— 未签发批次禁止重开：先造一个 inspected 态（无 pass 行的数据集做不到，
        #    直接用状态机校验 reopened/inspected 拒绝路径，见独立用例）——

        # —— 重开已签发批次 ——
        reopened = env.reopen_mod.reopen_batch(b1["id"], "现场反馈 ORD-1 数据错误，需打回重检")
        assert reopened["status"] == "reopened"
        assert reopened["reopen_reason"] == "现场反馈 ORD-1 数据错误，需打回重检"
        assert reopened["reopened_at"] is not None

        after_reopen = _counts(conn, env.curated_repo, env.quarantine_repo, env.events_repo)
        # 精选区在撤回后变少：4 → 0
        assert after_reopen["curated_active"] == 0
        assert after_reopen["curated_withdrawn"] == 4
        # 该批隔离行同步失效，隔离区存量 2 → 0
        assert after_reopen["quarantine_active"] == 0
        assert after_reopen["reopen_events"] == 1

        # 撤回审计：每条失效行都带原因与时间，且物理行仍在库里（标记失效而非删除）
        withdrawn_rows = env.curated_repo.list_withdrawn(conn)
        assert len(withdrawn_rows) == 4
        assert all(r["active"] == 0 for r in withdrawn_rows)
        assert all(r["invalidate_reason"] for r in withdrawn_rows)
        assert all(r["invalidated_at"] for r in withdrawn_rows)
        assert {r["batch_id"] for r in withdrawn_rows} == {b1["id"]}
        physical = conn.execute("SELECT COUNT(*) AS c FROM curated").fetchone()["c"]
        assert physical == 4  # 4 条失效行仍在库里，没有物理删除

        # 事件里记录了撤回条数与重开原因
        event = env.events_repo.list_for_batch(conn, b1["id"])[0]
        assert event["curated_withdrawn_count"] == 4
        assert event["quarantine_superseded_count"] == 2
        assert event["reason"] == "现场反馈 ORD-1 数据错误，需打回重检"
        assert event["new_batch_id"] is None  # 再入检前还没有新批次

        # 批次报告追加重开历史
        hist = reopened["report"]["reopen_history"]
        assert len(hist) == 1
        assert hist[0]["curated_withdrawn_count"] == 4

        # —— 已重开批次不能再次重开（幂等保护）——
        with pytest.raises(env.reopen_mod.ReopenError):
            env.reopen_mod.reopen_batch(b1["id"], "重复重开")

        # —— 再入检：生成新批次、新一轮，可核对的新结果 ——
        b2 = env.svc.run_inspect(1, reopen_from_batch_id=b1["id"])
        assert b2["id"] != b1["id"]
        assert b2["round_no"] == 2
        assert b2["reopened_from_id"] == b1["id"]
        assert b2["status"] == "released"
        assert b2["released_count"] == 4
        assert b2["quarantined_count"] == 2

        after_reinspect = _counts(conn, env.curated_repo, env.quarantine_repo, env.events_repo)
        # 再入检后按新结果变化：精选区恢复为新一轮的 4 条 active
        assert after_reinspect["curated_active"] == 4
        # 撤回的旧行仍是失效状态，不会假装还在精选区；新结果是独立新行
        assert after_reinspect["curated_withdrawn"] == 4
        physical_curated = conn.execute("SELECT COUNT(*) AS c FROM curated").fetchone()["c"]
        assert physical_curated == 8  # 4 失效（第1轮）+ 4 有效（第2轮）
        # 新一轮隔离行重新落库；旧隔离行保持失效
        assert after_reinspect["quarantine_active"] == 2
        physical_quar = conn.execute("SELECT COUNT(*) AS c FROM quarantine").fetchone()["c"]
        assert physical_quar == 4  # 2 失效 + 2 新有效

        # 精选区现存行全部来自新一轮批次
        active_rows = env.curated_repo.list_all(conn, 1)
        assert {r["batch_id"] for r in active_rows} == {b2["id"]}
        assert all(r["active"] == 1 for r in active_rows)

        # 新批次报告中的重开互证校验必须通过
        trace_checks = [c for c in b2["report"]["checks"] if c["name"] == "reopen_round_curated_traceable"]
        assert len(trace_checks) == 1
        assert trace_checks[0]["ok"] is True
        assert all(c["ok"] for c in b2["report"]["checks"])

        # 审计事件已回填新批次 id，串起重开 → 再入检链
        event = env.events_repo.list_for_batch(conn, b1["id"])[0]
        assert event["new_batch_id"] == b2["id"]

        # 原批次状态保持 reopened，历史结果不被覆盖
        b1_again = env.batch_repo.get_batch(conn, b1["id"])
        assert b1_again["status"] == "reopened"
        assert len(env.batch_repo.list_batch_rows(conn, b1["id"])) == 6
        b2_rows = env.batch_repo.list_batch_rows(conn, b2["id"])
        assert len(b2_rows) == 6
        assert all(r["round_no"] == 2 for r in b2_rows)

    finally:
        conn.close()


def test_reopen_refuses_unreleased_batch(env):
    """未签发批次禁止重开。"""
    b1 = env.svc.run_inspect(1)
    # 手工把批次置回 inspected，模拟未签发态
    conn = env.connect()
    try:
        conn.execute("UPDATE inspect_batches SET status='inspected' WHERE id=?", (b1["id"],))
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(env.reopen_mod.ReopenError) as exc:
        env.reopen_mod.reopen_batch(b1["id"], "不应允许")
    assert "不可重开" in str(exc.value)


def test_reopen_requires_reason(env):
    b1 = env.svc.run_inspect(1)
    with pytest.raises(env.reopen_mod.ReopenError):
        env.reopen_mod.reopen_batch(b1["id"], "   ")


def test_reopen_nonexistent_batch(env):
    with pytest.raises(env.reopen_mod.ReopenError):
        env.reopen_mod.reopen_batch(9999, "x")


def test_reinspect_requires_reopened_status(env):
    """只有 reopened 态批次能走再入检；已签发批次直接再入检拒绝。"""
    b1 = env.svc.run_inspect(1)  # released
    with pytest.raises(env.reopen_mod.ReopenError):
        env.svc.run_inspect(1, reopen_from_batch_id=b1["id"])


def test_reinspect_dataset_mismatch(env):
    b1 = env.svc.run_inspect(1)
    env.reopen_mod.reopen_batch(b1["id"], "打回")
    with pytest.raises(env.reopen_mod.ReopenError) as exc:
        env.svc.run_inspect(2, reopen_from_batch_id=b1["id"])
    assert "dataset 不匹配" in str(exc.value)


def test_second_reopen_round_after_fix(env):
    """第二轮再入检签发后还能再次重开、第三次入检，轮次号与链路正确。"""
    b1 = env.svc.run_inspect(1)
    env.reopen_mod.reopen_batch(b1["id"], "第一次打回")
    b2 = env.svc.run_inspect(1, reopen_from_batch_id=b1["id"])
    assert b2["round_no"] == 2

    env.reopen_mod.reopen_batch(b2["id"], "第二次打回")
    conn = env.connect()
    try:
        # 第二次重开撤回的是 b2 写入的 4 行；b1 的 4 行早已失效
        assert env.curated_repo.count_all(conn, 1) == 0
        assert len(env.curated_repo.list_withdrawn(conn)) == 8
        assert env.events_repo.count_all(conn) == 2
    finally:
        conn.close()

    b3 = env.svc.run_inspect(1, reopen_from_batch_id=b2["id"])
    assert b3["round_no"] == 3
    assert b3["reopened_from_id"] == b2["id"]
    conn = env.connect()
    try:
        assert env.curated_repo.count_all(conn, 1) == 4
        active = env.curated_repo.list_all(conn, 1)
        assert {r["batch_id"] for r in active} == {b3["id"]}
        # 事件链完整
        events = env.events_repo.list_all(conn)
        assert [e["batch_id"] for e in events] == [b2["id"], b1["id"]]
        assert [e["new_batch_id"] for e in events] == [b3["id"], b2["id"]]
    finally:
        conn.close()


def test_curated_count_survives_refresh(env):
    """计数口径来自 SQL 查询而非内存：重新打开连接后数字仍互证。"""
    b1 = env.svc.run_inspect(1)
    env.reopen_mod.reopen_batch(b1["id"], "打回")
    env.svc.run_inspect(1, reopen_from_batch_id=b1["id"])

    conn = env.connect()  # 全新连接，模拟页面刷新
    try:
        assert env.curated_repo.count_all(conn, 1) == 4
        assert len(env.curated_repo.list_withdrawn(conn)) == 4
        assert env.quarantine_repo.count_all(conn) == 2
        batches = env.batch_repo.list_batches(conn)
        statuses = {b["id"]: b["status"] for b in batches}
        assert statuses[b1["id"]] == "reopened"
    finally:
        conn.close()
