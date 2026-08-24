import pandas as pd

from ashare_quant.strategies import top_n_momentum_weights


def test_top_n_momentum_is_equally_weighted() -> None:
    close = pd.DataFrame({"A": [10, 11, 12], "B": [10, 10, 10], "C": [10, 9, 8]})
    weights = top_n_momentum_weights(close, lookback_days=1, holdings=2, rebalance_every=1)

    assert weights.iloc[-1].sum() == 1.0
    assert weights.iloc[-1]["A"] == 0.5
    assert weights.iloc[-1]["B"] == 0.5


def test_first_rebalance_is_exactly_at_lookback() -> None:
    close = pd.DataFrame(
        {
            "A": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            "B": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        }
    )
    weights = top_n_momentum_weights(close, lookback_days=3, holdings=1, rebalance_every=2)

    signal_rows = [i for i, value in enumerate(weights.sum(axis=1)) if value > 0]
    assert signal_rows == [3, 5, 7, 9]


def test_rejects_non_positive_parameters() -> None:
    close = pd.DataFrame({"A": [10, 11, 12]})
    for kwargs in ({"lookback_days": 0}, {"holdings": 0}, {"rebalance_every": 0}):
        try:
            top_n_momentum_weights(close, **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {kwargs}")
