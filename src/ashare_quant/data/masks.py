"""Assemble a full trading calendar plus tradability masks from raw histories.

Raw per-symbol downloads only contain rows for days that symbol actually
traded.  Dropping mismatched rows would silently shrink the calendar and
distort both the momentum horizon (``lookback`` rows spanning extra wall-clock
days) and the annualised metrics.  Instead, :func:`build_price_panels` keeps
the union calendar of every symbol, forward-fills closes for valuation, and
expresses unavailability as masks the backtester understands:

* ``tradable``  - False on days a symbol has no open print (suspension, gap);
* ``buyable``   - False when the open sits at (or above) the limit-up price;
* ``sellable``  - False when the open sits at (or below) the limit-down price.

Limit bands follow the board the code belongs to (main 10%, ChiNext/STAR 20%,
BSE 30%); ST names carry a narrower band that cannot be detected from the code
alone and are therefore only coarsely covered here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PricePanels:
    """Execution/valuation panels plus masks, all sharing one calendar."""

    open_prices: pd.DataFrame      # fills missing opens with the valuation close; never traded there
    close_prices: pd.DataFrame     # forward-filled valuation closes
    tradable: pd.DataFrame
    buyable: pd.DataFrame
    sellable: pd.DataFrame


def limit_band(symbol: str) -> float:
    """Price-limit fraction for a six-digit A-share code by board."""
    if symbol.startswith(("300", "301", "688", "689")):
        return 0.20
    if symbol.startswith(("43", "83", "87", "88", "92")):
        return 0.30
    return 0.10


def _round_tick(series: pd.Series) -> pd.Series:
    """Round to the 0.01 tick, half-up (A-share quotes are tick-rounded)."""
    return np.floor(series * 100 + 0.5) / 100


def limit_price_bands(prev_close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Limit-up / limit-down reference prices for every symbol and date."""
    up = pd.DataFrame(index=prev_close.index, columns=prev_close.columns, dtype="float64")
    down = up.copy()
    for symbol in prev_close.columns:
        band = limit_band(symbol)
        up[symbol] = _round_tick(prev_close[symbol] * (1 + band))
        down[symbol] = _round_tick(prev_close[symbol] * (1 - band))
    return up, down


def build_price_panels(histories: dict[str, pd.DataFrame]) -> PricePanels:
    """Merge per-symbol histories into calendar-aligned panels with masks."""
    if not histories:
        raise ValueError("no symbol histories supplied")
    open_wide = pd.concat({s: f["open"] for s, f in histories.items()}, axis=1)
    close_wide = pd.concat({s: f["close"] for s, f in histories.items()}, axis=1)
    calendar = open_wide.index.union(close_wide.index).sort_values()
    open_wide = open_wide.reindex(calendar)
    close_wide = close_wide.reindex(calendar)

    valuation_close = close_wide.ffill()
    listed = valuation_close.notna().all(axis=1)
    if not listed.any():
        raise ValueError("no date on which every symbol has at least one observation")
    # Trim the lead-in where late-listed symbols still lack any price.
    valuation_close = valuation_close.loc[listed.idxmax():]
    open_wide = open_wide.loc[listed.idxmax():]

    tradable = open_wide.notna()
    execution_open = open_wide.fillna(valuation_close)

    prev_close = valuation_close.shift(1)
    limit_up, limit_down = limit_price_bands(prev_close)
    buyable = tradable & ~(execution_open >= limit_up)
    sellable = tradable & ~(execution_open <= limit_down)
    return PricePanels(
        open_prices=execution_open,
        close_prices=valuation_close,
        tradable=tradable,
        buyable=buyable,
        sellable=sellable,
    )
