"""FastAPI routes exposing the A-share backtest reports read-only."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ashare_quant.api import service

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _reports_dir() -> Path:
    """Allow deployment overrides via ASHARE_REPORTS_DIR, default to ./reports."""
    override = os.environ.get("ASHARE_REPORTS_DIR")
    return Path(override) if override else PROJECT_ROOT / "reports"


def create_router() -> APIRouter:
    router = APIRouter(tags=["a-share"])

    @router.get("/reports")
    def get_reports() -> dict[str, object]:
        reports_dir = _reports_dir()
        if not reports_dir.exists():
            return {"runs": []}
        return {"runs": service.list_runs(reports_dir)}

    @router.get("/runs/{run_id}/summary")
    def get_summary(run_id: str) -> dict[str, object]:
        summary = service.load_summary(_reports_dir(), run_id)
        if summary is None:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
        return summary

    @router.get("/runs/{run_id}/trades")
    def get_trades(run_id: str) -> dict[str, object]:
        trades = service.load_trades(_reports_dir(), run_id)
        if trades is None:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
        return trades

    return router
