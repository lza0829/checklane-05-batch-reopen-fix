from fastapi import APIRouter

from app.db import connect
from app.repositories import curated as curated_repo

router = APIRouter(tags=["curated"])


@router.get("/curated")
def list_curated(dataset_id: int | None = None):
    conn = connect()
    try:
        return curated_repo.list_all(conn, dataset_id)
    finally:
        conn.close()


@router.get("/curated/withdrawn")
def list_withdrawn_curated():
    """重开撤回审计：被标记失效（active=0）的历史精选行。"""
    conn = connect()
    try:
        return curated_repo.list_withdrawn(conn)
    finally:
        conn.close()
