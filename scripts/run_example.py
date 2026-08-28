"""Run a self-contained smoke test of the research-to-report workflow."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_quant import DailyBacktester
from ashare_quant.pipeline import synthetic_panel
from ashare_quant.reporting import performance_summary
from ashare_quant.strategies import top_n_momentum_weights

if __name__ == "__main__":
    open_price, close = synthetic_panel()
    weights = top_n_momentum_weights(close, lookback_days=60, holdings=10, rebalance_every=5)
    result = DailyBacktester().run(open_price, close, weights)
    summary = performance_summary(result.equity_curve)
    print(summary.map(lambda value: f"{value:.2%}" if abs(value) < 10 else f"{value:.2f}"))
    print(f"成交笔数: {len(result.trades)}")
