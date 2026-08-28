"""End-to-end tests for web-triggered backtests (synthetic source)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture()
def client(reports_dir, monkeypatch):
    testclient = pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("ASHARE_REPORTS_DIR", str(reports_dir))
    from fastapi import FastAPI

    from ashare_quant.api import create_a_share_router

    app = FastAPI()
    app.include_router(create_a_share_router(), prefix="/api/a-share")
    return testclient.TestClient(app)


def _wait_for_job(client, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/api/a-share/jobs/{job_id}").json()
        if payload["status"] in ("succeeded", "failed"):
            return payload
        time.sleep(0.3)
    raise AssertionError("job did not finish in time")


def test_submit_and_complete_synthetic_backtest(client, reports_dir) -> None:
    response = client.post(
        "/api/a-share/backtests",
        json={"start": "20240101", "end": "20241231", "lookback": 60,
              "holdings": 10, "rebalance": 5, "source": "synthetic"},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    job = _wait_for_job(client, job_id)
    assert job["status"] == "succeeded", job["error"]
    assert job["result"]["run_id"].startswith("20240101_20241231__web_momentum_")
    assert job["result"]["trades"] > 0

    listing = client.get("/api/a-share/reports").json()["runs"]
    assert job["result"]["run_id"] in {r["run_id"] for r in listing}

    summary = client.get(f"/api/a-share/runs/{job['result']['run_id']}/summary")
    assert summary.status_code == 200
    assert summary.json()["curve"]


def test_invalid_params_rejected(client) -> None:
    response = client.post(
        "/api/a-share/backtests",
        json={"start": "20241231", "end": "20240101", "source": "synthetic"},
    )
    assert response.status_code == 422


def test_unknown_job_404(client) -> None:
    assert client.get("/api/a-share/jobs/deadbeef").status_code == 404
