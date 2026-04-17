"""Single shared FastMCP instance.

Both `server.py` and every module under `tools/` import `mcp` from here.
Keeping the instance in its own module avoids the circular-import trap
where `python server.py` runs the script as `__main__`, tool modules
re-import `server` as a second module, and we end up with two FastMCP
instances — one with tools registered (but no HTTP serving) and one
serving HTTP (but with no tools).
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP(
    name="devlake",
    instructions=(
        "Read-only access to a local Apache DevLake instance. "
        "Use dora__* for DORA metrics, team__* for team dynamics, "
        "contributors__* for per-engineer analysis, synthetic__* to inspect "
        "and toggle the synthetic data layer, and schema__* for ad-hoc SQL."
    ),
)
