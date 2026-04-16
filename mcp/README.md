# devlake-mcp server

Read-only MCP server over the DevLake MySQL domain schema. Exposes DORA
metrics, repo/PR analytics, contributor signals, team-dynamics proxies, and
an ad-hoc SQL escape hatch.

## Run (local dev)

```bash
cd mcp
uv venv
uv pip install -e '.[dev]'
uv run server.py
```

## Environment

- `DB_URL` — SQLAlchemy URL to DevLake's MySQL (example in `devlake-config/env.example`)
- `MCP_HOST` (default `0.0.0.0`)
- `MCP_PORT` (default `8811`)

## Tests

```bash
uv run pytest tests/ -v
```

## Claude Desktop wiring

See the project root `CLAUDE.md` for the exact JSON block, or:

```bash
claude mcp add devlake-mcp \
  --env DB_URL=mysql+pymysql://devlake:PASSWORD@localhost:3306/lake \
  -- uv --directory "$(pwd)" run server.py
```
