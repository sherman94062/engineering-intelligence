# CLAUDE.md — devlake-mcp

## Project Purpose

This project stands up a local Apache DevLake instance as a self-hosted,
open-source equivalent to the DX developer intelligence platform. It ingests
engineering data from GitHub (and optionally Jira), computes DORA metrics,
and exposes the underlying Postgres database via a custom MCP server — enabling
natural-language queries against real engineering data from Claude Desktop,
Claude Code, or any MCP-compatible client.

The architecture mirrors what DX (getdx.com) provides commercially:
- GitHub + Jira → DevLake ingest pipeline → Postgres → Grafana dashboards
- Postgres → MCP server → Claude / Cursor / Windsurf

### Data Strategy: Hybrid (Real + Synthetic)

Real GitHub repos (`sherman94062`) provide an authentic foundation — genuine
commit velocity, real AI-assisted code patterns, and actual project diversity.
However, solo repos structurally cannot produce team-dynamics signals: there
are no PR reviewers, no contributor variance, no incident history, and no
cross-engineer AI adoption spread.

A synthetic team layer addresses this gap by injecting realistic data directly
into DevLake's MySQL schema — simulating a 12-engineer team working on the
same repos. The synthetic layer is clearly flagged in the database
(`source = 'synthetic'`) so real and simulated data are always distinguishable.

| Data Layer   | Source                              | What It Enables                              |
|--------------|-------------------------------------|----------------------------------------------|
| Real         | GitHub `sherman94062` (ingested)    | Commit velocity, AI code signal, deploy freq |
| Synthetic    | `scripts/seed-synthetic-team.py`    | PR reviews, incidents, CFR, TTR, bus factor  |

Primary real data source: GitHub org/user `sherman94062`

---

## Repository Layout

```
devlake-mcp/
├── CLAUDE.md                  # This file
├── docker-compose.yml         # DevLake full stack
├── devlake-config/
│   └── env                    # DevLake environment variables (gitignored)
├── mcp/
│   ├── server.py              # FastMCP server (entry point)
│   ├── tools/
│   │   ├── dora.py            # DORA metric tools
│   │   ├── repos.py           # Repository and PR tools
│   │   ├── contributors.py    # Contributor activity tools
│   │   ├── team.py            # Team dynamics: ACG, incidents, AI adoption
│   │   ├── synthetic.py       # Synthetic data status and toggle tools
│   │   └── schema.py          # Schema discovery tools
│   ├── queries/
│   │   ├── dora.sql           # DORA metric queries
│   │   ├── prs.sql            # Pull request analytics
│   │   ├── commits.sql        # Commit activity
│   │   ├── contributors.sql   # Contributor breakdowns
│   │   ├── team.sql           # Team-level aggregations
│   │   └── incidents.sql      # Incident queries for CFR/TTR
│   ├── pyproject.toml
│   └── README.md
├── grafana/
│   └── provisioning/          # Auto-loaded DORA dashboards
├── scripts/
│   ├── bootstrap.sh              # First-run setup
│   ├── configure-github.py       # Automates DevLake GitHub connection via API
│   ├── trigger-pipeline.py       # Kicks off a collection run
│   └── seed-synthetic-team.py    # Generates synthetic team layer (see below)
├── synthetic/
│   ├── team-profiles.yml         # Engineer personas and behavioral configs
│   ├── incident-scenarios.yml    # Incident archetypes for CFR/TTR generation
│   └── README.md                 # How synthetic data is structured and flagged
└── docs/
    ├── devlake-setup.md
    ├── mcp-setup.md
    ├── synthetic-data.md         # Detailed synthetic layer documentation
    └── sample-queries.md
```

---

## Stack

| Component     | Image / Version              | Port  | Purpose                         |
|---------------|------------------------------|-------|---------------------------------|
| devlake       | apache/devlake:latest        | 8080  | DevLake API + pipeline engine   |
| mysql         | mysql:8                      | 3306  | DevLake metadata store          |
| grafana       | grafana/grafana:latest       | 3000  | DORA dashboards                 |
| config-ui     | apache/devlake-config-ui     | 4000  | DevLake web configuration UI    |
| mcp-server    | local build                  | 8811  | FastMCP server over Streamable HTTP |

DevLake uses MySQL internally. The MCP server connects to DevLake's **exposed
read-only Postgres view layer** (DevLake Data Cloud). If DevLake's Data Cloud
Postgres is not available in the open-source version, the MCP server connects
directly to MySQL via SQLAlchemy with read-only credentials.

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Python 3.11+ with `uv` or `pip`
- GitHub Personal Access Token (PAT) with `repo` and `read:org` scopes
- Optional: Jira API token for incident data

Environment variables required (create `devlake-config/env`, never commit):

```bash
# DevLake
DEVLAKE_ADMIN_USER=admin
DEVLAKE_ADMIN_PASS=<choose>
MYSQL_ROOT_PASSWORD=<choose>
MYSQL_PASSWORD=<choose>

# GitHub connection
GITHUB_TOKEN=<your PAT>
GITHUB_ORG_OR_USER=sherman94062

# MCP server
DB_URL=mysql+pymysql://devlake:<MYSQL_PASSWORD>@localhost:3306/lake
MCP_PORT=8811
```

---

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/sherman94062/devlake-mcp
cd devlake-mcp

# 2. Set up environment
cp devlake-config/env.example devlake-config/env
# Edit devlake-config/env with your values

# 3. Start the full stack
docker compose up -d

# 4. Wait for DevLake to be ready (~60s), then configure GitHub connection
python scripts/configure-github.py

# 5. Trigger the first data collection pipeline (real GitHub data)
python scripts/trigger-pipeline.py

# 6. Seed the synthetic team layer (PR reviews, incidents, contributor personas)
python scripts/seed-synthetic-team.py
# Options:
#   --engineers 12          Number of synthetic team members (default: 12)
#   --lookback-days 180     History window to populate (default: 180)
#   --ai-adoption-rate 0.6  Fraction of engineers showing AI commit patterns
#   --dry-run               Preview inserts without writing to DB

# 7. Install and start the MCP server
cd mcp
uv pip install -e .
uv run server.py

# 8. Open Grafana dashboards
open http://localhost:3000   # admin / admin (change on first login)

# 9. Open DevLake config UI
open http://localhost:4000
```

---

## DevLake Configuration

### GitHub Repos to Ingest

Configure these repos in DevLake (via config UI or `configure-github.py`).
All are under `sherman94062`:

| Repo                        | Why It's Useful                              |
|-----------------------------|----------------------------------------------|
| `argus`                     | Self-healing dbt agent — rich PR history     |
| `mcp-security-stack`        | Multi-server FastAPI project                 |
| `databricks-mcp-server`     | 14-tool MCP server                           |
| `analytics-agent`           | Agent project with iterative commits         |
| `agent-benchmarks`          | Benchmarking harness                         |
| `dbt-semantic-layer-agent`  | dbt project with transformation history      |
| `nl-to-sql-agent`           | NL→SQL agent                                 |

Add all repos for maximum DORA signal. More PR/deploy history = better metrics.

### Scope Config (DORA)

In DevLake, for each GitHub repo define:

- **Deployments**: GitHub workflow runs whose job names match `(?i)(deploy|release|publish)`
- **Incidents**: GitHub issues with label `incident` or `bug` (or Jira issue type `Bug`)
- **Code Changes**: All commits and pull requests (default)

### Optional: Jira Connection

If you have a Jira instance, connect it for incident data (Time to Restore, Change Failure Rate).
Otherwise, use GitHub Issues as the incident source — or rely on the synthetic
incident layer (see Synthetic Team Layer below).

---

## Synthetic Team Layer

### Why It Exists

Real solo repos cannot produce several critical DORA and DX signals:
- **Change Failure Rate** and **Time to Restore** require incident history
- **PR review depth** requires multiple reviewers
- **Bus factor** and **contributor variance** require multiple engineers
- **AI adoption spread** requires comparing engineers with different AI usage patterns
- **Architecture-Code Gap** at team scale requires seeing the metric vary across people

The synthetic layer injects these signals into DevLake's MySQL schema alongside
the real GitHub data, producing a believable 12-engineer team picture.

### Engineer Personas (`synthetic/team-profiles.yml`)

The generator creates 12 personas with distinct behavioral signatures:

| Persona Type       | Count | Characteristics                                              |
|--------------------|-------|--------------------------------------------------------------|
| AI Power User      | 3     | High batch-commit ratio, large diffs, fast cycle time        |
| AI Adopter         | 4     | Mixed AI/manual pattern, moderate diff sizes                 |
| Traditional        | 3     | Small focused commits, long review cycles, manual patterns   |
| Senior Reviewer    | 2     | Few commits, high PR comment volume, multiple review rounds  |

Each persona has configurable parameters: commit frequency, avg diff size,
PR iteration count, review comment rate, incident-creation probability.

### What Gets Seeded

```
accounts          →  12 synthetic engineer accounts (flagged source='synthetic')
commits           →  Synthetic commits on real repos, attributed to personas
pull_requests     →  PRs with realistic open/review/merge timelines
pull_request_comments → Review threads with iteration counts matching persona type
cicd_pipelines    →  Deploy events derived from synthetic PR merges
incidents         →  ~8% of deploys trigger an incident (realistic CFR baseline)
incident_comments →  Resolution timeline entries for TTR calculation
```

### Incident Scenarios (`synthetic/incident-scenarios.yml`)

Predefined incident archetypes drive realistic CFR/TTR patterns:

| Scenario             | Frequency | Avg TTR  | Trigger Pattern                        |
|----------------------|-----------|----------|----------------------------------------|
| Config regression    | 40%       | 2.5 hrs  | Deploy to prod within 1hr of incident  |
| Data pipeline break  | 25%       | 6 hrs    | Linked to dbt/analytics repo deploys   |
| Auth service outage  | 20%       | 1.5 hrs  | High-severity, fast resolution         |
| Slow memory leak     | 15%       | 18 hrs   | Gradual detection, long TTR            |

### Architecture-Code Gap in the Synthetic Layer

The AI Power User and AI Adopter personas are configured with elevated
**PR iteration counts** and **post-merge churn rates** — simulating the
plan-abandonment pattern Mark Nelson describes. This makes the
Architecture-Code Gap metric visible and comparable across persona types.

Traditional engineers show lower gap scores, providing the contrast needed
to make the metric meaningful.

### Resetting Synthetic Data

```bash
# Remove all synthetic records and re-seed
python scripts/seed-synthetic-team.py --reset

# Remove synthetic data entirely (revert to real-only)
python scripts/seed-synthetic-team.py --purge
```

---

## MCP Server

### Design

The MCP server is built with **FastMCP** (Python). It exposes read-only tools
that query the DevLake database and return structured data for LLM consumption.
It is intentionally read-only — no writes to DevLake.

### Tools Exposed

```
dora__deployment_frequency     → Deployments per week/month by repo
dora__lead_time_for_changes    → Median/p90 commit-to-deploy time
dora__change_failure_rate      → % deploys causing incidents
dora__time_to_restore          → Mean/median incident resolution time
dora__performance_level        → Elite/High/Medium/Low classification per repo
dora__trend                    → DORA metrics over rolling time windows

repos__list                    → All ingested repos with metadata
repos__pr_cycle_time           → PR open→merge cycle time by repo
repos__pr_review_depth         → Comment counts, review iterations
repos__commit_frequency        → Commits per week by repo/author

contributors__activity         → Commit + PR activity by contributor
contributors__ai_signal        → Batch-commit pattern detection (AI vs human proxy)
contributors__bus_factor       → Unique contributor count per repo/file area
contributors__ai_adoption      → AI usage spread across team (real + synthetic)
contributors__persona_compare  → Side-by-side metric comparison across engineer types

team__architecture_code_gap    → Gap metric: PR iterations + post-merge churn by engineer
team__incident_summary         → Incident history with severity, TTR, linked deploys
team__ai_vs_traditional        → DORA metric comparison: AI-heavy vs traditional engineers

synthetic__status              → Show counts of real vs synthetic records by table
synthetic__toggle              → Include or exclude synthetic data from query scope

schema__tables                 → List DevLake database tables
schema__describe               → Describe a table's columns and types
schema__query                  → Execute arbitrary read-only SQL (SELECT only)
```

All tools that query contributors or PRs accept a `--include-synthetic` flag
(default: `true`). Set to `false` to restrict to real GitHub data only.

### Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "devlake": {
      "command": "uv",
      "args": ["--directory", "/path/to/devlake-mcp/mcp", "run", "server.py"],
      "env": {
        "DB_URL": "mysql+pymysql://devlake:PASSWORD@localhost:3306/lake"
      }
    }
  }
}
```

Or, if the Streamable HTTP server (docker or local) is already running on
port 8811, use `mcp-remote` as a bridge — Claude Desktop's config format
doesn't support raw `url` entries:

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

### Claude Code Config

```bash
claude mcp add devlake-mcp \
  --env DB_URL=mysql+pymysql://devlake:PASSWORD@localhost:3306/lake \
  -- uv --directory /path/to/devlake-mcp/mcp run server.py
```

---

## Key Database Tables (DevLake Schema)

These are the primary tables the MCP tools query:

| Table                    | Contents                                      |
|--------------------------|-----------------------------------------------|
| `commits`                | All commits with author, timestamp, repo      |
| `pull_requests`          | PRs with open/merge/close timestamps          |
| `pull_request_comments`  | Review comments                               |
| `cicd_pipelines`         | CI/CD runs (deployments)                      |
| `cicd_tasks`             | Individual job steps within pipelines         |
| `incidents`              | Mapped incidents from GitHub Issues or Jira   |
| `repos`                  | Repository metadata                           |
| `accounts`               | Contributor accounts                          |
| `issue_worklogs`         | Time tracking (if Jira connected)             |

Schema docs: https://devlake.apache.org/docs/DataModels/DevLakeDomainLayerSchema

---

## DORA Metric Definitions (DevLake)

| Metric                  | Definition Used                                                  |
|-------------------------|------------------------------------------------------------------|
| Deployment Frequency    | # successful `cicd_pipelines` where `type=DEPLOYMENT` per week  |
| Lead Time for Changes   | `cicd_pipeline.finished_date` - first `commit.authored_date`    |
| Change Failure Rate     | # deploys linked to an incident / total deploys                 |
| Time to Restore Service | `incident.resolution_date` - `incident.created_date`           |

Performance bands (Google DORA 2023):
- **Elite**: Deploy multiple/day, LT <1hr, CFR <5%, TTR <1hr
- **High**: Deploy weekly, LT <1day, CFR <10%, TTR <1day
- **Medium**: Deploy monthly, LT <1wk, CFR <15%, TTR <1wk
- **Low**: Deploy <monthly, LT >1month, CFR >15%, TTR >1wk

---

## Architecture-Code Gap Proxy Metric

One of the goals of this project is to implement a proxy for the
**Architecture-Code Gap** metric coined by Mark Nelson (CTO, MX Technologies):

> The percentage of AI-generated plans that get significantly changed or
> abandoned during implementation — indicating context failure, not model failure.

Since we lack IDE telemetry, we approximate it using:

1. **PR Iteration Count**: PRs with >3 review cycles before merge (plan quality proxy)
2. **Batch Commit Detection**: Commits with unusually large line-count deltas in
   short time windows (AI-generated code proxy — see `contributors__ai_signal` tool)
3. **Post-Merge Churn**: Files modified again within 7 days of a PR merge
   (implementation abandonment proxy)

The `dora__performance_level` tool surfaces these alongside standard DORA to
give a richer picture of AI-assisted engineering health.

---

## Common Claude Prompts for This Environment

Once the MCP server is connected to Claude:

**DORA fundamentals (real data)**
```
What are my DORA metrics across all repos for the last 90 days?
What's my deployment frequency this month vs last month?
Show me the lead time trend for the mcp-security-stack repo week over week.
```

**AI code signal (real data — your unique story)**
```
Show me commits that look AI-generated (large batch changes) and how they
correlate with post-merge churn.

What percentage of my commits show AI batch-generation patterns vs manual typing?

Which repos have the highest post-merge churn rate and is it correlated with
large-diff commits?
```

**Team dynamics (synthetic layer)**
```
Compare DORA metrics between AI power users and traditional engineers on the team.

Which engineers have the highest Architecture-Code Gap score and what does their
PR iteration pattern look like?

Show me the bus factor risk across repos — which files have only one contributor?

What's the AI adoption spread across the team? Show me from highest to lowest usage.
```

**Incident and reliability (synthetic layer)**
```
Which repo has the highest change failure rate and what does the incident history
look like?

Show me all incidents in the last 90 days with their TTR and linked deploy.

What's the relationship between AI-heavy deploys and incident rate?
```

**Blended analysis**
```
Give me an Architecture-Code Gap estimate for the whole team. Break it down by
engineer type (AI power user vs traditional).

If I filter out synthetic data, what does my personal DORA performance look like?

Pretend you're an engineering VP presenting to a board. Summarize the team's
engineering health based on this data.
```

---

## Development Notes

### Adding a New Tool

1. Add a SQL file to `mcp/queries/`
2. Add a tool function to the appropriate file in `mcp/tools/`
3. Register it in `mcp/server.py` with `@mcp.tool()`
4. Test with: `uv run -m mcp.tools.<module> --test`

### Running Tests

```bash
cd mcp
uv run pytest tests/ -v
```

### Extending the Synthetic Team

To add personas or adjust existing ones, edit `synthetic/team-profiles.yml`
and re-run the seeder:

```bash
# Purge existing synthetic records and re-seed with updated profiles
python scripts/seed-synthetic-team.py --reset

# Tune a specific dimension without full reset
python scripts/seed-synthetic-team.py --update-incidents
python scripts/seed-synthetic-team.py --update-prs
```

### Refreshing Data

```bash
# Pull new real GitHub data
python scripts/trigger-pipeline.py

# Or via DevLake UI
open http://localhost:4000  # Blueprints → Run Now

# Synthetic data does not need refreshing unless profiles change
```

### Resetting DevLake

```bash
docker compose down -v   # WARNING: destroys all ingested data including synthetic
docker compose up -d
python scripts/bootstrap.sh
python scripts/configure-github.py
python scripts/trigger-pipeline.py
python scripts/seed-synthetic-team.py   # Re-seed after pipeline completes
```

---

## Gotchas

- **DevLake takes ~60s to initialize** on first start. The config UI at `:4000`
  will return 502 until it's ready. Check with `docker compose logs devlake -f`.

- **GitHub rate limits**: DevLake respects GitHub's API limits but large repos
  with deep history will take time. Start with a 6-month lookback window.

- **Deployment detection requires workflow runs**. Repos without GitHub Actions
  will have no deployment data, which tanks Deployment Frequency and Lead Time.
  For repos without CI, create a stub workflow that fires on push to `main`.

- **MySQL vs Postgres**: DevLake open-source uses MySQL. The DX MCP server uses
  Postgres (DX Data Cloud). The `schema__query` tool here uses SQLAlchemy so
  SQL dialect differences are handled, but some DX-specific queries will need
  adaptation.

- **Seed synthetic data AFTER the first GitHub pipeline run** completes. The
  seeder references real repo IDs from the `repos` table. Running it before
  ingestion will produce orphaned records.

- **Synthetic data survives a DevLake re-collection**. Re-running the GitHub
  pipeline does not wipe synthetic records (different `source` value). However,
  `docker compose down -v` destroys everything — re-seed after a full reset.

- **MCP server must be running** before Claude Desktop loads. If tools don't
  appear, check `docker compose ps` and `uv run server.py` separately.

---

## References

- Apache DevLake docs: https://devlake.apache.org/docs
- DevLake DORA setup: https://devlake.apache.org/docs/DORA
- DevLake domain layer schema: https://devlake.apache.org/docs/DataModels/DevLakeDomainLayerSchema
- DX MCP server (reference implementation): https://github.com/get-dx/dx-mcp-server
- FastMCP: https://github.com/jlowin/fastmcp
- DX Core 4 framework: https://getdx.com/research/core-four
- Mark Nelson on Architecture-Code Gap: https://www.linkedin.com/in/marknelsonmx
- DevLake MySQL schema (for synthetic seeder): https://github.com/apache/incubator-devlake/tree/main/backend/plugins/core/dal
