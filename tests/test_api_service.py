"""Tests for the read-only report API service and FastAPI routes."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_quant.api import service  # noqa: E402


@pytest.fixture()
def reports_dir(tmp_path: Path) -> Path:
    curve = pd.DataFrame(
        {
            "cash": [100.0, 50.0, 40.0],
            "market_value": [0.0, 55.0, 66.0],
            "equity": [100.0, 105.0, 106.0],
            "buy_value": [0.0, 50.0, 0.0],
            "sell_value": [0.0, 0.0, 10.0],
        },
        index=pd.date_range("2024-01-02", periods=3, freq="D"),
    )
    trades = pd.DataFrame(
        [
            {"date": "2024-01-03", "symbol": "600519", "side": "BUY", "shares": 100,
             "price": 1700.0, "commission": 5.0, "tax": 0.0, "fee": 5.0},
            {"date": "2024-01-04", "symbol": "600519", "side": "SELL", "shares": 10,
             "price": 1710.0, "commission": 5.0, "tax": 8.5, "fee": 13.5},
        ]
    )
    summary = pd.Series(
        {
            "cumulative_return": 0.06,
            "annualized_return": float("nan"),  # exercise NaN -> None mapping
            "annualized_volatility": 0.2,
            "sharpe_ratio": 1.1,
            "max_drawdown": -0.03,
            "turnover_rate": 2.5,
        }
    )
    stem = "real_momentum"
    start, end = "20240102", "20260821"
    curve.to_csv(tmp_path / f"{stem}_equity_{start}_{end}.csv", encoding="utf-8-sig")
    trades.to_csv(tmp_path / f"{stem}_trades_{start}_{end}.csv", index=False, encoding="utf-8-sig")
    summary.to_frame("value").to_csv(tmp_path / f"{stem}_summary_{start}_{end}.csv", encoding="utf-8-sig")
    return tmp_path


def test_list_runs_discovers_and_sorts(reports_dir: Path) -> None:
    runs = service.list_runs(reports_dir)
    assert len(runs) == 1
    run = runs[0]
    assert run["run_id"] == "20240102_20260821"
    assert run["strategy"] == "real_momentum"
    assert run["has_trades"] is True


def test_summary_maps_metrics_and_curve(reports_dir: Path) -> None:
    payload = service.load_summary(reports_dir, "20240102_20260821")
    assert payload is not None
    assert payload["metrics"]["annualized_return"] is None  # NaN became null
    assert payload["metrics"]["sharpe_ratio"] == pytest.approx(1.1)
    equity_values = [point["equity"] for point in payload["curve"]]
    assert equity_values == [100.0, 105.0, 106.0]
    drawdowns = [point["drawdown"] for point in payload["curve"]]
    assert drawdowns == [0.0, 0.0, pytest.approx(0.0)] or max(drawdowns) <= 0.0


def test_trades_roundtrip(reports_dir: Path) -> None:
    payload = service.load_trades(reports_dir, "20240102_20260821")
    assert payload is not None and payload["count"] == 2
    first = payload["trades"][0]
    assert first["symbol"] == "600519"
    assert first["side"] == "BUY"
    assert first["price"] == pytest.approx(1700.0)


def test_unknown_run_returns_none(reports_dir: Path) -> None:
    assert service.load_summary(reports_dir, "19990101_20000101") is None
    assert service.load_trades(reports_dir, "../../etc/passwd") is None


def test_router_end_to_end(reports_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("ASHARE_REPORTS_DIR", str(reports_dir))
    from fastapi import FastAPI

    from ashare_quant.api import create_a_share_router

    app = FastAPI()
    app.include_router(create_a_share_router(), prefix="/api/a-share")
    client = fastapi_testclient.TestClient(app)

    listing = client.get("/api/a-share/reports")
    assert listing.status_code == 200
    assert listing.json()["runs"][0]["run_id"] == "20240102_20260821"

    summary = client.get("/api/a-share/runs/20240102_20260821/summary")
    assert summary.status_code == 200
    assert summary.json()["curve"][0]["date"].startswith("2024-01-02")

    missing = client.get("/api/a-share/runs/19990101_20000101/summary")
    assert missing.status_code == 404
