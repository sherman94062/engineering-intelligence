"""Contributor-focused tools: activity, AI signal, bus factor, adoption."""

from __future__ import annotations

from typing import Any

from db import load_sql, run_query, synth_filter
from tools._common import coerce_rows, get_mcp, window_dates

mcp = get_mcp()


@mcp.tool(
    name="contributors__activity",
    description="Per-engineer commit + PR activity in the window.",
)
def activity(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("contributors.sql", key="activity").format(
        synth_filter_a=synth_filter(include_synthetic, alias="a"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="contributors__ai_signal",
    description=(
        "Batch-commit pattern detection. Returns authors whose commits exceed "
        "min_batch_lines in line count, at least min_batch_count times."
    ),
)
def ai_signal(
    window_days: int = 90,
    min_batch_lines: int = 250,
    min_batch_count: int = 3,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("commits.sql", key="ai_signal").format(
        synth_filter_alias=synth_filter(include_synthetic, alias="c"),
    )
    return coerce_rows(
        run_query(
            sql,
            {
                "since": since,
                "until": until,
                "min_batch_lines": min_batch_lines,
                "min_batch_count": min_batch_count,
            },
        )
    )


@mcp.tool(
    name="contributors__bus_factor",
    description="Per-repo contributor concentration: top contributor %, top-2 %.",
)
def bus_factor(
    window_days: int = 180,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("contributors.sql", key="bus_factor").format(
        synth_filter_c=synth_filter(include_synthetic, alias="c"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="contributors__ai_adoption",
    description="AI batch-signal spread across engineers sorted by batch commit count.",
)
def ai_adoption(
    window_days: int = 90,
    min_batch_lines: int = 250,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("contributors.sql", key="ai_adoption").format(
        synth_filter_c=synth_filter(include_synthetic, alias="c"),
    )
    return coerce_rows(
        run_query(
            sql,
            {"since": since, "until": until, "min_batch_lines": min_batch_lines},
        )
    )


@mcp.tool(
    name="contributors__persona_compare",
    description=(
        "Side-by-side comparison of engineers across key metrics (commits, "
        "mean diff, PR cycle time). Useful for spotting persona archetypes."
    ),
)
def persona_compare(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    # The synth_filter here has to guard `c.`; PR-level join reuses same alias via `pr`.
    sql = f"""
        SELECT
            a.user_name,
            a.full_name,
            COUNT(DISTINCT c.sha) AS commits,
            ROUND(AVG(c.additions + c.deletions), 0) AS mean_diff,
            COUNT(DISTINCT pr.id) AS prs,
            ROUND(AVG(TIMESTAMPDIFF(HOUR, pr.created_date, pr.merged_date)), 1) AS mean_cycle_hours
        FROM accounts a
        LEFT JOIN commits c
               ON c.author_id = a.id
              AND c.authored_date BETWEEN :since AND :until
        LEFT JOIN pull_requests pr
               ON pr.author_id = a.id
              AND pr.merged_date BETWEEN :since AND :until
        WHERE 1=1
          {synth_filter(include_synthetic, alias='a')}
        GROUP BY a.user_name, a.full_name
        HAVING commits > 0
        ORDER BY mean_diff DESC
    """
    return coerce_rows(run_query(sql, {"since": since, "until": until}))
