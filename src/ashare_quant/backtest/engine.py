"""A deliberately small, auditable A-share long-only daily backtester."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 1_000_000
    commission_rate: float = 0.0003
    minimum_commission: float = 5.0
    stamp_duty_rate: float = 0.0005  # applies to sell orders only
    slippage_rate: float = 0.0005
    lot_size: int = 100


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame


class DailyBacktester:
    """Execute yesterday's target weights at today's open.

    `target_weights` must use the same index/columns as price data.  A target
    generated at date T is executed at T+1's open, preventing close-price
    look-ahead bias.  The caller must set unavailable stocks to False in
    `tradable`; limit-up/down and suspension rules can therefore be supplied
    from a market-data layer without being hidden in this engine.
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(
        self,
        open_prices: pd.DataFrame,
        close_prices: pd.DataFrame,
        target_weights: pd.DataFrame,
        tradable: pd.DataFrame | None = None,
    ) -> BacktestResult:
        self._validate_inputs(open_prices, close_prices, target_weights)
        dates, symbols = open_prices.index, open_prices.columns
        tradable = (
            pd.DataFrame(True, index=dates, columns=symbols)
            if tradable is None
            else tradable.reindex(index=dates, columns=symbols).fillna(False).astype(bool)
        )

        cash = self.config.initial_cash
        shares = pd.Series(0, index=symbols, dtype="int64")
        buy_date = pd.Series(pd.NaT, index=symbols, dtype="datetime64[ns]")
        records: list[dict[str, object]] = []
        trades: list[dict[str, object]] = []

        for i, date in enumerate(dates):
            # The signal is known only after the previous close.
            if i > 0:
                targets = target_weights.iloc[i - 1].clip(lower=0).fillna(0)
                targets = targets / targets.sum() if targets.sum() > 0 else targets
                cash, shares, buy_date = self._rebalance(
                    date, open_prices.loc[date], targets, tradable.loc[date], cash, shares, buy_date, trades
                )

            market_value = float((shares * close_prices.loc[date]).sum())
            records.append(
                {"date": date, "cash": cash, "market_value": market_value, "equity": cash + market_value}
            )

        equity_curve = pd.DataFrame(records).set_index("date")
        equity_curve["daily_return"] = equity_curve["equity"].pct_change().fillna(0.0)
        return BacktestResult(equity_curve=equity_curve, trades=pd.DataFrame(trades))

    def _rebalance(
        self, date: pd.Timestamp, prices: pd.Series, targets: pd.Series, tradable: pd.Series,
        cash: float, shares: pd.Series, buy_date: pd.Series, trades: list[dict[str, object]],
    ) -> tuple[float, pd.Series, pd.Series]:
        current_equity = cash + float((shares * prices).sum())
        desired_value = targets * current_equity
        desired_shares = (desired_value / (prices * (1 + self.config.slippage_rate))).fillna(0)
        desired_shares = (desired_shares // self.config.lot_size * self.config.lot_size).astype("int64")

        # Sell first. T+1 prevents selling a position bought today, although
        # same-day buy/sell does not normally arise with one daily rebalance.
        for symbol in shares.index:
            quantity = max(0, shares[symbol] - desired_shares[symbol])
            if quantity and tradable[symbol] and buy_date[symbol] < date:
                proceeds = quantity * prices[symbol] * (1 - self.config.slippage_rate)
                fee = max(proceeds * self.config.commission_rate, self.config.minimum_commission)
                tax = proceeds * self.config.stamp_duty_rate
                cash += proceeds - fee - tax
                shares[symbol] -= quantity
                trades.append({"date": date, "symbol": symbol, "side": "SELL", "shares": quantity, "price": prices[symbol], "fee": fee + tax})

        # Buy in descending target priority. Cash is never allowed below zero.
        for symbol in targets.sort_values(ascending=False).index:
            quantity = max(0, desired_shares[symbol] - shares[symbol])
            if not quantity or not tradable[symbol] or not np.isfinite(prices[symbol]):
                continue
            unit_cost = prices[symbol] * (1 + self.config.slippage_rate)
            affordable = int(cash / (unit_cost * (1 + self.config.commission_rate)))
            quantity = min(quantity, affordable // self.config.lot_size * self.config.lot_size)
            if quantity <= 0:
                continue
            gross = quantity * unit_cost
            fee = max(gross * self.config.commission_rate, self.config.minimum_commission)
            while quantity >= self.config.lot_size and gross + fee > cash:
                quantity -= self.config.lot_size
                gross = quantity * unit_cost
                fee = max(gross * self.config.commission_rate, self.config.minimum_commission)
            if quantity < self.config.lot_size:
                continue
            cash -= gross + fee
            shares[symbol] += quantity
            buy_date[symbol] = date
            trades.append({"date": date, "symbol": symbol, "side": "BUY", "shares": quantity, "price": prices[symbol], "fee": fee})
        return cash, shares, buy_date

    @staticmethod
    def _validate_inputs(*frames: pd.DataFrame) -> None:
        reference = frames[0]
        if reference.empty or not reference.index.is_monotonic_increasing:
            raise ValueError("price index must be non-empty and ordered by date")
        for frame in frames[1:]:
            if not reference.index.equals(frame.index) or not reference.columns.equals(frame.columns):
                raise ValueError("all inputs must have identical dates and symbols")
        if (reference <= 0).any().any():
            raise ValueError("open prices must be positive")
