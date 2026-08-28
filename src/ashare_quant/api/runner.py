"""Execute a momentum backtest from API parameters and persist its reports.

Mirrors ``scripts/run_real_backtest.py`` so CLI and web runs produce
identical artifacts. ``source`` selects the price panel:

* ``synthetic`` - deterministic pseudo-random panel, runs in seconds,
  ideal for demoing the pipeline without external dependencies.
* ``real``      - AkShare/Tencent forward-adjusted dailies with a local
  cache; requires the ``akshare`` package.

The returned dict is JSON-ready (NaN mapped to ``None``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ashare_quant import BacktestConfig, DailyBacktester
from ashare_quant.data import download_daily_history
from ashare_quant.reporting import performance_summary
from ashare_quant.strategies import top_n_momentum_weights

# Same stable, liquid universe as the CLI runner so results stay comparable.
DEFAULT_SYMBOLS = [
    "000001", "000333", "000651", "000858", "002594",
    "300750", "600000", "600036", "600519", "601318",
    "601398", "601857", "601888", "601899", "603288",
]

CADENCE = {"weekly": 5, "monthly": 21}
SOURCES = ("synthetic", "real")


@dataclass(frozen=True)
class BacktestRequest:
    start: str          # YYYYMMDD inclusive
    end: str            # YYYYMMDD inclusive
    lookback: int = 60
    holdings: int = 10
    rebalance: int | str = 5
    source: str = "synthetic"

    def normalized(self) -> "BacktestRequest":
        cadence = CADENCE.get(self.rebalance) if isinstance(self.rebalance, str) else None
        rebalance = cadence if cadence is not None else int(self.rebalance)
        return BacktestRequest(
            start=self.start.strip(), end=self.end.strip(),
            lookback=int(self.lookback), holdings=int(self.holdings),
            rebalance=rebalance, source=self.source.strip().lower(),
        )

    def validate(self) -> None:
        if len(self.start) != 8 or len(self.end) != 8 or not all(c.isdigit() for c in self.start + self.end):
            raise ValueError("start/end must be YYYYMMDD")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if min(self.lookback, self.holdings) < 1:
            raise ValueError("lookback and holdings must be positive")
        if self.rebalance < 1:
            raise ValueError("rebalance must be positive")
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}")


def synthetic_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministic demo panel (mirrors scripts/run_example.py)."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2021-01-01", periods=300)
    symbols = [f"{code:06d}.SZ" for code in range(1, 31)]
    returns = rng.normal(0.0003, 0.018, size=(len(dates), len(symbols)))
    close = pd.DataFrame(20 * np.exp(np.cumsum(returns, axis=0)), index=dates, columns=symbols)
    open_ = close.shift(1).bfill() * 1.001
    return open_, close


def _import_akshare():
    """Import akshare, falling back to the repo's vendored copy."""
    try:
        import akshare  # noqa: F401
    except ImportError:
        vendor = Path(__file__).resolve().parents[3] / ".vendor"
        if vendor.is_dir():
            import sys
            sys.path.insert(0, str(vendor))
            import akshare  # noqa: F401
        else:
            raise
    return akshare


def real_panel(request: BacktestRequest, cache_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download (or reuse cached) forward-adjusted dailies for the universe."""
    _import_akshare()
    histories = download_daily_history(
        DEFAULT_SYMBOLS, request.start, request.end, cache_dir
    )
    open_prices = pd.concat({s: f["open"] for s, f in histories.items()}, axis=1)
    close_prices = pd.concat({s: f["close"] for s, f in histories.items()}, axis=1)
    valid = open_prices.notna().all(axis=1) & close_prices.notna().all(axis=1)
    return open_prices.loc[valid], close_prices.loc[valid]


def run_backtest(request: BacktestRequest, reports_dir: Path, data_cache_dir: Path) -> dict[str, object]:
    """Run one backtest end to end and write the standard report trio."""
    request = request.normalized()
    request.validate()
    reports_dir.mkdir(parents=True, exist_ok=True)

    if request.source == "synthetic":
        open_prices, close_prices = synthetic_panel()
    else:
        open_prices, close_prices = real_panel(request, data_cache_dir)

    if len(close_prices) <= request.lookback:
        raise RuntimeError(
            f"only {len(close_prices)} common trading days; lookback={request.lookback} requires more"
        )

    weights = top_n_momentum_weights(
        close_prices, lookback_days=request.lookback, holdings=request.holdings,
        rebalance_every=request.rebalance,
    )
    result = DailyBacktester(BacktestConfig()).run(open_prices, close_prices, weights)
    summary = performance_summary(result.equity_curve)

    # Wall-clock stamp keeps repeated windows from overwriting each other.
    stamp = pd.Timestamp.now().strftime("%H%M%S")
    strategy = f"web_momentum_{stamp}"
    start, end = request.start, request.end
    result.equity_curve.to_csv(reports_dir / f"{strategy}_equity_{start}_{end}.csv", encoding="utf-8-sig")
    result.trades.to_csv(reports_dir / f"{strategy}_trades_{start}_{end}.csv", index=False, encoding="utf-8-sig")
    summary.to_frame("value").to_csv(reports_dir / f"{strategy}_summary_{start}_{end}.csv", encoding="utf-8-sig")

    from ashare_quant.api import service

    return {
        "run_id": f"{start}_{end}__{strategy}",
        "metrics": {str(k): service._num(v) for k, v in summary.items()},
        "trades": int(len(result.trades)),
        "days": int(len(close_prices)),
    }
