"""End-to-end tests for the shared pipeline (synthetic source, mask wiring)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ashare_quant import pipeline
from ashare_quant.api import service
from ashare_quant.data.masks import PricePanels


def test_synthetic_run_writes_directory_with_meta(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    params = pipeline.RunParams(start="20240101", end="20241231")
    result = pipeline.run_backtest(params, reports, tmp_path / "raw", trigger="web")

    assert result.run_id == "20240101_20241231__momentum"
    run_dir = reports / result.run_id
    for name in ("equity.csv", "trades.csv", "summary.csv", "meta.json"):
        assert (run_dir / name).is_file(), name

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["params"] == {"lookback": 60, "holdings": 10, "rebalance": 5}
    assert meta["trigger"] == "web"
    assert meta["source"] == "synthetic"
    assert meta["universe"] == list(pipeline.DEFAULT_UNIVERSE)
    assert meta["config"]["commission_rate"] == 0.0003
    assert meta["days"] == result.days

    runs = service.list_runs(reports)
    assert [r["run_id"] for r in runs] == [result.run_id]
    assert runs[0]["params"] == meta["params"]


def test_repeated_window_gets_unique_run_id(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    params = pipeline.RunParams(start="20240101", end="20241231")
    first = pipeline.run_backtest(params, reports, tmp_path / "raw")
    second = pipeline.run_backtest(params, reports, tmp_path / "raw")

    assert first.run_id != second.run_id
    assert second.run_id.startswith(f"{first.run_id}__")
    assert len(service.list_runs(reports)) == 2


def test_invalid_params_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="start must be before end"):
        pipeline.run_backtest(
            pipeline.RunParams(start="20241231", end="20240101"),
            tmp_path, tmp_path,
        )


def test_real_source_wires_masks_into_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A never-tradable symbol must never trade, proving the pipeline passes
    the tradability masks from the data layer into the backtester."""
    dates = pd.bdate_range("2024-01-02", periods=80)
    symbols = ["600000", "000001", "300750"]
    rng = np.random.default_rng(3)
    close = pd.DataFrame(
        20 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, size=(len(dates), 3)), axis=0)),
        index=dates, columns=symbols,
    )
    open_ = close.shift(1).bfill()
    true_frame = pd.DataFrame(True, index=dates, columns=symbols)
    panels = PricePanels(
        open_prices=open_, close_prices=close,
        tradable=true_frame.copy(), buyable=true_frame.copy(), sellable=true_frame.copy(),
    )
    panels.tradable["600000"] = False  # permanently suspended
    monkeypatch.setattr(
        pipeline, "real_panels", lambda params, cache_dir, refresh=False: panels
    )

    reports = tmp_path / "reports"
    result = pipeline.run_backtest(
        pipeline.RunParams(start="20240102", end="20240501", lookback=10, holdings=2, source="real"),
        reports, tmp_path / "raw",
    )
    assert result.run_id.startswith("20240102_20240501__momentum")

    trades = pd.read_csv(reports / result.run_id / "trades.csv")
    assert "600000" not in set(trades["symbol"])
    assert set(trades["symbol"])  # the other two did trade
