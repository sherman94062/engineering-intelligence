"""Repository and pull-request tools."""

from __future__ import annotations

from typing import Any

from db import load_sql, run_query, synth_filter
from tools._common import coerce_rows, get_mcp, window_dates

mcp = get_mcp()


@mcp.tool(
    name="repos__list",
    description="List every repository DevLake has ingested with basic metadata.",
)
def list_repos(include_synthetic: bool = True) -> list[dict[str, Any]]:
    sql = f"""
        SELECT id, name, url, language, created_date, updated_date
        FROM repos
        WHERE 1=1
          {synth_filter(include_synthetic)}
        ORDER BY name
    """
    return coerce_rows(run_query(sql))


@mcp.tool(
    name="repos__pr_cycle_time",
    description="PR open→merge cycle time by repo for the given window.",
)
def pr_cycle_time(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("prs.sql", key="pr_cycle_time").format(
        synth_filter_alias=synth_filter(include_synthetic, alias="pr"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="repos__pr_review_depth",
    description="Review-comment density per PR by repo.",
)
def pr_review_depth(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("prs.sql", key="pr_review_depth").format(
        synth_filter_alias=synth_filter(include_synthetic, alias="pr"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="repos__commit_frequency",
    description="Weekly commit counts per repo/author with lines added/removed.",
)
def commit_frequency(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("commits.sql", key="commit_frequency").format(
        synth_filter_alias=synth_filter(include_synthetic, alias="c"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))
