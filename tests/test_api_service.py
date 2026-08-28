"""Tests for the read-only report API service and FastAPI routes."""

from __future__ import annotations

from pathlib import Path

import pytest

from ashare_quant.api import service


def test_list_runs_discovers_and_sorts(reports_dir: Path) -> None:
    runs = service.list_runs(reports_dir)
    assert len(runs) == 1
    run = runs[0]
    assert run["run_id"] == "20240102_20260821__real_momentum"
    assert run["strategy"] == "real_momentum"
    assert run["has_trades"] is True
    assert run["params"] == {"lookback": 60, "holdings": 10, "rebalance": 5}


def test_summary_maps_metrics_curve_and_params(reports_dir: Path) -> None:
    payload = service.load_summary(reports_dir, "20240102_20260821__real_momentum")
    assert payload is not None
    assert payload["metrics"]["annualized_return"] is None  # NaN became null
    assert payload["metrics"]["sharpe_ratio"] == pytest.approx(1.1)
    assert payload["params"]["lookback"] == 60
    equity_values = [point["equity"] for point in payload["curve"]]
    assert equity_values == [100.0, 105.0, 106.0]
    drawdowns = [point["drawdown"] for point in payload["curve"]]
    assert drawdowns == [0.0, 0.0, pytest.approx(0.0)] or max(drawdowns) <= 0.0


def test_trades_roundtrip(reports_dir: Path) -> None:
    payload = service.load_trades(reports_dir, "20240102_20260821__real_momentum")
    assert payload is not None and payload["count"] == 1
    first = payload["trades"][0]
    assert first["symbol"] == "600519"
    assert first["side"] == "BUY"
    assert first["price"] == pytest.approx(1700.0)


def test_unknown_or_malformed_run_returns_none(reports_dir: Path) -> None:
    assert service.load_summary(reports_dir, "19990101_20000101") is None
    assert service.load_summary(reports_dir, "../../etc/passwd") is None
    assert service.load_summary(reports_dir, "..") is None
    assert service.load_trades(reports_dir, "missing_run") is None


def test_router_end_to_end(reports_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("ASHARE_REPORTS_DIR", str(reports_dir))
    from fastapi import FastAPI

    from ashare_quant.api import create_a_share_router

    app = FastAPI()
    app.include_router(create_a_share_router(), prefix="/api/a-share")
    client = fastapi_testclient.TestClient(app)
    run_id = "20240102_20260821__real_momentum"

    listing = client.get("/api/a-share/reports")
    assert listing.status_code == 200
    assert listing.json()["runs"][0]["run_id"] == run_id

    summary = client.get(f"/api/a-share/runs/{run_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["curve"][0]["date"].startswith("2024-01-02")

    missing = client.get("/api/a-share/runs/19990101_20000101/summary")
    assert missing.status_code == 404
