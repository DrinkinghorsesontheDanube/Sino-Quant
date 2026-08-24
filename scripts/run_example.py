"""Run a self-contained smoke test of the research-to-report workflow."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_quant import DailyBacktester
from ashare_quant.reporting import performance_summary
from ashare_quant.strategies import top_n_momentum_weights


def synthetic_prices() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2021-01-01", periods=300)
    symbols = [f"{code:06d}.SZ" for code in range(1, 31)]
    daily_returns = rng.normal(0.0003, 0.018, size=(len(dates), len(symbols)))
    return pd.DataFrame(20 * np.exp(np.cumsum(daily_returns, axis=0)), index=dates, columns=symbols)


if __name__ == "__main__":
    close = synthetic_prices()
    open_price = close.shift(1).bfill() * 1.001
    weights = top_n_momentum_weights(close, lookback_days=60, holdings=10, rebalance_every=5)
    result = DailyBacktester().run(open_price, close, weights)
    print(performance_summary(result.equity_curve).map(lambda value: f"{value:.2%}" if abs(value) < 10 else f"{value:.2f}"))
    print(f"成交笔数: {len(result.trades)}")
