"""JSON-ready primitives shared by the pipeline outputs and the API layer."""

from __future__ import annotations

import math
from datetime import date, datetime


def number(value: object) -> float | None:
    """Convert numeric values to float, mapping NaN/inf/None to None."""
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def iso(value: object) -> str | None:
    """Format Timestamp/date/str values as an ISO date or datetime string."""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value is not None else None
