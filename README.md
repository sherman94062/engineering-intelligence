# devlake-mcp

Local Apache DevLake + Grafana + MCP server for natural-language queries against
your engineering data. A self-hosted, open-source counterpart to DX.

See [CLAUDE.md](./CLAUDE.md) for the full design, data strategy, and prompt
recipes. Quick-start below.

## Stack

| Service    | Port  | Purpose                                   |
|------------|-------|-------------------------------------------|
| devlake    | 8080  | Ingest pipeline + REST API                |
| mysql      | 3306  | DevLake metadata + domain store           |
| grafana    | 3000  | DORA dashboards                           |
| config-ui  | 4000  | DevLake web configuration                 |
| mcp-server | 8811  | FastMCP server over Streamable HTTP       |

## Quick start

```bash
cp devlake-config/env.example devlake-config/env
$EDITOR devlake-config/env      # fill in GITHUB_TOKEN etc.

./scripts/bootstrap.sh          # compose up, wait for devlake, configure GitHub, run pipeline
python scripts/seed-synthetic-team.py

cd mcp && uv pip install -e . && uv run server.py
```

Then:

- Grafana: <http://localhost:3000>
- DevLake config UI: <http://localhost:4000>
- MCP endpoint: <http://localhost:8811/mcp>

## Docs

- [docs/devlake-setup.md](docs/devlake-setup.md)
- [docs/mcp-setup.md](docs/mcp-setup.md)
- [docs/synthetic-data.md](docs/synthetic-data.md)
- [docs/sample-queries.md](docs/sample-queries.md)
