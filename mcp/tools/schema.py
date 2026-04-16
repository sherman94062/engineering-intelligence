"""Schema discovery + ad-hoc read-only SQL."""

from __future__ import annotations

from typing import Any

from db import assert_read_only, run_query
from tools._common import coerce_rows, get_mcp

mcp = get_mcp()


@mcp.tool(
    name="schema__tables",
    description="List every table in the DevLake database with row count.",
)
def tables() -> list[dict[str, Any]]:
    rows = run_query(
        """
        SELECT LOWER(table_name) AS name, table_rows AS approx_rows
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        ORDER BY name
        """
    )
    return coerce_rows(rows)


@mcp.tool(
    name="schema__describe",
    description="Describe a table's columns + types.",
)
def describe(table: str) -> list[dict[str, Any]]:
    rows = run_query(
        """
        SELECT
            column_name AS COLUMN_NAME,
            data_type AS DATA_TYPE,
            is_nullable AS IS_NULLABLE,
            column_key AS COLUMN_KEY,
            column_comment AS COLUMN_COMMENT
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = :table
        ORDER BY ordinal_position
        """,
        {"table": table},
    )
    return coerce_rows(rows)


@mcp.tool(
    name="schema__query",
    description=(
        "Execute a read-only SELECT / WITH / SHOW / DESCRIBE / EXPLAIN. "
        "Any query containing a mutation keyword is rejected."
    ),
)
def query(sql: str, row_limit: int = 500) -> list[dict[str, Any]]:
    assert_read_only(sql)
    limited = _apply_row_limit(sql, row_limit)
    return coerce_rows(run_query(limited))


def _apply_row_limit(sql: str, row_limit: int) -> str:
    trimmed = sql.rstrip().rstrip(";")
    tail = trimmed.lower().split()[-3:]
    if "limit" in tail:
        return trimmed
    return f"{trimmed} LIMIT {int(row_limit)}"
