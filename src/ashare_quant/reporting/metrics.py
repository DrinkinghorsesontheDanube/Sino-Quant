"""Standard performance statistics for daily equity curves."""

import numpy as np
import pandas as pd


def performance_summary(equity_curve: pd.DataFrame, trading_days: int = 252) -> pd.Series:
    """Summarise an equity curve produced by :class:`DailyBacktester`.

    ``turnover_rate`` is the annualised one-sided turnover: the average of
    gross buy and sell value over the period, divided by the mean equity and
    annualised.  It is ``NaN`` when the curve lacks ``buy_value``/``sell_value``
    columns (for example a manually built curve).
    """
    equity = equity_curve["equity"].dropna()
    returns = equity.pct_change().dropna()
    years = max(len(returns) / trading_days, 1 / trading_days)
    cumulative = equity.iloc[-1] / equity.iloc[0] - 1
    annualized = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    drawdown = equity / equity.cummax() - 1
    volatility = returns.std(ddof=1) * np.sqrt(trading_days)
    sharpe = annualized / volatility if volatility > 0 else np.nan

    if {"buy_value", "sell_value"}.issubset(equity_curve.columns):
        traded_value = (equity_curve["buy_value"].sum() + equity_curve["sell_value"].sum()) / 2
        turnover_rate = traded_value / equity.mean() / years
    else:
        turnover_rate = np.nan

    return pd.Series({
        "cumulative_return": cumulative,
        "annualized_return": annualized,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": drawdown.min(),
        "turnover_rate": turnover_rate,
    })
