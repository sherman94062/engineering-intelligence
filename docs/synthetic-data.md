# Synthetic team layer

## Why

Real solo repos produce authentic commit + deploy signal but can't show
team dynamics — no PR reviewers, no contributor variance, no incident
history, no AI-adoption spread. The synthetic layer fills those gaps while
keeping the real data clearly distinguishable.

## Tagging

Every synthetic row has `source = 'synthetic'` (a nullable column the
seeder adds to `accounts`, `commits`, `repo_commits`, `pull_requests`,
`pull_request_commits`, `pull_request_comments`, `cicd_pipelines`,
`cicd_pipeline_commits`, `issues`, `board_issues`). Real rows keep
`source = NULL`.

Every MCP query tool accepts `include_synthetic: bool = True`. Set it to
`False` to see real-only data.

## Sources of truth

- `synthetic/team-profiles.yml` — 12 engineers across 4 personas
- `synthetic/incident-scenarios.yml` — 4 incident archetypes driving
  CFR and TTR

## Seeder

```bash
python scripts/seed-synthetic-team.py               # fresh seed
python scripts/seed-synthetic-team.py --reset       # purge + reseed
python scripts/seed-synthetic-team.py --purge       # delete only
python scripts/seed-synthetic-team.py --dry-run     # preview
python scripts/seed-synthetic-team.py --engineers 20
python scripts/seed-synthetic-team.py --lookback-days 365
python scripts/seed-synthetic-team.py --ai-adoption-rate 0.8
```

## What gets written

| Table                     | Rows per run (default, 12 eng × 180d) |
|---------------------------|----------------------------------------|
| accounts                  | 12                                     |
| commits                   | ~3 500                                 |
| repo_commits              | ~3 500                                 |
| pull_requests             | ~900                                   |
| pull_request_commits      | ~3 500                                 |
| pull_request_comments     | ~4 000                                 |
| cicd_pipelines (deploy)   | ~900                                   |
| cicd_pipeline_commits     | ~900                                   |
| issues (INCIDENT)         | ~75                                    |

Numbers are approximate — persona parameters randomise volumes.

## Architecture-Code Gap

AI Power User and AI Adopter personas are configured with elevated
`pr_iterations` and `post_merge_churn_rate`. That makes the
`team__architecture_code_gap` tool produce a meaningful spread when compared
against Traditional and Senior Reviewer personas.

## Determinism

The seed is fixed at the top of `team-profiles.yml` (`seed: 20260416`).
Reruns produce identical synthetic data so dashboards and notebooks remain
reproducible. Change the seed to get a different draw.

## Gotchas

- Seed **after** the first real GitHub pipeline run — the seeder references
  real `repos.id` values.
- `docker compose down -v` wipes everything. Re-seed after.
- If DevLake upgrades add new not-null columns to the target tables, the
  seeder will need matching entries; the `INSERT IGNORE` used today skips
  rows that fail schema checks but prints a DB error.
