import pandas as pd

from ashare_quant.strategies import top_n_momentum_weights


def test_top_n_momentum_is_equally_weighted() -> None:
    close = pd.DataFrame({"A": [10, 11, 12], "B": [10, 10, 10], "C": [10, 9, 8]})
    weights = top_n_momentum_weights(close, lookback_days=1, holdings=2, rebalance_every=1)

    assert weights.iloc[-1].sum() == 1.0
    assert weights.iloc[-1]["A"] == 0.5
    assert weights.iloc[-1]["B"] == 0.5
