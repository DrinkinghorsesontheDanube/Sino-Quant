"""Read-only query layer over the CSV reports written by the backtest scripts.

The scripts persist three siblings per run inside ``reports/``::

    {strategy}_equity_{start}_{end}.csv   equity curve (date-indexed)
    {strategy}_trades_{start}_{end}.csv   trade blotter
    {strategy}_summary_{start}_{end}.csv  metric name / value pairs

A *run id* is ``"{start}_{end}"``, which uniquely identifies the backtest
window produced by the current strategy set. All functions return
JSON-ready primitives (dates as ISO strings, NaN replaced by ``None``).
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from pathlib import Path

RUN_RE = re.compile(r"^(?P<strategy>.+)_equity_(?P<start>\d{8})_(?P<end>\d{8})\.csv$")


def _num(value: object) -> float | None:
    """Convert numeric values to float, mapping NaN/None to None."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso(value: object) -> str | None:
    """Format Timestamp/date/str values as an ISO date or datetime string."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value is not None else None


def list_runs(reports_dir: Path) -> list[dict[str, object]]:
    """Enumerate backtest runs found on disk, newest period first."""
    runs: list[dict[str, object]] = []
    for csv_path in reports_dir.glob("*_equity_*.csv"):
        match = RUN_RE.match(csv_path.name)
        if not match:
            continue
        start, end = match.group("start"), match.group("end")
        trades_csv = csv_path.with_name(
            f"{match.group('strategy')}_trades_{start}_{end}.csv"
        )
        summary_csv = csv_path.with_name(
            f"{match.group('strategy')}_summary_{start}_{end}.csv"
        )
        runs.append(
            {
                "run_id": f"{start}_{end}",
                "strategy": match.group("strategy"),
                "start": start,
                "end": end,
                "has_trades": trades_csv.exists(),
                "created_at": datetime.fromtimestamp(csv_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return sorted(runs, key=lambda item: (str(item["start"]), str(item["end"])), reverse=True)


def _run_paths(reports_dir: Path, run_id: str) -> tuple[str, Path] | None:
    """Resolve a run id back to its (strategy, equity csv) pair."""
    if not re.fullmatch(r"\d{8}_\d{8}", run_id):
        return None
    for csv_path in reports_dir.glob(f"*_equity_{run_id}.csv"):
        match = RUN_RE.match(csv_path.name)
        if match:
            return match.group("strategy"), csv_path
    return None


def load_summary(reports_dir: Path, run_id: str) -> dict[str, object] | None:
    """Metrics plus the daily equity/drawdown curve for one run."""
    resolved = _run_paths(reports_dir, run_id)
    if resolved is None:
        return None
    strategy, equity_csv = resolved
    stem = equity_csv.name[: -len(".csv")]

    import pandas as pd

    curve_frame = pd.read_csv(equity_csv, index_col=0, parse_dates=True, encoding="utf-8-sig")
    summary_frame = pd.read_csv(
        reports_dir / f"{stem.replace('_equity_', '_summary_')}.csv",
        index_col=0,
        encoding="utf-8-sig",
    )

    peak = curve_frame["equity"].cummax()
    drawdown = (curve_frame["equity"] / peak - 1.0).fillna(0.0)
    curve = [
        {"date": _iso(idx), "equity": _num(val), "drawdown": _num(dd)}
        for idx, val, dd in zip(curve_frame.index, curve_frame["equity"], drawdown)
    ]
    metrics = {
        str(name): _num(value) for name, value in summary_frame.iloc[:, 0].items()
    }
    return {
        "run_id": run_id,
        "strategy": strategy,
        "start": run_id.split("_")[0],
        "end": run_id.split("_")[1],
        "metrics": metrics,
        "curve": curve,
    }


def load_trades(reports_dir: Path, run_id: str) -> dict[str, object] | None:
    """The full trade blotter for one run."""
    resolved = _run_paths(reports_dir, run_id)
    if resolved is None:
        return None
    strategy = resolved[0]

    import pandas as pd

    frame = pd.read_csv(
        reports_dir / f"{strategy}_trades_{run_id}.csv",
        encoding="utf-8-sig",
    )
    columns = ["date", "symbol", "side", "shares", "price", "commission", "tax", "fee"]
    trades = []
    for row in frame.to_dict("records"):
        record = {}
        for column in columns:
            value = row.get(column)
            record[column] = _num(value) if column not in ("date", "symbol", "side") else (
                str(row.get(column)) if row.get(column) is not None else None
            )
        trades.append(record)
    return {"count": len(trades), "trades": trades}
