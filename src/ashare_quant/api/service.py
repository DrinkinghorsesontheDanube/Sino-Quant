"""Read-only query layer over per-run report directories.

The shared pipeline persists one directory per run inside ``reports/``::

    {start}_{end}__{strategy}/
    ├── meta.json     # params, universe, fees, git commit, created_at
    ├── equity.csv    # date-indexed equity curve
    ├── trades.csv    # trade blotter
    └── summary.csv   # metric name / value pairs

The directory name is the *run id*.  All functions return JSON-ready
primitives (dates as ISO strings, NaN replaced by ``None``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ashare_quant.serialize import iso, number

# Run ids are directory names: digits/letters/underscores only, no dots or
# separators, so a crafted id cannot escape the reports directory.
_RUN_ID_RE = re.compile(r"[A-Za-z0-9_]+")


def _run_dir(reports_dir: Path, run_id: str) -> Path | None:
    if not _RUN_ID_RE.fullmatch(run_id):
        return None
    path = reports_dir / run_id
    return path if path.is_dir() and (path / "meta.json").is_file() else None


def _read_meta(run_dir: Path) -> dict[str, object]:
    try:
        return json.loads(run_dir.joinpath("meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def list_runs(reports_dir: Path) -> list[dict[str, object]]:
    """Enumerate backtest runs found on disk, newest period first."""
    runs: list[dict[str, object]] = []
    for meta_path in reports_dir.glob("*/meta.json"):
        meta = _read_meta(meta_path.parent)
        runs.append(
            {
                "run_id": meta_path.parent.name,
                "strategy": str(meta.get("strategy", "")),
                "start": str(meta.get("start", "")),
                "end": str(meta.get("end", "")),
                "source": str(meta.get("source", "")),
                "created_at": str(meta.get("created_at", "")),
                "params": meta.get("params", {}),
                "has_trades": (meta_path.parent / "trades.csv").is_file(),
            }
        )
    return sorted(runs, key=lambda item: (str(item["start"]), str(item["end"])), reverse=True)


def load_summary(reports_dir: Path, run_id: str) -> dict[str, object] | None:
    """Metrics, the daily equity/drawdown curve and the run parameters."""
    run_dir = _run_dir(reports_dir, run_id)
    if run_dir is None:
        return None
    meta = _read_meta(run_dir)

    import pandas as pd

    curve_frame = pd.read_csv(run_dir / "equity.csv", index_col=0, parse_dates=True, encoding="utf-8-sig")
    summary_frame = pd.read_csv(run_dir / "summary.csv", index_col=0, encoding="utf-8-sig")

    peak = curve_frame["equity"].cummax()
    drawdown = (curve_frame["equity"] / peak - 1.0).fillna(0.0)
    curve = [
        {"date": iso(idx), "equity": number(val), "drawdown": number(dd)}
        for idx, val, dd in zip(curve_frame.index, curve_frame["equity"], drawdown, strict=True)
    ]
    metrics = {str(name): number(value) for name, value in summary_frame.iloc[:, 0].items()}
    return {
        "run_id": run_id,
        "strategy": meta.get("strategy", ""),
        "start": meta.get("start", ""),
        "end": meta.get("end", ""),
        "source": meta.get("source", ""),
        "created_at": meta.get("created_at", ""),
        "params": meta.get("params", {}),
        "metrics": metrics,
        "curve": curve,
    }


def load_trades(reports_dir: Path, run_id: str) -> dict[str, object] | None:
    """The full trade blotter for one run."""
    run_dir = _run_dir(reports_dir, run_id)
    if run_dir is None or not (run_dir / "trades.csv").is_file():
        return None

    import pandas as pd

    frame = pd.read_csv(run_dir / "trades.csv", encoding="utf-8-sig")
    columns = ["date", "symbol", "side", "shares", "price", "commission", "tax", "fee"]
    trades = []
    for row in frame.to_dict("records"):
        record: dict[str, object] = {}
        for column in columns:
            value = row.get(column)
            record[column] = number(value) if column not in ("date", "symbol", "side") else (
                str(value) if value is not None else None
            )
        trades.append(record)
    return {"count": len(trades), "trades": trades}
