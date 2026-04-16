"""SQLAlchemy engine + read-only query helpers shared by every MCP tool."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

QUERIES_DIR = Path(__file__).resolve().parent / "queries"

# Anything that could mutate the database. The `schema__query` tool rejects
# queries containing these tokens (case-insensitive, word-boundary).
FORBIDDEN_SQL_TOKENS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "replace", "call", "use",
    "rename", "merge", "load",
}


@lru_cache(maxsize=1)
def engine() -> Engine:
    db_url = os.environ["DB_URL"]
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        future=True,
        connect_args={"read_default_group": "client"} if "mysql" in db_url else {},
    )


def run_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a SELECT and return rows as list[dict]."""
    with engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in result]


def assert_read_only(sql: str) -> None:
    """Reject SQL containing any mutation keyword."""
    lowered = " " + re.sub(r"\s+", " ", sql.lower()) + " "
    for tok in FORBIDDEN_SQL_TOKENS:
        if f" {tok} " in lowered:
            raise ValueError(f"Rejecting query: contains forbidden token '{tok}'")
    if not re.search(r"\bselect\b|\bwith\b|\bshow\b|\bdescribe\b|\bexplain\b", lowered):
        raise ValueError("Rejecting query: not a SELECT/WITH/SHOW/DESCRIBE/EXPLAIN statement")


def load_sql(filename: str, key: str | None = None) -> str:
    """Load a SQL snippet from mcp/queries/.

    Files can contain multiple named snippets separated by lines of the form
    ``-- name: <key>``. Passing ``key`` returns just that snippet; omitting it
    returns the full file.
    """
    path = QUERIES_DIR / filename
    text_content = path.read_text()
    if key is None:
        return text_content
    pattern = re.compile(r"--\s*name:\s*(\S+)\s*\n(.*?)(?=\n--\s*name:|\Z)", re.S)
    for match in pattern.finditer(text_content):
        if match.group(1).strip() == key:
            return match.group(2).strip()
    raise KeyError(f"No SQL snippet '{key}' in {filename}")


def synth_filter(include_synthetic: bool, alias: str | None = None) -> str:
    """Return a SQL fragment to append to WHERE clauses.

    When include_synthetic is True returns an empty string (no filter). When
    False, restricts to real rows (source IS NULL or source != 'synthetic').
    """
    if include_synthetic:
        return ""
    col = f"{alias}.source" if alias else "source"
    return f" AND ({col} IS NULL OR {col} != 'synthetic')"
