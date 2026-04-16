# Sample Claude prompts

Once the MCP server is connected to Claude Desktop or Claude Code, these
prompts are known-good against the tool surface.

## DORA fundamentals (real data)

```
What are my DORA metrics across all repos for the last 90 days?
Compare deployment frequency this month vs last month — just the top 3 repos.
Show me the lead time trend for mcp-security-stack week over week.
Which repo has the worst change failure rate right now, and what do the
incidents look like?
```

## AI code signal (real data)

```
Show me commits that look AI-generated (large batch changes) and how they
correlate with post-merge churn.

What percentage of my commits show AI batch-generation patterns vs manual
typing?

Which repos have the highest post-merge churn rate and is it correlated with
large-diff commits?
```

## Team dynamics (synthetic layer)

```
Compare DORA metrics between AI power users and traditional engineers on
the team.

Which engineers have the highest Architecture-Code Gap score and what does
their PR iteration pattern look like?

Show me the bus factor risk across repos — which files have only one
contributor?

What's the AI adoption spread across the team? Show me highest to lowest.
```

## Incident and reliability

```
Which repo has the highest change failure rate and what does the incident
history look like?

Show me all incidents in the last 90 days with their TTR and linked deploy.

What's the relationship between AI-heavy deploys and incident rate?
```

## Blended

```
Give me an Architecture-Code Gap estimate for the whole team, broken down
by engineer type (AI power user vs traditional).

If I filter out synthetic data, what does my personal DORA performance
look like?

Pretend you're an engineering VP presenting to a board. Summarize the
team's engineering health based on this data.
```

## Raw SQL escape hatch

```
Use schema__query to run: select count(*), source from commits group by
source.
```

The MCP server will run that as-is (it's a SELECT) and return results. Any
query containing INSERT/UPDATE/DELETE/DROP/ALTER/etc. is rejected.
