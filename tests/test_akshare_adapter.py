import pandas as pd

from ashare_quant.data.akshare import _normalize_history


def test_normalize_akshare_daily_history() -> None:
    source = pd.DataFrame(
        {
            "日期": ["2024-01-03", "2024-01-02", "2024-01-03"],
            "开盘": [11.0, 10.0, 11.0],
            "收盘": [11.5, 10.5, 11.5],
            "成交量": [100, 100, 100],
        }
    )

    result = _normalize_history(source, "000001")

    assert list(result.columns) == ["open", "close", "volume"]
    assert list(result.index.strftime("%F")) == ["2024-01-02", "2024-01-03"]
    assert result.loc[pd.Timestamp("2024-01-02"), "close"] == 10.5
