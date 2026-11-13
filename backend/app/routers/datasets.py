from fastapi import APIRouter

from app.db import connect
from app.repositories import datasets as dataset_repo

router = APIRouter(tags=["datasets"])


@router.get("/datasets")
def list_datasets():
    conn = connect()
    try:
        return dataset_repo.list_datasets(conn)
    finally:
        conn.close()
