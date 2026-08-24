"""Standard performance statistics for daily equity curves."""

import numpy as np
import pandas as pd


def performance_summary(equity_curve: pd.DataFrame, trading_days: int = 252) -> pd.Series:
    equity = equity_curve["equity"].dropna()
    returns = equity.pct_change().dropna()
    years = max(len(returns) / trading_days, 1 / trading_days)
    cumulative = equity.iloc[-1] / equity.iloc[0] - 1
    annualized = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    drawdown = equity / equity.cummax() - 1
    volatility = returns.std(ddof=1) * np.sqrt(trading_days)
    sharpe = annualized / volatility if volatility > 0 else np.nan
    return pd.Series({
        "cumulative_return": cumulative,
        "annualized_return": annualized,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "max_drawdown": drawdown.min(),
    })
