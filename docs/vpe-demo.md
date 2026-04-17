# 15-minute VPE demo

A scripted walkthrough for showing this platform to a VP of Engineering
candidate (or anyone evaluating it against DX). Designed to be read
near-verbatim, or memorized the night before.

**Audience**: a VPE at a 50-500 engineer company who has either already
evaluated DX or is DX-curious.

**Goal of the demo**: by minute 15 they should believe
(a) we can match DX on code-derived metrics, (b) we have something
genuinely novel on the AI-era side, and (c) the conversational interface
is a real second act, not a gimmick.

---

## Pre-demo checklist (5 min before they join)

- [ ] Stack is up: `docker compose --env-file devlake-config/env ps`
      all 5 services healthy
- [ ] Dashboard loads: <http://localhost:3002/d/devlake-dora-overview/>
      (admin / admin) — panels populated, no red triangles
- [ ] Claude Desktop is open, `devlake` tools visible in MCP menu
- [ ] Second screen / window arrangement:
      **left**: browser at dashboard
      **right**: Claude Desktop, empty conversation
- [ ] Water glass. No Slack notifications.

One-minute recovery if something's broken:
```bash
docker compose --env-file devlake-config/env restart grafana mcp-server
```

---

## Minute 0-2 · Cold open (dashboard)

**Open on the dashboard, filter set to Last 90 days, All repos,
Synthetic data = true.**

> "This is a self-hosted stand-in for DX I built in a weekend. It
> ingests real GitHub data via Apache DevLake, layers a simulated
> 12-engineer team on top, and exposes everything through a local MCP
> server so Claude can query it in natural language.
>
> The four numbers at the top are the DORA metrics — Google's
> four-metric framework. Color-coded to the 2023 DORA report bands:
> Elite, High, Medium, Low.
>
> Right now we're looking at the blended picture — real + synthetic."

*(Point at each stat briefly as you say the name.)*

---

## Minute 2-5 · The synthetic-data reveal

**Flip the `Synthetic data` toggle from `true` to `false`.**

> "Watch what happens when I filter to real data only."

**Wait 2 seconds. Panels go empty or show near-zero numbers.**

> "This is what DX would see pointed at a solo developer's repos —
> which is the constraint I built against. There are no deploys, no
> PR reviewers, no incidents. Just commits. Any engineering intelligence
> platform pointed here would be unusable.
>
> The synthetic layer is how we get from "unusable" to "demonstrable"
> without fabricating anything. Every synthetic row is tagged in the
> database with `source = 'synthetic'`, so we can always separate them.
> It's not a mock — it writes into the same tables real data lives in,
> respects the same foreign keys, obeys the same ID conventions."

**Flip synthetic back to `true`.**

> "Twelve synthetic engineers, four personas — AI Power Users, AI
> Adopters, Traditionals, Senior Reviewers — each parameterized by
> commit cadence, diff size, PR iteration count, incident probability.
> Deterministic seed. The dashboard you're looking at is reproducible
> bit-for-bit."

---

## Minute 5-8 · DORA bands + repo health

**Scroll to the "DORA band per repo" table.**

> "Google's classification lands each of these repos in a band.
> Mcp-security-stack is High, argus is High, nl-to-sql-agent is Medium.
> The color coding comes straight from the DORA 2023 thresholds — 13+
> deploys in the window, mean lead time under 24 hours, that's High."

**Scroll to "Deploys per week" timeseries.**

> "Cadence is consistent — no silent weeks, no unusual bursts. On a
> real team you'd use this to catch things like freeze weeks that
> didn't unfreeze or a CI outage nobody escalated."

---

## Minute 8-11 · The AI-era row (the differentiator)

**Scroll to the "AI-era signals" row.**

> "This row is the reason this project exists, and the reason I
> wouldn't just pay for DX."

*(Let them read the three panels. Give them 5 seconds.)*

> "Left panel is the Architecture-Code Gap score per engineer. Mark
> Nelson — CTO at MX — coined this. His observation is that
> AI-generated plans get abandoned mid-implementation more than
> human-authored ones. At MX he measures it with IDE telemetry. I
> don't have that, so I proxy it with two signals I do have: how many
> review iterations a PR took before merge, and how often the files
> it touched get modified again within a week. High ACG means high
> rework.
>
> Middle panel is AI adoption spread — engineers sorted by how many
> 'batch' commits they authored, where batch means over 250 lines. It's
> a rough AI-generation detector because humans don't usually type 250
> lines at once.
>
> Right panel is the cohort breakdown. Buckets every engineer into AI
> Power User / AI Adopter / Traditional by their mean commit diff, and
> then compares cohort-level metrics. Notice the AI Power Users ship in
> 62 hours cycle-time; Traditionals are at 285 hours. Four-and-a-half
> times faster. But — hold that thought, it matters for the CLI bit."

---

## Minute 11-15 · Switch to Claude

**Hard switch to Claude Desktop. Make the screen switch visible to the
audience.**

> "Dashboards have a ceiling: they can only answer questions you
> anticipated building a panel for. Here's what unlocks when the same
> data is behind an AI tool."

### Prompt 1 — a question the dashboard can answer, just to show it works

Type:

```
Using the devlake MCP, show me synthetic__status and then
dora__performance_level for the last 90 days.
```

**Wait for response. Read the relevant lines out loud.**

> "So we've confirmed the data shape — around 8,000 synthetic commits,
> 1,700 PRs, 190 incidents — and the DORA band per repo. Same numbers
> as the dashboard. That's parity, not magic."

### Prompt 2 — a question the dashboard can't answer

Type:

```
Earlier I said AI Power Users ship in 62h vs Traditionals at 285h.
Does that faster cycle come at the cost of quality? Compare their
change failure rates, and if CFR is higher for AI Power Users, show
me the top 3 incidents that correlate with their deploys.
```

**Wait. Claude will chain `team__ai_vs_traditional` →
`dora__change_failure_rate` → `team__incident_summary` and narrate
a coherent answer.**

> "This is a three-tool chain the dashboard can't do in one shot. The
> answer bridges four concepts — speed, quality, persona, incidents.
> DX has dashboards for each of those, but asking the combined
> question requires the human to do the synthesis."

### Prompt 3 — the "what if" nobody else can answer

Type:

```
Pretend I'm about to invest heavily in Claude Code rollout for
the whole team. Model what happens to CFR and cycle time if 80% of
the team becomes AI Power Users. What should I worry about? Be
specific about which metric will tank first.
```

**Wait. Claude will reason from the cohort data, project, and
probably flag ACG or CFR as the concern.**

> "This is the 'board meeting prep' question. The answer isn't
> pre-computed — Claude is actually reasoning from the cohort data
> and projecting. You can push back on the logic, ask for sources,
> rerun with different assumptions. DX gives you a dashboard; this
> gives you a thought partner."

---

## Close (30 seconds)

> "To summarize: we have DORA coverage on par with DX on the code
> side. We're missing the survey and calendar data that DX sells on
> the people side — that's a genuine gap I'm not pretending to close.
> What we have that DX doesn't is a synthetic team you can tune, a
> novel AI-era metric — the Architecture-Code Gap — and a conversational
> interface that changes what 'asking your data a question' looks like.
>
> The stack is open source, under MIT license, and running on my
> laptop right now. I'm happy to hand you a link or spin up a
> Codespace."

---

## Likely pushback — have answers ready

| They ask | You say |
|---|---|
| *"How is this different from DX?"* | "DX is a polished product with a survey engine I don't have. We're stronger on code signal extensibility and have an AI-era metric DX doesn't. If your priority is the people side — cognitive load, flow, burnout — pay DX. If your priority is deep code-signal analysis plus custom queries, this is better." |
| *"The synthetic team is fake — doesn't this produce fake insights?"* | "The synthetic layer exists because solo repos structurally can't produce team signals. For a real 50-engineer team, I'd skip the seeder entirely and run on real data. The synthetic piece is for demos, metric prototyping, and what-if scenarios." |
| *"Why DevLake and not building something from scratch?"* | "DevLake solves the GitHub-API-to-normalized-schema problem. That's about 2 years of Go engineering. Rebuilding it wouldn't change the thesis — all the differentiation is in the MCP layer and the AI-era metrics, which are pure additions." |
| *"How does this scale to 500 engineers?"* | "MySQL + DevLake scale to thousands of repos — apache.org uses it internally. The MCP server is stateless. The thing that wouldn't scale is me being oncall for it, which is where you'd either pay DX or staff a platform team." |
| *"Is the Architecture-Code Gap metric validated?"* | "No — it's a proxy. Mark Nelson's underlying observation has real telemetry behind it at MX. My version is two-signal inference from commit data. Treat it as hypothesis generation, not a closed science. That said, the correlation it surfaces in our synthetic team matches the persona design, so the math isn't broken." |
| *"What's your moat?"* | "Against DX: none, and they have a head start on polish. Against a hypothetical competitor building something similar: the combination of DevLake foundation + MCP composability + the AI-era metric direction + OSS license. The moat is that I'm open about how it works." |

---

## If you have extra time (optional minute 15-18)

Show the read-only SQL escape hatch. Type in Claude:

```
Use schema__query to run:
  SELECT author_name, COUNT(*) AS n
  FROM commits
  WHERE authored_date > DATE_SUB(NOW(), INTERVAL 30 DAY)
  GROUP BY author_name
  ORDER BY n DESC;
```

> "One more thing. Every dashboard is ultimately a SQL query. DX hides
> that; we expose it. Anyone who can read SQL can ask anything the
> schema can answer. No mutation — we reject INSERT/UPDATE/DELETE — but
> every SELECT is fair game."

---

## Demo variants

### If the VPE has a real GitHub org they want to show

Pre-demo prep: run `scripts/configure-github.py` pointed at *their* token,
with their repos. They'll see their real DORA band in minute 0. This is
**the most compelling version** if you can get a PAT from them in advance.

### If the VPE is non-technical (e.g., a founder-CEO)

Skip minute 8-11 (the AI-era row) — it's dense. Spend more time in the
Claude chat, especially Prompt 3 ("what if"). The narrative answers land
with non-engineers better than the cohort table.

### If the VPE is very technical (e.g., a former staff engineer now VPE)

Offer them the `schema__query` tool early. They'll want to write SQL
themselves. Let them drive for 5 minutes. This is a conversion move.

---

## Follow-up assets

After the demo, send them:

1. Link to the repo: <https://github.com/sherman94062/engineering-intelligence>
2. Link to WALKTHROUGH.md for the setup path
3. Link to this file so they can re-run the demo themselves

---

## Presenter notes

- Tempo > coverage. It's fine to skip a panel if you're running long.
- Don't over-apologize for what's missing vs DX. The point is the
  conceptual shift, not the feature checklist.
- The emotional center of the demo is **Prompt 2**. If one moment lands,
  make it that one.
- If Claude is slow (API latency), that's fine. Comment on the thinking
  happening: *"It's chaining three tools — you can see in the tool-call
  log."* That's a feature, not a bug.
