"""Simple and explainable momentum baseline strategy."""

import pandas as pd


def top_n_momentum_weights(
    adjusted_close: pd.DataFrame, lookback_days: int = 60, holdings: int = 15, rebalance_every: int = 5
) -> pd.DataFrame:
    """Return equal target weights for the strongest trailing-return stocks.

    Input close prices should already be forward-adjusted and filtered to an
    investable universe. Signals are emitted only on rebalance dates.
    """
    if lookback_days < 1 or holdings < 1 or rebalance_every < 1:
        raise ValueError("lookback_days, holdings and rebalance_every must be positive")
    returns = adjusted_close.pct_change(lookback_days)
    weights = pd.DataFrame(0.0, index=adjusted_close.index, columns=adjusted_close.columns)
    for row_number, date in enumerate(weights.index):
        if row_number < lookback_days or row_number % rebalance_every:
            continue
        winners = returns.loc[date].dropna().nlargest(holdings).index
        if len(winners):
            weights.loc[date, winners] = 1 / len(winners)
    return weights.ffill().fillna(0.0)
