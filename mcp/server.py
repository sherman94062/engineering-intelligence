"""FastMCP server exposing read-only tools over DevLake's schema.

Transport: Streamable HTTP on ${MCP_HOST}:${MCP_PORT} (defaults 0.0.0.0:8811).
All tools are read-only; schema__query rejects mutation statements.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT.parent / "devlake-config" / "env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# The single shared FastMCP instance. Importing this BEFORE importing the
# tool modules is important — every tool registers against `mcp`.
from mcp_instance import mcp  # noqa: E402

# Importing these modules is what registers all 23 tools.
from tools import contributors, dora, repos, schema, synthetic, team  # noqa: E402,F401

# ASGI app exposed as `server:app` so uvicorn (and MCP clients via HTTP)
# see the same instance that has tools registered.
app = mcp.http_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8811"))
    uvicorn.run(app, host=host, port=port, log_level="info")
