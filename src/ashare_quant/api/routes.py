"""FastAPI routes exposing the A-share module: read-only reports plus
web-triggered backtests running as background jobs."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ashare_quant import pipeline
from ashare_quant.api import jobs, service

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _reports_dir() -> Path:
    """Allow deployment overrides via ASHARE_REPORTS_DIR, default to ./reports."""
    override = os.environ.get("ASHARE_REPORTS_DIR")
    return Path(override) if override else PROJECT_ROOT / "reports"


def _data_cache_dir() -> Path:
    return PROJECT_ROOT / "data" / "raw"


class BacktestBody(BaseModel):
    start: str
    end: str
    lookback: int = 60
    holdings: int = 10
    rebalance: int | str = 5
    source: str = "synthetic"

    def to_params(self) -> pipeline.RunParams:
        return pipeline.RunParams(
            start=self.start, end=self.end, lookback=self.lookback,
            holdings=self.holdings, rebalance=self.rebalance, source=self.source,
        )


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

    @router.post("/backtests", status_code=202)
    def post_backtest(body: BacktestBody) -> dict[str, object]:
        params = body.to_params()
        try:
            params.validate()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            job = jobs.submit(
                "backtest",
                lambda: pipeline.run_backtest(
                    params, _reports_dir(), _data_cache_dir(), trigger="web"
                ).public(),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"job_id": job.job_id, "status": job.status}

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, object]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
        return job.public()

    return router
