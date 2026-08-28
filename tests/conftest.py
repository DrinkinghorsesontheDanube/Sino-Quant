"""Sandbox-friendly replacement for pytest's ``tmp_path``.

The stock fixture creates numbered directories under the system temp area
with permission hardening, which this locked-down environment rejects with
WinError 5. A plain workspace-local directory with default (inherited)
ACLs works everywhere, so we shadow the built-in fixture by name.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pandas as pd
import pytest

BASE = Path(__file__).resolve().parent / ".tmp-scratch"


@pytest.fixture()
def tmp_path() -> Path:
    BASE.mkdir(exist_ok=True)
    path = BASE / uuid.uuid4().hex[:12]
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def reports_dir(tmp_path: Path) -> Path:
    """One run in the on-disk report naming scheme, for API tests."""
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
        ]
    )
    summary = pd.Series(
        {
            "cumulative_return": 0.06,
            "annualized_return": float("nan"),
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
