# Synthetic data layer

DevLake ingests real GitHub activity, but solo repos can't produce team-scale
signals (PR reviews, contributor variance, incidents, AI-adoption spread).
This layer injects a believable 12-engineer team on top of the real repos.

## Tagging

Every synthetic row carries `source = 'synthetic'`. Real rows carry
`source IS NULL` (DevLake's default). Every MCP query exposes an
`include_synthetic` flag so real-only views are always available.

## Files

- `team-profiles.yml` — persona definitions (4 archetypes, 12 engineers total)
- `incident-scenarios.yml` — incident archetypes driving CFR/TTR

## Persona mix

| Persona         | Count | Distinctive signature                          |
|-----------------|-------|------------------------------------------------|
| AI Power User   | 3     | Batch commits, large diffs, high PR iteration |
| AI Adopter      | 4     | Mixed pattern, moderate diffs                 |
| Traditional     | 3     | Small focused commits, long review cycles     |
| Senior Reviewer | 2     | Few commits, high comment volume              |

## Regenerating

```bash
# Full reset: purge then re-seed with current YAML
python scripts/seed-synthetic-team.py --reset

# Fresh insert (assumes nothing synthetic exists yet)
python scripts/seed-synthetic-team.py

# Purge only, leaves real data intact
python scripts/seed-synthetic-team.py --purge
```

## Notes

- Seed the synthetic layer **after** the first real GitHub pipeline run
  completes so `repos` is populated — see Gotchas in `CLAUDE.md`.
- `docker compose down -v` destroys everything; re-seed after that.
