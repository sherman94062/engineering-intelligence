"""Team-level tools: architecture-code gap, incident summary, AI vs traditional."""

from __future__ import annotations

from typing import Any

from db import load_sql, run_query, synth_filter
from tools._common import coerce_rows, get_mcp, window_dates

mcp = get_mcp()


@mcp.tool(
    name="team__architecture_code_gap",
    description=(
        "Proxy for Mark Nelson's Architecture-Code Gap: PR iteration count × "
        "post-merge churn. Higher score ⇒ more AI-plan abandonment signal."
    ),
)
def architecture_code_gap(
    window_days: int = 180,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("team.sql", key="architecture_code_gap").format(
        synth_filter_pr=synth_filter(include_synthetic, alias="pr"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="team__incident_summary",
    description="List of incidents in the window with severity, TTR, linked deploy.",
)
def incident_summary(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("incidents.sql", key="summary").format(
        synth_filter_alias=synth_filter(include_synthetic, alias="i"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="team__ai_vs_traditional",
    description=(
        "Buckets engineers into high/mixed/low AI-signal bands and reports "
        "commit volume, diff size, and cycle time for each band."
    ),
)
def ai_vs_traditional(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("team.sql", key="ai_vs_traditional").format(
        synth_filter_c=synth_filter(include_synthetic, alias="c"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))
