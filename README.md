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
$EDITOR devlake-config/env      # fill in GITHUB_TOKEN; set a real DEVLAKE_ENCRYPTION_SECRET

# Install the small Python deps bootstrap.sh + the seeder need.
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt

./scripts/bootstrap.sh          # compose up, wait for devlake, configure GitHub, run pipeline
python scripts/seed-synthetic-team.py   # run after the first pipeline finishes

cd mcp && uv pip install -e . && uv run server.py
```

The same `.venv` works for `bootstrap.sh` and `seed-synthetic-team.py`. The MCP
server has its own dependency set managed by `uv` in `mcp/pyproject.toml`.

A good `DEVLAKE_ENCRYPTION_SECRET` value:

```bash
openssl rand -hex 32
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
