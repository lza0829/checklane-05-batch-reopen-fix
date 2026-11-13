from fastapi import APIRouter, HTTPException

from app.schemas.entities import InspectRequest
from app.services.inspect_service import run_inspect

router = APIRouter(tags=["inspect"])


@router.post("/inspect")
def inspect(body: InspectRequest):
    try:
        return run_inspect(body.dataset_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
