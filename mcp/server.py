"""FastMCP server exposing read-only tools over DevLake's schema.

Transport: Streamable HTTP on ${MCP_HOST}:${MCP_PORT} (defaults 0.0.0.0:8811).
All tools are read-only; schema__query rejects mutation statements.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT.parent / "devlake-config" / "env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

mcp = FastMCP(
    name="devlake",
    instructions=(
        "Read-only access to a local Apache DevLake instance. "
        "Use dora__* for DORA metrics, team__* for team dynamics, "
        "contributors__* for per-engineer analysis, synthetic__* to inspect "
        "and toggle the synthetic data layer, and schema__* for ad-hoc SQL."
    ),
)

# Register tool modules. Each module attaches its tools with @mcp.tool().
from tools import contributors, dora, repos, schema, synthetic, team  # noqa: E402,F401

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8811"))
    mcp.run(transport="http", host=host, port=port)
