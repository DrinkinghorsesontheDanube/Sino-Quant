"""Download daily A-share prices from AkShare and keep an auditable cache."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

_REQUIRED_COLUMNS = ["open", "close"]
_COLUMN_MAP = {"日期": "date", "开盘": "open", "收盘": "close", "成交量": "volume"}


def _exchange_prefix(symbol: str) -> str:
    """Map a six-digit code to the Tencent exchange prefix (sh/sz/bj).

    Mirrors AkShare's own ``_normalize_tx_symbol`` prefix sets so the two
    layers never disagree.
    """
    if symbol.startswith(("600", "601", "603", "605", "688", "900")):
        return "sh"
    if symbol.startswith(("430", "440", "830", "831", "832", "833", "839")):
        return "bj"
    return "sz"


def _fetch_with_retry(fetch, retries: int = 3, backoff: float = 1.0):
    """Run ``fetch`` up to ``retries`` times with exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return fetch()
        except Exception as exc:  # transient network errors should not kill a run
            last_error = exc
            if attempt < retries - 1:
                time.sleep(backoff * (2**attempt))
    assert last_error is not None
    raise last_error


def download_daily_history(
    symbols: list[str],
    start_date: str,
    end_date: str,
    cache_dir: Path,
    *,
    adjust: str = "qfq",
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Return forward-adjusted daily histories keyed by six-digit stock code.

    Each source response is saved exactly as normalized here under ``cache_dir``.
    Existing cached files are reused unless ``refresh`` is set.  A symbol with no
    usable observations raises an error rather than silently entering a backtest.
    """
    try:
        import akshare as ak
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError("AkShare is required; install with `pip install -e '.[data]'`.") from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    histories: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        cache_file = cache_dir / f"{symbol}_{start_date}_{end_date}_{adjust}.csv"
        if cache_file.exists() and not refresh:
            frame = pd.read_csv(cache_file)
            histories[symbol] = _normalize_history(frame, symbol)
        else:
            # Tencent's interface is used here because it is publicly accessible
            # without a token and has been more reliable than the Eastmoney route
            # in proxy-restricted environments.  It returns English field names.
            # Bind the loop variable explicitly so the retry lambda cannot
            # capture a late-bound value if the loop ever changes shape.
            frame = _fetch_with_retry(
                lambda symbol=symbol: ak.stock_zh_a_hist_tx(
                    symbol=_exchange_prefix(symbol) + symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                    timeout=30,
                )
            )
            frame = _normalize_history(frame, symbol)
            frame.reset_index().to_csv(cache_file, index=False, encoding="utf-8-sig")
            histories[symbol] = frame
    return histories


def _normalize_history(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Convert AkShare's Chinese-labelled response to a stable internal schema."""
    normalized = frame.rename(columns=_COLUMN_MAP).copy()
    missing = set(_REQUIRED_COLUMNS) - set(normalized.columns)
    if missing:
        raise ValueError(f"{symbol}: missing required source columns: {sorted(missing)}")
    if "date" not in normalized:
        raise ValueError(f"{symbol}: source response has no date column")
    normalized["date"] = pd.to_datetime(normalized["date"])
    normalized = normalized.drop_duplicates("date").sort_values("date")
    normalized = normalized.set_index("date")
    for column in _REQUIRED_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.loc[(normalized["open"] > 0) & (normalized["close"] > 0)]
    if normalized.empty:
        raise ValueError(f"{symbol}: no usable daily data returned")
    return normalized
