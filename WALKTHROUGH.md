# Walkthrough

A zero-to-working guide for setting this up on a fresh machine. Every step
below was actually executed during the first real run — the gotchas listed
are the ones we hit, not hypothetical ones.

If you just want the quick path, jump to the [Quick start](./README.md#quick-start)
in the README. This file is for when a step breaks and you want to know
why.

---

## 0 · Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Python 3.11+
- A GitHub Personal Access Token

The repo has been smoke-tested against:

- macOS (Darwin 25.3), Python 3.14, Docker Desktop
- DevLake `apache/devlake:latest` (pulled during first run)

---

## 1 · Clone and configure env

```bash
git clone https://github.com/sherman94062/engineering-intelligence
cd engineering-intelligence
cp devlake-config/env.example devlake-config/env
$EDITOR devlake-config/env
```

Two fields *must* change from the defaults:

### `GITHUB_TOKEN`

Create a classic PAT at <https://github.com/settings/tokens/new> with
these scopes:

- `repo` — read repo metadata, commits, PRs
- `read:user` — **required**, not optional. DevLake's GraphQL query for
  PRs asks for reviewer/author `email`, which requires `read:user` (or
  `user:email`). Without it every *Collect Pull Requests* subtask fails
  with `graphql query got error`.
- `read:org` — only needed if any ingested repo is org-owned

### `DEVLAKE_ENCRYPTION_SECRET`

DevLake refuses to start if this is left as the placeholder. Generate one:

```bash
openssl rand -hex 32
```

Paste the output into `devlake-config/env`.

The other placeholders (`change-me`, `change-me-root`, `change-me-devlake`)
are fine for local-only runs as long as they stay consistent between
`MYSQL_PASSWORD` and the `DB_URL` line (both default to the same value).

### `GITHUB_REPOS`

Comma-separated. Use `*` (or leave blank) to auto-discover every repo you
own — `configure-github.py` will page `/users/<owner>/repos` and add all of
them. Missing repos in an explicit list are skipped with a warning, not a
hard error.

---

## 2 · Install the Python deps

Both `bootstrap.sh` and `seed-synthetic-team.py` invoke `python` directly.
They need `requests`, `python-dotenv`, `sqlalchemy`, `pymysql`, `pyyaml`,
`faker`. A venv keeps it clean:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r scripts/requirements.txt
```

The MCP server has its own dependency set (`mcp/pyproject.toml`) managed
by `uv` — separate from this venv.

---

## 3 · Bootstrap the stack

```bash
./scripts/bootstrap.sh
```

This does four things in order:

1. `docker compose --env-file devlake-config/env up -d` — brings up devlake,
   mysql, grafana, config-ui, mcp-server
2. Polls `http://localhost:8080/ping` until DevLake's REST API responds
3. Runs `scripts/configure-github.py` to create the GitHub connection,
   scope config, scopes, and blueprint
4. Runs `scripts/trigger-pipeline.py` to kick off the first ingest

Expect this to take **5–15 minutes** on first run (pulling images +
ingesting a few months of commits).

### What DevLake's REST API wants

The script handles all of this — listing here so you know what's happening
if something fails.

| Step | Endpoint | Shape gotcha |
|------|----------|--------------|
| Create connection | `POST /plugins/github/connections` | Needs `authMethod: "AccessToken"` alongside `token` |
| Create scope config | `POST /plugins/github/connections/:id/scope-configs` | `entities` defaults to everything; we exclude `TICKET` so repos with Issues disabled don't break GraphQL |
| Create scopes | `PUT /plugins/github/connections/:id/scopes` | Body is `{"data": [...]}`; only persists `connectionId/githubId/name/fullName` |
| Enrich scopes | `PATCH /plugins/github/connections/:id/scopes/:scopeId` | Must set `cloneUrl/HTMLUrl/ownerId/language/scopeConfigId` or gitextractor fails with `Invalid Git URL` |
| Create blueprint | `POST /blueprints` | Scope references use the **numeric githubId as a string**, not `owner/repo` |

---

## 4 · Watch the first pipeline

`trigger-pipeline.py` polls every 10 s. Output looks like:

```
==> Triggering blueprint id=1 (github-blueprint)
   pipeline id=N — polling every 10s...
   [0s] status=TASK_CREATED  tasks=0/N
   [10s] status=TASK_PARTIAL tasks=3/N
   ...
   [150s] status=TASK_PARTIAL tasks=N/N
==> Pipeline finished successfully.
```

`TASK_PARTIAL` with `finishedTasks == totalTasks` is terminal — it means
some tasks failed but others succeeded. The script returns exit code 2 in
that case and prints a message per failed task.

### Diagnosing failed tasks

If the script exits with failed tasks, the most useful extra signal is in
DevLake's container logs:

```bash
docker compose --env-file devlake-config/env logs devlake \
  | grep -A 4 -i "graphql query got error\|error preparing\|forbidden\|unauthorized"
```

Common patterns:

| Symptom | Cause | Fix |
|---------|-------|-----|
| `subtask Collect Issues ended unexpectedly` + `field requires user:email / read:user` | PAT scope | Regenerate PAT with `read:user` added, update env, rerun configure-github + trigger |
| `failed to get Git URL / Invalid Git URL` | Scope missing `cloneUrl` | `configure-github.py` already PATCHes cloneUrl; rerun it |
| `subtask Collect Issues ended unexpectedly` (first fail) | Repo has Issues disabled on GitHub | Our scope config excludes TICKET — rerun configure-github.py |
| `graphql query got error` inside *Collect Pull Requests* | PAT is missing `read:user` | Same as first row |

---

## 5 · Seed the synthetic team

**Only run this after the first pipeline finishes**, because the seeder
reads real `repos.id` values from DevLake.

```bash
python scripts/seed-synthetic-team.py
```

What gets generated (default, 12 engineers × 180-day window):

| Table                     | Rows       |
|---------------------------|------------|
| accounts                  | 12         |
| commits                   | ~8 000     |
| pull_requests             | ~1 700     |
| pull_request_comments     | ~5 000     |
| cicd_pipelines            | ~1 700     |
| issues (incidents only)   | ~140       |

Every row is tagged `source = 'synthetic'`. The first run of the seeder
also ALTERs each target table to add that column (nullable, default NULL)
so real rows remain `source IS NULL`.

### If the seeder errors mid-run

Partial inserts will have landed. Reset cleanly:

```bash
python scripts/seed-synthetic-team.py --reset
```

### Tuning

```bash
python scripts/seed-synthetic-team.py --lookback-days 365
python scripts/seed-synthetic-team.py --engineers 20
python scripts/seed-synthetic-team.py --ai-adoption-rate 0.8
python scripts/seed-synthetic-team.py --dry-run
```

---

## 6 · Sanity-check before wiring Claude

Open Grafana: <http://localhost:3000> (admin / admin). The *DORA Overview*
dashboard in the DORA folder should be populated.

Or query MySQL directly:

```bash
source devlake-config/env
docker compose exec mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -D lake -e "
SELECT
  (SELECT COUNT(*) FROM commits) AS commits,
  (SELECT COUNT(*) FROM pull_requests) AS prs,
  (SELECT COUNT(*) FROM cicd_pipelines) AS deploys,
  (SELECT COUNT(*) FROM issues WHERE type='INCIDENT') AS incidents;"
```

---

## 7 · Wire up Claude Desktop

The MCP server is already running in the `devlake-mcp-server` container on
port 8811. You do **not** need to `uv run server.py` yourself.

Claude Desktop's config format spawns each MCP server as a subprocess — it
silently rejects raw `"url": "…"` entries with *"not valid MCP server
configurations"*. Use `mcp-remote` as a bridge (the same pattern
`databricks` / other HTTP MCPs use):

```bash
$EDITOR "~/Library/Application Support/Claude/claude_desktop_config.json"
```

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

Fully quit Claude Desktop (⌘Q — not close), reopen, and the 23 devlake
tools should appear in the MCP menu.

### First prompts to try

```
Using the devlake MCP, show synthetic__status, then dora__performance_level
for the last 90 days.

Show me the Architecture-Code Gap across the synthetic team — who's highest
and lowest and how does their PR iteration pattern compare?

Compare DORA metrics between AI power users and traditional engineers.

If I filter out synthetic data, what does my personal DORA performance
look like on sherman94062/argus specifically?
```

More in [docs/sample-queries.md](./docs/sample-queries.md).

---

## 8 · Day-2 operations

### Pull newer GitHub data

```bash
python scripts/trigger-pipeline.py
```

Synthetic data is independent — re-running ingest doesn't disturb it.

### Regenerate the synthetic layer

```bash
python scripts/seed-synthetic-team.py --reset
```

### Remove synthetic data entirely

```bash
python scripts/seed-synthetic-team.py --purge
```

### Full reset

```bash
docker compose --env-file devlake-config/env down -v   # destroys all data
./scripts/bootstrap.sh
python scripts/seed-synthetic-team.py
```

### Updating the MCP server code

If you edit anything under `mcp/`:

```bash
docker compose --env-file devlake-config/env build mcp-server
docker compose --env-file devlake-config/env up -d mcp-server
```

Claude Desktop picks up the new tools on its next restart.

---

## Troubleshooting reference

| You see | Try |
|---------|-----|
| `DevLake POST /plugins/github/connections failed (400): validation failed … AuthMethod` | Ensure `authMethod: "AccessToken"` is in the connection body (already in the script) |
| `GithubRepo.GithubId` required | Script fetches this from `api.github.com/repos/…`; means the PAT can't see the repo |
| `failed to get Git URL / Invalid Git URL` | Scope not PATCHed with `cloneUrl`; rerun `configure-github.py` |
| `field requires user:email / read:user` | Regenerate PAT with `read:user` |
| `address already in use :8811` | The dockerized MCP server is already running — don't run it locally too |
| `Some MCP servers could not be loaded: devlake` in Claude Desktop | Config uses raw `url`; switch to `mcp-remote` bridge |
| `Unknown column 'source' in where clause` | Seeder must run once to ALTER the table; rerun |
| `Unknown column 'user_id' in field list` on `pull_request_comments` | Old seeder code; pull latest (DevLake uses `account_id`) |
| `NoSuchColumnError: Could not locate column 'table_name'` | MySQL 8 case sensitivity; pull latest (queries now use `LOWER(...)`) |

---

## Reference

- Apache DevLake docs: <https://devlake.apache.org/docs>
- DORA setup: <https://devlake.apache.org/docs/DORA>
- DevLake domain schema: <https://devlake.apache.org/docs/DataModels/DevLakeDomainLayerSchema>
- FastMCP: <https://github.com/jlowin/fastmcp>
- mcp-remote (HTTP bridge for Claude Desktop): <https://www.npmjs.com/package/mcp-remote>
- DX Core 4 framework: <https://getdx.com/research/core-four>
- Mark Nelson on Architecture-Code Gap: <https://www.linkedin.com/in/marknelsonmx>
