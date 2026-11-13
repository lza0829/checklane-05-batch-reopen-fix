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
