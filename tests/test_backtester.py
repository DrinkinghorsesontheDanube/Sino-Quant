import pandas as pd

from ashare_quant.backtest import DailyBacktester


def test_signal_executes_next_trading_day() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame({"000001.SZ": [10.0, 10.0, 10.0]}, index=dates)
    targets = pd.DataFrame({"000001.SZ": [1.0, 1.0, 1.0]}, index=dates)
    result = DailyBacktester().run(prices, prices, targets)

    assert result.trades.iloc[0]["date"] == dates[1]
    assert result.trades.iloc[0]["shares"] % 100 == 0
    assert result.equity_curve.iloc[0]["market_value"] == 0
