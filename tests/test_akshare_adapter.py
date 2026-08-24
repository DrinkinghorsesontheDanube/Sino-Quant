import sys
import types

import pandas as pd
import pytest

from ashare_quant.data.akshare import _exchange_prefix, _normalize_history


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


def test_exchange_prefix() -> None:
    assert _exchange_prefix("600000") == "sh"
    assert _exchange_prefix("688001") == "sh"
    assert _exchange_prefix("000001") == "sz"
    assert _exchange_prefix("300750") == "sz"
    assert _exchange_prefix("430047") == "bj"
    assert _exchange_prefix("830799") == "bj"


@pytest.fixture()
def fake_akshare(monkeypatch):
    """Provide a stub ``akshare`` module recording every download call."""
    module = types.ModuleType("akshare")
    calls: list[tuple] = []

    def stock_zh_a_hist_tx(*args, **kwargs):
        calls.append((args, kwargs))
        return pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03"],
                "open": [10.0, 10.2],
                "close": [10.5, 10.8],
                "volume": [100, 120],
            }
        )

    module.stock_zh_a_hist_tx = stock_zh_a_hist_tx
    monkeypatch.setitem(sys.modules, "akshare", module)
    return calls


def test_download_retries_transient_failure(monkeypatch, tmp_path) -> None:
    module = types.ModuleType("akshare")
    attempts = {"count": 0}

    def flaky(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionError("transient network failure")
        return pd.DataFrame(
            {"date": ["2024-01-02"], "open": [10.0], "close": [10.5], "volume": [100]}
        )

    module.stock_zh_a_hist_tx = flaky
    monkeypatch.setitem(sys.modules, "akshare", module)

    from ashare_quant.data.akshare import download_daily_history

    histories = download_daily_history(["000001"], "20240102", "20240105", tmp_path, adjust="qfq")
    assert attempts["count"] == 2
    assert "000001" in histories
    assert histories["000001"].loc[pd.Timestamp("2024-01-02"), "close"] == 10.5


def test_download_reuses_cache(monkeypatch, tmp_path, fake_akshare) -> None:
    from ashare_quant.data.akshare import download_daily_history

    download_daily_history(["000001"], "20240102", "20240105", tmp_path, adjust="qfq")
    download_daily_history(["000001"], "20240102", "20240105", tmp_path, adjust="qfq")
    # The cached file is reused on the second call: exactly one download.
    assert len(fake_akshare) == 1
