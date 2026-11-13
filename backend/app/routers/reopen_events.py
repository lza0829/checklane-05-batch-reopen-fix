from fastapi import APIRouter

from app.db import connect
from app.repositories import reopen_events as events_repo

router = APIRouter(tags=["batches"])


@router.get("/reopen-events")
def list_reopen_events():
    """批次重开审计事件：重开原因、精选区撤回条数、隔离区失效条数、新一轮批次。"""
    conn = connect()
    try:
        return events_repo.list_all(conn)
    finally:
        conn.close()
