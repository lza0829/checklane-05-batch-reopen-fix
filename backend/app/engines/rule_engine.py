from __future__ import annotations

import math
from typing import Any


def evaluate_row(payload: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对单行执行已启用规则，返回命中列表（可空）。"""
    hits: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.get("enabled", 1):
            continue
        field = rule["field"]
        value = payload.get(field)
        rule_type = rule["rule_type"]
        ok = True
        detail = ""
        if rule_type == "required":
            ok = value is not None and str(value).strip() != ""
            detail = "字段为空" if not ok else ""
        elif rule_type == "type_number":
            try:
                num = float(value)
                ok = math.isfinite(num)
                detail = f"期望有限数字，实际 {value!r}" if not ok else ""
            except (TypeError, ValueError):
                ok = False
                detail = f"期望数字，实际 {value!r}"
        elif rule_type == "type_int":
            ok = isinstance(value, int) and not isinstance(value, bool)
            if not ok:
                # JSON 可能把整数字面量解析成 int；字符串整数不算通过
                detail = f"期望整数，实际 {value!r}"
        else:
            ok = True
            detail = f"未知规则类型 {rule_type}，已跳过"
            continue
        if not ok:
            hits.append(
                {
                    "rule_id": rule["id"],
                    "name": rule["name"],
                    "field": field,
                    "rule_type": rule_type,
                    "severity": rule["severity"],
                    "detail": detail,
                }
            )
    return hits


def decide_disposition(hits: list[dict[str, Any]]) -> str:
    """error 命中 → quarantine；仅 warn → pass（带命中）；无命中 → pass。"""
    if any(h.get("severity") == "error" for h in hits):
        return "quarantine"
    return "pass"
