"""Synthetic-layer introspection + toggle helpers."""

from __future__ import annotations

from typing import Any

from db import run_query
from tools._common import coerce_rows, get_mcp

mcp = get_mcp()

TABLES_OF_INTEREST = [
    "accounts",
    "commits",
    "pull_requests",
    "pull_request_comments",
    "cicd_pipelines",
    "issues",
]


@mcp.tool(
    name="synthetic__status",
    description="Row counts split by real vs synthetic for every tagged table.",
)
def status() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in TABLES_OF_INTEREST:
        try:
            result = run_query(
                f"""
                SELECT
                    SUM(CASE WHEN source = 'synthetic' THEN 1 ELSE 0 END) AS synthetic_rows,
                    SUM(CASE WHEN source IS NULL OR source != 'synthetic' THEN 1 ELSE 0 END) AS real_rows
                FROM `{table}`
                """
            )
            counts = result[0] if result else {"synthetic": 0, "real": 0}
            rows.append({"table": table, **counts})
        except Exception as exc:
            rows.append({"table": table, "error": str(exc)})
    return coerce_rows(rows)


@mcp.tool(
    name="synthetic__toggle",
    description=(
        "Reports whether synthetic data is currently detectable. Does not "
        "modify data — use scripts/seed-synthetic-team.py for that. The "
        "include_synthetic flag on every other tool is how queries are scoped."
    ),
)
def toggle() -> dict[str, Any]:
    rows = run_query(
        "SELECT COUNT(*) AS n FROM accounts WHERE source = 'synthetic'"
    )
    n = rows[0]["n"] if rows else 0
    return {
        "synthetic_accounts": int(n or 0),
        "hint": (
            "Every query tool accepts include_synthetic=True|False. "
            "Set it to False for real-only views."
        ),
    }
