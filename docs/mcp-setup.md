# MCP server setup

## Run locally

```bash
cd mcp
uv venv
uv pip install -e '.[dev]'
uv run server.py
```

Environment is read from `../devlake-config/env` automatically (via
`python-dotenv`). The server binds to `0.0.0.0:8811` over Streamable HTTP.

## Run via docker

`docker compose up -d` builds and runs the `mcp-server` service from the
Dockerfile in `mcp/`. It connects to `mysql:3306` via the compose network.

## Wire up Claude Desktop

Claude Desktop's config format spawns each MCP server as a subprocess. To
connect to our HTTP server, use `mcp-remote` as the bridge.

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "devlake": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8811/mcp"]
    }
  }
}
```

Fully quit Claude Desktop (⌘Q, not close) and reopen to pick up the config
change. The 23 devlake tools should appear in the MCP menu.

Or run the server via uv as a subprocess instead of going through the
container + mcp-remote:

```json
{
  "mcpServers": {
    "devlake": {
      "command": "uv",
      "args": ["--directory", "/ABS/PATH/engineering-intelligence/mcp", "run", "server.py"],
      "env": {
        "DB_URL": "mysql+pymysql://devlake:PASSWORD@localhost:3306/lake"
      }
    }
  }
}
```

## Wire up Claude Code

```bash
claude mcp add devlake-mcp \
  --env DB_URL=mysql+pymysql://devlake:PASSWORD@localhost:3306/lake \
  -- uv --directory /ABS/PATH/engineering-intelligence/mcp run server.py
```

## Tool surface

23 tools across six modules:

- `dora__*` — deployment frequency, lead time, CFR, TTR, performance band, trend
- `repos__*` — list, PR cycle time, PR review depth, commit frequency
- `contributors__*` — activity, AI signal, bus factor, AI adoption, persona compare
- `team__*` — architecture-code gap, incident summary, AI vs traditional
- `synthetic__*` — status, toggle
- `schema__*` — tables, describe, query

Every query tool accepts `include_synthetic: bool = True`. Set it to `False`
to restrict to real GitHub data.

## Safety

`schema__query` rejects any SQL containing a mutation keyword (INSERT,
UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, REPLACE, CALL,
USE, RENAME, MERGE, LOAD). Only SELECT/WITH/SHOW/DESCRIBE/EXPLAIN are
permitted. A row limit of 500 is applied by default.

## Tests

```bash
cd mcp
uv run pytest tests/ -v
```

The smoke tests import the server, verify all 23 tools register, and check
the read-only guard accepts SELECTs and rejects mutations. They do not need
DevLake to be running.
