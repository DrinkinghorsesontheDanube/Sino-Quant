import numpy as np
import pandas as pd
import pytest

from ashare_quant.backtest import BacktestConfig, DailyBacktester


def _single(dates, values, column="000001.SZ") -> pd.DataFrame:
    return pd.DataFrame({column: values}, index=dates)


def test_signal_executes_next_trading_day() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 1.0])
    result = DailyBacktester().run(prices, prices, targets)

    assert result.trades.iloc[0]["date"] == dates[1]
    assert result.trades.iloc[0]["shares"] % 100 == 0
    assert result.equity_curve.iloc[0]["market_value"] == 0


def test_buy_then_exit_never_trades_same_day() -> None:
    # Buy executed at day-2 open from the day-1 signal; the exit signal from
    # day-2 close is executed at day-3 open, so no same-day buy+sell (T+1).
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 0.0])
    result = DailyBacktester().run(prices, prices, targets)

    assert list(result.trades["side"]) == ["BUY", "SELL"]
    assert result.trades.iloc[0]["date"] < result.trades.iloc[1]["date"]


def test_t_plus_one_blocks_same_day_sell() -> None:
    # Direct guard check: a position bought today must not be sold today.
    date = pd.Timestamp("2024-01-03")
    prices = pd.Series([10.0], index=["A"])
    targets = pd.Series([0.0], index=["A"])  # exit signal
    tradable = pd.Series([True], index=["A"])
    buyable = pd.Series([True], index=["A"])
    sellable = pd.Series([True], index=["A"])
    shares = pd.Series([100], index=["A"], dtype="int64")
    buy_date = pd.Series([date], index=["A"], dtype="datetime64[ns]")  # bought TODAY
    trades: list[dict[str, object]] = []

    cash, out_shares, _, _, sell_value = DailyBacktester()._rebalance(
        date, prices, targets, tradable, buyable, sellable, 0.0, shares, buy_date, trades
    )
    assert out_shares["A"] == 100  # sell blocked by T+1
    assert sell_value == 0.0
    assert trades == []


def test_limit_up_blocks_buy_but_allows_sell() -> None:
    # Buy signal on day 1 executes day 2; day 2 is limit-up so the buy is blocked.
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 1.0])
    buyable = _single(dates, [True, False, True])
    result = DailyBacktester().run(prices, prices, targets, buyable=buyable)

    buys = result.trades[result.trades["side"] == "BUY"]
    # Day-3 buys come from the day-2 signal (still all-in), so the position
    # simply enters one day late instead of never.
    assert list(buys["date"]) == [dates[2]]
    assert result.equity_curve["cash"].iloc[1] == 1_000_000.0


def test_limit_down_blocks_sell_but_allows_buy() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 0.0])
    sellable = _single(dates, [True, True, False])  # day-3 open is limit-down
    result = DailyBacktester().run(prices, prices, targets, sellable=sellable)

    sells = result.trades[result.trades["side"] == "SELL"]
    assert sells.empty  # the exit would execute on the blocked day, position is kept
    buys = result.trades[result.trades["side"] == "BUY"]
    assert not buys.empty


def test_nan_close_price_rejected_at_validation() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    open_prices = _single(dates, [10.0, 10.0, 10.0])
    close_prices = _single(dates, [10.0, 10.0, np.nan])
    targets = _single(dates, [1.0, 1.0, 1.0])

    with pytest.raises(ValueError, match="close prices"):
        DailyBacktester().run(open_prices, close_prices, targets)


def test_stamp_duty_applies_to_sells_only() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 0.0])
    result = DailyBacktester().run(prices, prices, targets)

    buy, sell = result.trades.iloc[0], result.trades.iloc[1]
    assert buy["side"] == "BUY" and buy["tax"] == 0.0
    assert sell["side"] == "SELL"
    proceeds = sell["shares"] * sell["price"] * (1 - 0.0005)
    assert sell["tax"] == pytest.approx(proceeds * 0.0005)
    assert sell["fee"] == pytest.approx(sell["commission"] + sell["tax"])


def test_minimum_commission_floor() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = _single(dates, [5.0, 5.0])
    targets = _single(dates, [1.0, 1.0])
    result = DailyBacktester(BacktestConfig(initial_cash=5000)).run(prices, prices, targets)

    trade = result.trades.iloc[0]
    assert trade["commission"] == 5.0  # gross * 0.0003 < 5 -> floor applies


def test_slippage_makes_execution_worse_than_open() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = _single(dates, [10.0, 10.0])
    targets = _single(dates, [1.0, 1.0])
    config = BacktestConfig(
        initial_cash=10_000, commission_rate=0.0, minimum_commission=0.0, slippage_rate=0.01
    )
    result = DailyBacktester(config).run(prices, prices, targets)

    # 900 shares bought at effective price 10 * 1.01 = 10.1 -> cash 10_000 - 9_090.
    assert result.equity_curve.iloc[-1]["cash"] == pytest.approx(10_000 - 900 * 10.1)
    assert result.equity_curve.iloc[-1]["equity"] == pytest.approx(10_000 - 900 * 0.1)


def test_tradable_mask_blocks_unavailable_stocks() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = _single(dates, [10.0, 10.0])
    targets = _single(dates, [1.0, 1.0])
    tradable = _single(dates, [False, False])
    result = DailyBacktester().run(prices, prices, targets, tradable)

    assert result.trades.empty
    assert result.equity_curve["cash"].iloc[-1] == 1_000_000.0


def test_nan_open_price_rejected_at_validation() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    open_prices = _single(dates, [10.0, np.nan, 10.0])
    close_prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 1.0])

    with pytest.raises(ValueError, match="missing values"):
        DailyBacktester().run(open_prices, close_prices, targets)


def test_cash_never_negative_under_turnover() -> None:
    dates = pd.bdate_range("2024-01-02", periods=8)
    rng = np.random.default_rng(7)
    prices = pd.DataFrame(
        20 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, size=(len(dates), 4)), axis=0)),
        index=dates,
        columns=[f"{c:06d}" for c in range(4)],
    )
    targets = pd.DataFrame(
        np.eye(len(dates), 4), index=dates, columns=prices.columns
    )  # rotate the full position each day
    result = DailyBacktester().run(prices, prices, targets)

    assert (result.equity_curve["cash"] >= -1e-9).all()


def test_equity_curve_tracks_turnover_values() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = _single(dates, [10.0, 10.0, 10.0])
    targets = _single(dates, [1.0, 1.0, 0.0])
    result = DailyBacktester().run(prices, prices, targets)

    curve = result.equity_curve
    assert {"buy_value", "sell_value"}.issubset(curve.columns)
    # Buy executes on day 2; sell on day 3 (exit signal).
    assert curve["buy_value"].iloc[1] > 0 and curve["buy_value"].iloc[2] == 0
    assert curve["sell_value"].iloc[2] > 0
    # No trading activity on the first day.
    assert curve["buy_value"].iloc[0] == 0 and curve["sell_value"].iloc[0] == 0
