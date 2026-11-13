from fastapi import APIRouter, HTTPException

from app.modules.batch_reopen_fix import ReopenError
from app.schemas.entities import InspectRequest, ReInspectRequest
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


@router.post("/inspect/reopen-round")
def inspect_reopen_round(body: ReInspectRequest):
    """对已重开（reopened）批次执行新一轮再入检，生成新批次、新一轮结果。"""
    try:
        return run_inspect(
            body.dataset_id,
            reopen_from_batch_id=body.reopen_from_batch_id,
        )
    except ReopenError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
