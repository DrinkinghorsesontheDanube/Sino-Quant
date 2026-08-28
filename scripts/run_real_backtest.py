"""Download a real A-share sample and run the momentum baseline end to end.

Thin adapter over :mod:`ashare_quant.pipeline`: loads the YAML config into
:class:`RunParams` and delegates, so CLI and web runs produce identical
artifacts from the same code path.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
# Allows a self-contained installation made with `pip install --target .vendor`.
if (PROJECT_ROOT / ".vendor").exists():
    sys.path.insert(0, str(PROJECT_ROOT / ".vendor"))

from ashare_quant import BacktestConfig
from ashare_quant.pipeline import CADENCE, RunParams, run_backtest

DEFAULT_CONFIG = PROJECT_ROOT / "config" / "momentum_weekly.example.yaml"


def load_config(path: Path) -> tuple[dict[str, object], dict[str, object], int]:
    """Load the copyable strategy/backtest YAML into run parameters."""
    import yaml

    with path.open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    strategy = cfg.get("strategy") or {}
    backtest = cfg.get("backtest") or {}

    rebalance = strategy.get("rebalance", 5)
    if isinstance(rebalance, str):
        rebalance = CADENCE.get(rebalance.strip().lower(), 5)
    if not isinstance(rebalance, int) or rebalance < 1:
        raise ValueError(f"invalid rebalance cadence in {path}: {strategy.get('rebalance')!r}")

    return strategy, backtest, rebalance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="20240102", help="inclusive YYYYMMDD (default: 20240102)")
    parser.add_argument("--end", default=dt.date.today().strftime("%Y%m%d"),
                        help="inclusive YYYYMMDD (default: today)")
    parser.add_argument(
        "--refresh", action="store_true",
        help="redownload instead of reusing cached source data",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help=f"strategy/backtest YAML (default: {DEFAULT_CONFIG.name})")
    args = parser.parse_args()

    strategy, backtest, rebalance_every = load_config(Path(args.config))
    lookback_days = int(strategy.get("lookback_days", 60))
    holdings = int(strategy.get("holdings", 10))
    if lookback_days < 1 or holdings < 1:
        raise ValueError("lookback_days and holdings must be positive")
    config_fields = {f.name for f in dataclasses.fields(BacktestConfig)}
    config = BacktestConfig(**{k: v for k, v in backtest.items() if k in config_fields})

    params = RunParams(
        start=args.start,
        end=args.end,
        lookback=lookback_days,
        holdings=holdings,
        rebalance=rebalance_every,
        source="real",
        strategy=str(strategy.get("name") or "momentum"),
        config=config,
    )
    result = run_backtest(
        params, PROJECT_ROOT / "reports", PROJECT_ROOT / "data" / "raw",
        trigger="cli", refresh=args.refresh,
    )

    print("数据源: AkShare / 腾讯财经, 前复权日线")
    print(f"股票池: {', '.join(params.symbols)}")
    print(
        f"策略: {params.strategy} top-{params.holdings}, "
        f"lookback={params.lookback}, 调仓间隔={params.rebalance} 交易日"
    )
    print(
        f"有效区间: {result.panel_start:%F} 至 {result.panel_end:%F} "
        f"({result.days} 个交易日)"
    )
    percentage_metrics = {
        "cumulative_return", "annualized_return", "annualized_volatility", "max_drawdown", "turnover_rate"
    }
    for name, value in result.summary.items():
        print(f"{name}: {value:.2%}" if name in percentage_metrics else f"{name}: {value:.4f}")
    print(f"成交笔数: {result.n_trades}")
    print(f"报告目录: reports/{result.run_id}")


if __name__ == "__main__":
    main()
