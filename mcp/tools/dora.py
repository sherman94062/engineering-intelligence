"""DORA metric tools: DF, LT, CFR, TTR, performance band, trend."""

from __future__ import annotations

from typing import Any

from db import load_sql, run_query, synth_filter
from tools._common import coerce_rows, get_mcp, window_dates

mcp = get_mcp()


def _prepare(sql: str, include_synthetic: bool) -> str:
    return sql.format(
        synth_filter=synth_filter(include_synthetic, alias="p"),
        synth_filter_alias=synth_filter(include_synthetic, alias="p"),
    )


@mcp.tool(
    name="dora__deployment_frequency",
    description="Successful deployments per day, grouped by repo. Window defaults to the last 90 days.",
)
def deployment_frequency(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = _prepare(load_sql("dora.sql", key="deployment_frequency"), include_synthetic)
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="dora__lead_time_for_changes",
    description="Mean + median commit-to-deploy time, per repo.",
)
def lead_time_for_changes(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = _prepare(load_sql("dora.sql", key="lead_time_for_changes"), include_synthetic)
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="dora__change_failure_rate",
    description="Share of deploys followed by an incident within 24h, per repo.",
)
def change_failure_rate(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = _prepare(load_sql("dora.sql", key="change_failure_rate"), include_synthetic)
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="dora__time_to_restore",
    description="Incident resolution time across the window.",
)
def time_to_restore(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    # issues table has no `p` alias, use plain filter.
    sql = load_sql("dora.sql", key="time_to_restore").format(
        synth_filter=synth_filter(include_synthetic),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))


@mcp.tool(
    name="dora__performance_level",
    description=(
        "Classifies each repo into an Elite/High/Medium/Low band using Google DORA 2023 thresholds."
    ),
)
def performance_level(
    window_days: int = 90,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = _prepare(load_sql("dora.sql", key="performance_level"), include_synthetic)
    rows = run_query(sql, {"since": since, "until": until})
    for row in rows:
        row["band"] = _classify(row["deploys_in_window"], row.get("lead_time_hours"), window_days)
    return coerce_rows(rows)


def _classify(deploys: int | None, lead_time_hours: float | None, window_days: int) -> str:
    deploys = deploys or 0
    per_day = deploys / max(window_days, 1)
    lt = lead_time_hours if lead_time_hours is not None else 10_000
    if per_day >= 1 and lt < 1:
        return "Elite"
    if per_day >= 1 / 7 and lt < 24:
        return "High"
    if per_day >= 1 / 30 and lt < 24 * 7:
        return "Medium"
    return "Low"


@mcp.tool(
    name="dora__trend",
    description="Weekly deploy count + success rate for trend charts.",
)
def trend(
    window_days: int = 180,
    include_synthetic: bool = True,
) -> list[dict[str, Any]]:
    since, until = window_dates(window_days)
    sql = load_sql("dora.sql", key="trend").format(
        synth_filter_alias=synth_filter(include_synthetic, alias="p"),
    )
    return coerce_rows(run_query(sql, {"since": since, "until": until}))
