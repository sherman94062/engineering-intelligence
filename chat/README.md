# chat — Streamlit chat UI

A browser-based chat that talks to the local devlake MCP server via Claude.
Sits alongside the Grafana dashboard so presenters don't have to context-
switch to Claude Desktop during a demo.

## Requirements

- The devlake stack must be running (`docker compose up -d`).
- `ANTHROPIC_API_KEY` available in `~/.env` or `devlake-config/env`.

## Run

```bash
cd chat
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>.

## How it works

1. On startup the app connects to the MCP server at `MCP_URL`
   (default `http://localhost:8811/mcp`) and lists all 23 tools.
2. On each message it calls Anthropic's Messages API with those tools.
3. When Claude emits a `tool_use` block, the app executes it against the
   MCP server and feeds the result back.
4. The loop continues until Claude stops calling tools.

The MCP protocol handshake happens inside the app — Anthropic's API never
sees the local MCP URL, so this works without exposing the MCP publicly.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `MCP_URL` | `http://localhost:8811/mcp` | Local MCP endpoint |
| `ANTHROPIC_MODEL` | `claude-opus-4-6` | Change to sonnet for speed |
| `ANTHROPIC_MAX_TOKENS` | `4096` | Per message |

## Why Streamlit

Fast to build, first-class chat primitives, local dev loop of "save file
→ browser auto-reloads." Not intended for production — for that you'd
build a React/Next app against the same tool-use loop.
