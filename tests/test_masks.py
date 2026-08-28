import pandas as pd

from ashare_quant.data.masks import build_price_panels, limit_band


def _history(dates, closes, opens=None) -> pd.DataFrame:
    frame = pd.DataFrame({"close": closes}, index=dates)
    frame["open"] = opens if opens is not None else closes
    return frame


def test_limit_band_by_board() -> None:
    assert limit_band("600519") == 0.10
    assert limit_band("000001") == 0.10
    assert limit_band("300750") == 0.20
    assert limit_band("301236") == 0.20
    assert limit_band("688981") == 0.20
    assert limit_band("832000") == 0.30


def test_suspension_keeps_calendar_row_and_ffills_valuation() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    histories = {
        "600000": _history(dates, [10.0, 10.0, 10.0, 10.0]),
        # 000001 is suspended on day 3: no open/close print at all.
        "000001": _history(dates.delete(2), [20.0, 20.0, 20.0]),
    }
    panels = build_price_panels(histories)

    assert list(panels.close_prices.index) == list(dates)  # row is kept
    assert panels.close_prices["000001"].iloc[2] == 20.0   # ffilled for valuation
    assert not panels.tradable["000001"].iloc[2]           # but not tradable
    assert panels.tradable["600000"].all()


def test_limit_up_open_blocks_buy_only() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    # prev_close 10.0, day-2 open at the 10% limit-up tick (11.00).
    histories = {"600000": _history(dates, [10.0, 10.0, 10.0], [10.0, 11.0, 10.0])}
    panels = build_price_panels(histories)

    assert not panels.buyable["600000"].iloc[1]
    assert panels.sellable["600000"].iloc[1]  # selling into limit-up is fine
    assert panels.buyable["600000"].iloc[2]   # next day resumes normally


def test_limit_down_open_blocks_sell_only() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    histories = {"600000": _history(dates, [10.0, 10.0, 10.0], [10.0, 9.0, 10.0])}
    panels = build_price_panels(histories)

    assert not panels.sellable["600000"].iloc[1]
    assert panels.buyable["600000"].iloc[1]


def test_limit_band_applies_board_specific_threshold() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    # ChiNext band is 20%: an 11.0 open (10% up) is still buyable.
    histories = {"300750": _history(dates, [10.0, 10.0, 10.0], [10.0, 11.0, 10.0])}
    panels = build_price_panels(histories)
    assert panels.buyable["300750"].iloc[1]

    # ...but 12.0 (20% up) is the limit tick and blocks the buy.
    histories = {"300750": _history(dates, [10.0, 10.0, 10.0], [10.0, 12.0, 10.0])}
    panels = build_price_panels(histories)
    assert not panels.buyable["300750"].iloc[1]


def test_leading_rows_without_full_data_are_trimmed() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    # 600519 only has data from day 2 onward; day 1 must be dropped entirely.
    histories = {
        "600000": _history(dates, [10.0, 10.0, 10.0, 10.0]),
        "600519": _history(dates[1:], [1700.0, 1710.0, 1705.0]),
    }
    panels = build_price_panels(histories)

    assert list(panels.close_prices.index) == list(dates[1:])
    assert panels.tradable.all().all()
