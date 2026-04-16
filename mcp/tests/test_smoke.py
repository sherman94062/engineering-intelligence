"""Static import + read-only guard smoke tests.

These tests do not require DevLake to be running — they just verify that
the modules import cleanly and the SQL guard rejects mutation statements.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DB_URL", "mysql+pymysql://user:pw@localhost:3306/lake")


def test_server_imports():
    import server  # noqa: F401


def test_all_tool_modules_register():
    import asyncio

    import server

    expected = {
        "dora__deployment_frequency",
        "dora__lead_time_for_changes",
        "dora__change_failure_rate",
        "dora__time_to_restore",
        "dora__performance_level",
        "dora__trend",
        "repos__list",
        "repos__pr_cycle_time",
        "repos__pr_review_depth",
        "repos__commit_frequency",
        "contributors__activity",
        "contributors__ai_signal",
        "contributors__bus_factor",
        "contributors__ai_adoption",
        "contributors__persona_compare",
        "team__architecture_code_gap",
        "team__incident_summary",
        "team__ai_vs_traditional",
        "synthetic__status",
        "synthetic__toggle",
        "schema__tables",
        "schema__describe",
        "schema__query",
    }
    tools = asyncio.run(server.mcp.list_tools())
    registered = {t.name for t in tools}
    missing = expected - registered
    assert not missing, f"tools not registered: {missing}"


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO commits (sha) VALUES ('abc')",
        "update commits set message='x'",
        "DROP TABLE commits",
        "select 1; delete from commits",
    ],
)
def test_guard_rejects_mutations(sql: str):
    from db import assert_read_only

    with pytest.raises(ValueError):
        assert_read_only(sql)


def test_guard_allows_select():
    from db import assert_read_only

    assert_read_only("SELECT 1")
    assert_read_only("WITH x AS (SELECT 1) SELECT * FROM x")
    assert_read_only("SHOW TABLES")
