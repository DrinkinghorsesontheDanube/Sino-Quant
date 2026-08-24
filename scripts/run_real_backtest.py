"""Download a real A-share sample and run the momentum baseline end to end."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
# Allows a self-contained installation made with `pip install --target .vendor`.
if (PROJECT_ROOT / ".vendor").exists():
    sys.path.insert(0, str(PROJECT_ROOT / ".vendor"))

from ashare_quant import DailyBacktester
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


def build_price_panels(histories: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only dates where every selected stock has a valid open and close."""
    open_prices = pd.concat({symbol: frame["open"] for symbol, frame in histories.items()}, axis=1)
    close_prices = pd.concat({symbol: frame["close"] for symbol, frame in histories.items()}, axis=1)
    valid_dates = open_prices.notna().all(axis=1) & close_prices.notna().all(axis=1)
    return open_prices.loc[valid_dates], close_prices.loc[valid_dates]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="20240102", help="inclusive YYYYMMDD (default: 20240102)")
    parser.add_argument("--end", default="20260821", help="inclusive YYYYMMDD (default: 20260821)")
    parser.add_argument("--refresh", action="store_true", help="redownload instead of reusing cached source data")
    args = parser.parse_args()

    histories = download_daily_history(
        DEFAULT_SYMBOLS, args.start, args.end, PROJECT_ROOT / "data" / "raw", refresh=args.refresh
    )
    open_prices, close_prices = build_price_panels(histories)
    if len(close_prices) <= 60:
        raise RuntimeError(f"Only {len(close_prices)} common trading days; at least 61 are required.")

    weights = top_n_momentum_weights(close_prices, lookback_days=60, holdings=10, rebalance_every=5)
    result = DailyBacktester().run(open_prices, close_prices, weights)
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
    print(f"有效区间: {close_prices.index[0]:%F} 至 {close_prices.index[-1]:%F} ({len(close_prices)} 个交易日)")
    percentage_metrics = {
        "cumulative_return", "annualized_return", "annualized_volatility", "max_drawdown"
    }
    for name, value in summary.items():
        print(f"{name}: {value:.2%}" if name in percentage_metrics else f"{name}: {value:.4f}")
    print(f"成交笔数: {len(result.trades)}")


if __name__ == "__main__":
    main()
