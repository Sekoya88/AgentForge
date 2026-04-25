#!/usr/bin/env python3
"""Dump FastAPI OpenAPI schema to openapi/openapi.json (repo root).

Run from repository root:
  cd backend && uv run python ../scripts/export_openapi.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "openapi" / "openapi.json"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)


def main() -> int:
    from app.main import app

    OUT.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
