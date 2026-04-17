"""Common helpers used across all tool modules.

Pulled out so individual tools stay compact. Importing this module must not
have side effects (e.g. opening DB connections) — do that at call time.
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def get_mcp():
    """Return the shared FastMCP instance.

    Historically a late-bound `from server import mcp` lived here to avoid a
    circular import; that pattern produced two distinct FastMCP instances
    when server.py ran as __main__ (tools registered on one, HTTP served
    from the other). Now the instance is defined in `mcp_instance.py` and
    both server.py and every tool module import it from the same place.
    """
    from mcp_instance import mcp
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
