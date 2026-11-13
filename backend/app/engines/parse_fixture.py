from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"fixture missing: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"bad jsonl at line {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"row {line_no} must be object")
        rows.append(obj)
    return rows
