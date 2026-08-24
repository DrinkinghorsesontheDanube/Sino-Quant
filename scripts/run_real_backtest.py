"""Download a real A-share sample and run the momentum baseline end to end."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
# Allows a self-contained installation made with `pip install --target .vendor`.
if (PROJECT_ROOT / ".vendor").exists():
    sys.path.insert(0, str(PROJECT_ROOT / ".vendor"))

from ashare_quant import BacktestConfig, DailyBacktester
from ashare_quant.data import download_daily_history
from ashare_quant.reporting import performance_summary
from ashare_quant.strategies import top_n_momentum_weights

# Large, liquid A-share names across banking, consumer, industry, energy and tech.
# The explicit list makes the validation universe stable and the run reproducible.
DEFAULT_SYMBOLS = [
    "000001", "000333", "000651", "000858", "002594",
    "300750", "600000", "600036", "600519", "601318",
    "601398", "601857", "601888", "601899", "603288",
]

DEFAULT_CONFIG = PROJECT_ROOT / "config" / "momentum_weekly.example.yaml"
_WEEKLY_CADENCE = {"weekly": 5, "monthly": 21}


def load_config(path: Path) -> tuple[dict[str, object], dict[str, object], int]:
    """Load the copyable strategy/backtest YAML into run parameters."""
    import yaml

    with path.open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    strategy = cfg.get("strategy") or {}
    backtest = cfg.get("backtest") or {}

    rebalance = strategy.get("rebalance", 5)
    if isinstance(rebalance, str):
        rebalance = _WEEKLY_CADENCE.get(rebalance.strip().lower(), 5)
    if not isinstance(rebalance, int) or rebalance < 1:
        raise ValueError(f"invalid rebalance cadence in {path}: {strategy.get('rebalance')!r}")

    return strategy, backtest, rebalance


def build_price_panels(histories: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only dates where every selected stock has a valid open and close."""
    open_prices = pd.concat({symbol: frame["open"] for symbol, frame in histories.items()}, axis=1)
    close_prices = pd.concat({symbol: frame["close"] for symbol, frame in histories.items()}, axis=1)
    valid_dates = open_prices.notna().all(axis=1) & close_prices.notna().all(axis=1)
    return open_prices.loc[valid_dates], close_prices.loc[valid_dates]


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

    histories = download_daily_history(
        DEFAULT_SYMBOLS, args.start, args.end, PROJECT_ROOT / "data" / "raw", refresh=args.refresh
    )
    open_prices, close_prices = build_price_panels(histories)
    if len(close_prices) <= lookback_days:
        raise RuntimeError(
            f"Only {len(close_prices)} common trading days; at least {lookback_days + 1} are required."
        )

    weights = top_n_momentum_weights(
        close_prices, lookback_days=lookback_days, holdings=holdings, rebalance_every=rebalance_every
    )
    result = DailyBacktester(config).run(open_prices, close_prices, weights)
    summary = performance_summary(result.equity_curve)

    processed_dir = PROJECT_ROOT / "data" / "processed"
    report_dir = PROJECT_ROOT / "reports"
    processed_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"{close_prices.index[0]:%Y%m%d}_{close_prices.index[-1]:%Y%m%d}"
    close_prices.to_csv(processed_dir / f"real_close_{suffix}.csv", encoding="utf-8-sig")
    open_prices.to_csv(processed_dir / f"real_open_{suffix}.csv", encoding="utf-8-sig")
    result.equity_curve.to_csv(report_dir / f"real_momentum_equity_{suffix}.csv", encoding="utf-8-sig")
    result.trades.to_csv(report_dir / f"real_momentum_trades_{suffix}.csv", index=False, encoding="utf-8-sig")
    summary.to_frame("value").to_csv(report_dir / f"real_momentum_summary_{suffix}.csv", encoding="utf-8-sig")

    print("数据源: AkShare / 腾讯财经, 前复权日线")
    print(f"股票池: {', '.join(DEFAULT_SYMBOLS)}")
    print(f"策略: 动量 top-{holdings}, lookback={lookback_days}, 调仓间隔={rebalance_every} 交易日")
    print(
        f"有效区间: {close_prices.index[0]:%F} 至 {close_prices.index[-1]:%F} "
        f"({len(close_prices)} 个交易日)"
    )
    percentage_metrics = {
        "cumulative_return", "annualized_return", "annualized_volatility", "max_drawdown", "turnover_rate"
    }
    for name, value in summary.items():
        print(f"{name}: {value:.2%}" if name in percentage_metrics else f"{name}: {value:.4f}")
    print(f"成交笔数: {len(result.trades)}")


if __name__ == "__main__":
    main()
