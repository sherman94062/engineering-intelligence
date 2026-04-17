# engineering-intelligence

A self-hosted, open-source stand-in for DX ([getdx.com](https://getdx.com)).
Runs [Apache DevLake](https://devlake.apache.org) locally to ingest real
engineering data from GitHub, layers a synthetic 12-engineer team on top for
signals a solo repo can't produce, and exposes everything through a read-only
MCP server so Claude Desktop, Claude Code, or any MCP-compatible client can
answer questions like *"what's my change failure rate this quarter?"* against
real data.

> First time setting this up? Read [WALKTHROUGH.md](./WALKTHROUGH.md) — it's
> the end-to-end story with every gotcha we hit, in the order we hit them.

## Stack

| Service    | Port  | Purpose                                |
|------------|-------|----------------------------------------|
| devlake    | 8080  | Ingest pipeline + REST API             |
| mysql      | 3306  | DevLake metadata + domain store        |
| grafana    | 3002  | Provisioned DORA dashboard             |
| config-ui  | 4000  | DevLake web configuration              |
| mcp-server | 8811  | FastMCP server over Streamable HTTP    |

## What you get

- **Real DORA metrics** ingested from your GitHub repos — deployment
  frequency, lead time, change failure rate, time to restore
- **A 12-engineer synthetic team** that produces the signals a solo repo
  can't: PR reviews, contributor variance, incidents, AI-adoption spread.
  Every synthetic row is tagged `source = 'synthetic'` so you can always
  separate real from simulated
- **23 MCP tools** for natural-language queries (`dora__*`, `repos__*`,
  `contributors__*`, `team__*`, `synthetic__*`, `schema__*`) with a
  read-only SQL escape hatch
- **A provisioned Grafana dashboard** so you have a visual sanity check
  before the MCP is even wired up
- **An Architecture-Code Gap proxy** — PR iteration count × post-merge
  churn — so you can compare AI-heavy vs traditional engineering patterns
  across the synthetic team

## Quick start

```bash
cp devlake-config/env.example devlake-config/env
$EDITOR devlake-config/env      # GITHUB_TOKEN (repo+read:user+read:org)
                                # DEVLAKE_ENCRYPTION_SECRET (openssl rand -hex 32)

python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt

./scripts/bootstrap.sh          # compose up, configure GitHub, run first pipeline
python scripts/seed-synthetic-team.py   # after pipeline finishes
```

The MCP server runs automatically as a docker container on port 8811. Wire
it to Claude Desktop by editing
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

Fully quit (⌘Q) and reopen Claude Desktop. Ask it:

> Using the devlake MCP, show me synthetic__status and then
> dora__performance_level for the last 90 days.

## Architecture

```
  GitHub (real) ──┐                 ┌── Grafana (DORA dashboards)
                  │                 │
                  ▼                 ▼
              DevLake ──► MySQL ──┬──► MCP Server ──► Claude Desktop / Code
                  ▲               │
                  │               └── Synthetic seeder (flagged source='synthetic')
                  │
            config-ui (web)
```

Real data is ingested by DevLake into MySQL tables
(`commits`, `pull_requests`, `cicd_pipelines`, `repos`, …). The synthetic
seeder writes into the same tables with `source='synthetic'` so every query
tool in the MCP can scope to real-only with `include_synthetic=False`.

## Project layout

```
engineering-intelligence/
├── CLAUDE.md                    # Full design doc (source of truth)
├── WALKTHROUGH.md               # End-to-end setup story
├── README.md                    # This file
├── docker-compose.yml           # DevLake stack
├── devlake-config/env.example   # Env template
├── scripts/
│   ├── bootstrap.sh             # docker compose up + configure + trigger
│   ├── configure-github.py      # Idempotent DevLake REST configuration
│   ├── trigger-pipeline.py      # Pipeline trigger + progress poller
│   └── seed-synthetic-team.py   # Synthetic team data generator
├── synthetic/
│   ├── team-profiles.yml        # 12 engineers, 4 personas
│   └── incident-scenarios.yml   # CFR/TTR archetypes
├── mcp/                         # FastMCP server + tool modules
├── grafana/provisioning/        # Datasource + DORA dashboard
└── docs/
    ├── devlake-setup.md
    ├── mcp-setup.md
    ├── synthetic-data.md
    └── sample-queries.md
```

## Docs

| File | Covers |
|------|--------|
| [CLAUDE.md](./CLAUDE.md) | Full architecture, data strategy, persona design, ACG metric |
| [WALKTHROUGH.md](./WALKTHROUGH.md) | Zero-to-working walkthrough with every gotcha |
| [docs/devlake-setup.md](./docs/devlake-setup.md) | DevLake lifecycle: bootstrap, re-run, reset |
| [docs/mcp-setup.md](./docs/mcp-setup.md) | MCP server wiring for Claude Desktop + Claude Code |
| [docs/synthetic-data.md](./docs/synthetic-data.md) | Synthetic layer, tagging, determinism |
| [docs/sample-queries.md](./docs/sample-queries.md) | Prompt recipes for Claude |

## License

MIT
