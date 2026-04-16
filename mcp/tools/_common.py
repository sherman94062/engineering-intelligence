"""Common helpers used across all tool modules.

Pulled out so individual tools stay compact. Importing this module must not
have side effects (e.g. opening DB connections) — do that at call time.
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def get_mcp():
    # Late import to avoid a circular import during server bootstrap.
    from server import mcp
    return mcp


def window_dates(days: int) -> tuple[dt.datetime, dt.datetime]:
    """Return (start, end) UTC datetimes for a rolling `days`-wide window."""
    end = dt.datetime.now(dt.timezone.utc)
    return end - dt.timedelta(days=days), end


def iso(d: dt.datetime | dt.date | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, dt.datetime):
        return d.astimezone(dt.timezone.utc).isoformat()
    return d.isoformat()


def coerce_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert datetimes to ISO strings so MCP JSON serialisation is happy."""
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                k: iso(v) if isinstance(v, (dt.datetime, dt.date)) else v
                for k, v in row.items()
            }
        )
    return out
