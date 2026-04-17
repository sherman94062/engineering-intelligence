# DevLake setup

## First-run walkthrough

```bash
cp devlake-config/env.example devlake-config/env
$EDITOR devlake-config/env       # GITHUB_TOKEN + passwords
./scripts/bootstrap.sh
```

`bootstrap.sh` does four things:

1. `docker compose --env-file devlake-config/env up -d`
2. Waits for `GET http://localhost:8080/ping` to succeed
3. Runs `scripts/configure-github.py` to create/update the GitHub connection,
   scopes (one per repo listed in `GITHUB_REPOS`), and the
   `github-blueprint` blueprint
4. Runs `scripts/trigger-pipeline.py` to kick off a collection run and poll
   until it completes

## What to verify after bootstrap

- Grafana home: <http://localhost:3002> — should load and render the DORA
  Overview dashboard (DORA folder). Counts will be near-zero until the
  pipeline finishes ingesting.
- DevLake config UI: <http://localhost:4000> — log in with
  `DEVLAKE_ADMIN_USER` / `DEVLAKE_ADMIN_PASS` from env. Confirm the
  GitHub connection and blueprint are present.
- DevLake API: `curl http://localhost:8080/plugins/github/connections`
  should return a non-empty list.

## Re-running ingest

```bash
python scripts/trigger-pipeline.py
```

Or from the config UI: Blueprints → github-blueprint → Run now.

## Tuning the GitHub scope

Edit `GITHUB_REPOS` in `devlake-config/env` (comma-separated) and re-run
`configure-github.py`. It's idempotent — connections and scopes are updated
in place rather than duplicated.

## Reset

```bash
docker compose down -v      # destroys all data including synthetic
./scripts/bootstrap.sh
python scripts/seed-synthetic-team.py
```
