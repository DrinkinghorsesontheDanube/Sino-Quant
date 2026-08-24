import numpy as np
import pandas as pd
import pytest

from ashare_quant.reporting import performance_summary


def _curve(equity: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"equity": equity}, index=pd.bdate_range("2024-01-02", periods=len(equity)))


def test_drawdown_and_returns() -> None:
    summary = performance_summary(_curve([100.0, 120.0, 90.0, 130.0]), trading_days=252)

    assert summary["max_drawdown"] == pytest.approx(90.0 / 120.0 - 1)
    assert summary["cumulative_return"] == pytest.approx(0.30)
    years = 3 / 252
    assert summary["annualized_return"] == pytest.approx(1.3 ** (1 / years) - 1)


def test_flat_curve_has_no_sharpe() -> None:
    summary = performance_summary(_curve([100.0, 100.0, 100.0, 100.0]), trading_days=252)

    assert np.isnan(summary["sharpe_ratio"])  # zero volatility


def test_turnover_rate_is_annualised_one_sided() -> None:
    curve = pd.DataFrame(
        {
            "equity": [1000.0, 1000.0, 1000.0, 1000.0],
            "buy_value": [100.0, 0.0, 0.0, 0.0],
            "sell_value": [0.0, 100.0, 0.0, 0.0],
        },
        index=pd.bdate_range("2024-01-02", periods=4),
    )
    summary = performance_summary(curve, trading_days=252)

    traded = (100.0 + 100.0) / 2
    years = 3 / 252
    assert summary["turnover_rate"] == pytest.approx(traded / 1000.0 / years)


def test_turnover_is_nan_without_trade_columns() -> None:
    summary = performance_summary(_curve([100.0, 110.0]), trading_days=252)

    assert np.isnan(summary["turnover_rate"])
