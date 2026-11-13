from fastapi import APIRouter, HTTPException

from app.db import connect
from app.modules.batch_reopen_fix import ReopenError, reopen_batch
from app.repositories import batches as batch_repo
from app.repositories import curated as curated_repo
from app.repositories import reopen_events as events_repo
from app.schemas.entities import ReopenRequest

router = APIRouter(tags=["batches"])


@router.get("/batches")
def list_batches():
    conn = connect()
    try:
        return batch_repo.list_batches(conn)
    finally:
        conn.close()


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int):
    conn = connect()
    try:
        detail = batch_repo.get_batch(conn, batch_id)
        if not detail:
            raise HTTPException(404, "batch not found")
        detail["rows"] = batch_repo.list_batch_rows(conn, batch_id)
        detail["reopen_events"] = events_repo.list_for_batch(conn, batch_id)
        detail["curated_total"] = curated_repo.count_all(conn, detail["dataset_id"])
        return detail
    finally:
        conn.close()


@router.post("/batches/{batch_id}/reopen")
def reopen(batch_id: int, body: ReopenRequest):
    """重开已签发/已完成批次：撤回精选区行、失效隔离行、进入可修复态并留审计。"""
    try:
        return reopen_batch(batch_id, body.reason)
    except ReopenError as exc:
        raise HTTPException(409, str(exc)) from exc
