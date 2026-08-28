"""The one backtest pipeline shared by the CLI and the web API.

Both entry points reduce to :class:`RunParams` plus :func:`run_backtest`, so
they cannot drift apart: same universe, same config handling, same
tradability masks and the same on-disk report layout — one directory per run
under ``reports/`` containing ``equity.csv``, ``trades.csv``,
``summary.csv`` and a ``meta.json`` that records exactly how the run was
produced.

``source`` selects the price panel:

* ``synthetic`` - deterministic pseudo-random panel, runs in seconds,
  ideal for demoing the pipeline without external dependencies.
* ``real``      - AkShare/Tencent forward-adjusted dailies with a local
  cache; requires the ``akshare`` package.  Suspensions are masked
  untradable and limit-up/down opens block the affected side.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ashare_quant import BacktestConfig, DailyBacktester
from ashare_quant.data import download_daily_history
from ashare_quant.data.masks import PricePanels, build_price_panels
from ashare_quant.reporting import performance_summary
from ashare_quant.serialize import number
from ashare_quant.strategies import top_n_momentum_weights

# Same stable, liquid universe for CLI and web so results stay comparable.
DEFAULT_UNIVERSE = (
    "000001", "000333", "000651", "000858", "002594",
    "300750", "600000", "600036", "600519", "601318",
    "601398", "601857", "601888", "601899", "603288",
)

CADENCE = {"weekly": 5, "monthly": 21}
SOURCES = ("synthetic", "real")
REPORTS_VERSION = 2  # on-disk layout: one directory per run with meta.json


@dataclass(frozen=True)
class RunParams:
    """Everything one backtest run needs; shared verbatim by CLI and web."""

    start: str          # YYYYMMDD inclusive
    end: str            # YYYYMMDD inclusive
    lookback: int = 60
    holdings: int = 10
    rebalance: int | str = 5
    source: str = "synthetic"
    strategy: str = "momentum"
    symbols: tuple[str, ...] = DEFAULT_UNIVERSE
    config: BacktestConfig = BacktestConfig()

    def normalized(self) -> RunParams:
        cadence = CADENCE.get(self.rebalance) if isinstance(self.rebalance, str) else None
        rebalance = cadence if cadence is not None else int(self.rebalance)
        return RunParams(
            start=self.start.strip(), end=self.end.strip(),
            lookback=int(self.lookback), holdings=int(self.holdings),
            rebalance=rebalance, source=self.source.strip().lower(),
            strategy=self.strategy.strip(), symbols=tuple(self.symbols),
            config=self.config,
        )

    def validate(self) -> None:
        if len(self.start) != 8 or len(self.end) != 8 or not all(c.isdigit() for c in self.start + self.end):
            raise ValueError("start/end must be YYYYMMDD")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if min(self.lookback, self.holdings) < 1:
            raise ValueError("lookback and holdings must be positive")
        if not isinstance(self.rebalance, int) or self.rebalance < 1:
            raise ValueError("rebalance must be positive")
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}")
        if not self.strategy:
            raise ValueError("strategy name must not be empty")


@dataclass(frozen=True)
class RunResult:
    """Outcome of one persisted run; ``public()`` is the API JSON shape."""

    run_id: str
    params: RunParams
    days: int
    panel_start: pd.Timestamp
    panel_end: pd.Timestamp
    summary: pd.Series
    n_trades: int

    def public(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "metrics": {str(name): number(value) for name, value in self.summary.items()},
            "trades": int(self.n_trades),
            "days": int(self.days),
        }


def synthetic_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministic demo panel (also used by scripts/run_example.py)."""
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
        vendor = Path(__file__).resolve().parents[2] / ".vendor"
        if vendor.is_dir():
            import sys
            sys.path.insert(0, str(vendor))
            import akshare  # noqa: F401
        else:
            raise
    return akshare


def real_panels(params: RunParams, cache_dir: Path, refresh: bool = False) -> PricePanels:
    """Download (or reuse cached) forward-adjusted dailies, then add masks."""
    _import_akshare()
    histories = download_daily_history(
        list(params.symbols), params.start, params.end, cache_dir, refresh=refresh
    )
    return build_price_panels(histories)


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).resolve().parents[2],
        )
    except Exception:  # not a checkout / no git binary — meta only
        return None
    return completed.stdout.strip() or None


def _allocate_run_dir(reports_dir: Path, params: RunParams) -> tuple[str, Path]:
    """``{start}_{end}__{strategy}``, de-duplicated with a timestamp/uuid."""
    base = f"{params.start}_{params.end}__{params.strategy}"
    run_id = base
    if (reports_dir / run_id).exists():
        run_id = f"{base}__{datetime.now():%H%M%S}"
    while (reports_dir / run_id).exists():
        run_id = f"{base}__{uuid.uuid4().hex[:6]}"
    return run_id, reports_dir / run_id


def run_backtest(
    params: RunParams,
    reports_dir: Path,
    data_cache_dir: Path,
    *,
    trigger: str = "cli",
    refresh: bool = False,
) -> RunResult:
    """Run one backtest end to end and persist the per-run report directory."""
    params = params.normalized()
    params.validate()

    if params.source == "synthetic":
        open_prices, close_prices = synthetic_panel()
        panels: PricePanels | None = None
    else:
        panels = real_panels(params, data_cache_dir, refresh=refresh)
        open_prices, close_prices = panels.open_prices, panels.close_prices

    if len(close_prices) <= params.lookback:
        raise RuntimeError(
            f"only {len(close_prices)} common trading days; lookback={params.lookback} requires more"
        )

    weights = top_n_momentum_weights(
        close_prices, lookback_days=params.lookback, holdings=params.holdings,
        rebalance_every=params.rebalance,
    )
    result = DailyBacktester(params.config).run(
        open_prices, close_prices, weights,
        **({} if panels is None else {
            "tradable": panels.tradable,
            "buyable": panels.buyable,
            "sellable": panels.sellable,
        }),
    )
    summary = performance_summary(result.equity_curve)

    reports_dir.mkdir(parents=True, exist_ok=True)
    run_id, run_dir = _allocate_run_dir(reports_dir, params)
    run_dir.mkdir(parents=True, exist_ok=True)
    result.equity_curve.to_csv(run_dir / "equity.csv", encoding="utf-8-sig")
    result.trades.to_csv(run_dir / "trades.csv", index=False, encoding="utf-8-sig")
    summary.to_frame("value").to_csv(run_dir / "summary.csv", encoding="utf-8-sig")
    meta = {
        "layout_version": REPORTS_VERSION,
        "run_id": run_id,
        "strategy": params.strategy,
        "start": params.start,
        "end": params.end,
        "source": params.source,
        "trigger": trigger,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": _git_commit(),
        "params": {
            "lookback": params.lookback,
            "holdings": params.holdings,
            "rebalance": params.rebalance,
        },
        "universe": list(params.symbols),
        "config": asdict(params.config),
        "days": int(len(close_prices)),
        "panel_start": f"{close_prices.index[0]:%Y-%m-%d}",
        "panel_end": f"{close_prices.index[-1]:%Y-%m-%d}",
    }
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if panels is not None:
        # Keep the processed panels for audit, named after the run.
        processed_dir = data_cache_dir.parent / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        close_prices.to_csv(processed_dir / f"real_close_{run_id}.csv", encoding="utf-8-sig")
        open_prices.to_csv(processed_dir / f"real_open_{run_id}.csv", encoding="utf-8-sig")

    return RunResult(
        run_id=run_id, params=params, days=int(len(close_prices)),
        panel_start=close_prices.index[0], panel_end=close_prices.index[-1],
        summary=summary, n_trades=len(result.trades),
    )
