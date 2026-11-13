from fastapi import APIRouter, HTTPException

from app.db import connect
from app.repositories import rules as rules_repo
from app.schemas.entities import RuleEnablePatch

router = APIRouter(tags=["rules"])


@router.get("/rules")
def list_rules(dataset_id: int | None = None):
    conn = connect()
    try:
        return rules_repo.list_rules(conn, dataset_id)
    finally:
        conn.close()


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: int, body: RuleEnablePatch):
    conn = connect()
    try:
        existing = conn.execute("SELECT id FROM rules WHERE id=?", (rule_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "rule not found")
        rules_repo.set_enabled(conn, rule_id, body.enabled)
        conn.commit()
        return {"id": rule_id, "enabled": body.enabled}
    finally:
        conn.close()
