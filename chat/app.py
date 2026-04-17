"""Streamlit chat app — talks to the devlake MCP server via Claude.

Sits alongside the Grafana dashboard at http://localhost:8501. Asks
Anthropic's Messages API to answer engineering-intelligence questions,
routing tool calls through the local MCP server at http://localhost:8811.

Run locally:
    cd chat
    pip install -r requirements.txt
    streamlit run app.py

Environment variables:
    ANTHROPIC_API_KEY   required
    MCP_URL             default http://localhost:8811/mcp
    ANTHROPIC_MODEL     default claude-opus-4-6
"""

from __future__ import annotations

# --- Streamlit helpers must be imported before everything else so the
# layout is set before any other st.* call ---
import streamlit as st

st.set_page_config(
    page_title="DevLake — Engineering Intelligence Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from fastmcp import Client as MCPClient

# Load .env from repo root or ~/.env so ANTHROPIC_API_KEY is picked up
REPO_ROOT = Path(__file__).resolve().parents[1]
for candidate in [REPO_ROOT / "devlake-config" / "env", Path.home() / ".env", REPO_ROOT / ".env"]:
    if candidate.exists():
        load_dotenv(candidate, override=False)

MCP_URL = os.getenv("MCP_URL", "http://localhost:8811/mcp")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))

SYSTEM_PROMPT = """You are an engineering intelligence assistant for a local
Apache DevLake instance. You have read-only tools that query DORA metrics,
PR analytics, contributor activity, team dynamics (including a novel
Architecture-Code Gap proxy), and the underlying schema.

When answering:
- Prefer composing multiple tools to give a richer answer.
- Cite the tool(s) you called and the key numbers they returned.
- Be concise and direct; this is an executive-style interface.
- The `include_synthetic` flag on every tool defaults to True — flip it to
  False to see real-only data.
- If asked a "what if" or hypothetical, reason from the data you fetched."""


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages: list[dict[str, Any]] = []
if "mcp_tools" not in st.session_state:
    st.session_state.mcp_tools = None


# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------

async def _fetch_mcp_tools() -> list[dict[str, Any]]:
    async with MCPClient(MCP_URL) as client:
        tools = await client.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in tools
        ]


async def _call_mcp_tool(name: str, args: dict[str, Any]) -> str:
    async with MCPClient(MCP_URL) as client:
        result = await client.call_tool(name, args)
    # Result content is a list of content blocks; stringify for the LLM.
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
        else:
            parts.append(str(block))
    return "\n".join(parts) if parts else "(no content)"


def load_tools() -> list[dict[str, Any]]:
    if st.session_state.mcp_tools is None:
        st.session_state.mcp_tools = asyncio.run(_fetch_mcp_tools())
    return st.session_state.mcp_tools


# ---------------------------------------------------------------------------
# Sidebar — starter prompts, settings, reset
# ---------------------------------------------------------------------------

STARTER_PROMPTS = [
    ("Team overview", "Using the devlake MCP, show synthetic__status, then dora__performance_level for the last 90 days. Summarize what band we're in per repo."),
    ("AI vs Traditional", "Compare AI Power Users vs Traditional engineers on the team. Do the fast-shipping AI users pay for it with a higher change failure rate? Show the numbers."),
    ("Architecture-Code Gap", "Who has the highest Architecture-Code Gap score, and what does their PR iteration pattern look like? Explain what this metric means."),
    ("Real vs Synthetic", "If I exclude synthetic data, what does my personal DORA performance look like? Then contrast that with the blended picture."),
    ("What-if scenario", "If 80% of the team became AI Power Users, what would happen to CFR and cycle time based on the current cohort numbers? What metric should I worry about first?"),
]

with st.sidebar:
    st.subheader("About")
    st.caption(
        "This chat talks to the local devlake MCP server. Every answer is "
        "backed by a real tool call against your DevLake MySQL. "
        "Pair it with the [Grafana dashboard](http://localhost:3002/d/devlake-dora-overview/)."
    )

    st.subheader("Starter prompts")
    for label, prompt in STARTER_PROMPTS:
        if st.button(label, key=f"starter_{label}", use_container_width=True):
            st.session_state.pending_prompt = prompt
            st.rerun()

    st.subheader("Session")
    st.caption(f"Model: `{MODEL}`")
    st.caption(f"MCP endpoint: `{MCP_URL}`")
    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("DevLake — Engineering Intelligence Chat")
st.caption(
    "Ask questions about your engineering data. The answers are grounded in "
    "live MCP tool calls against your local Apache DevLake."
)

if not os.getenv("ANTHROPIC_API_KEY"):
    st.error("ANTHROPIC_API_KEY is not set. Add it to ~/.env or devlake-config/env and restart.")
    st.stop()

try:
    tools = load_tools()
except Exception as exc:
    st.error(f"Could not reach the MCP server at {MCP_URL}: {exc}")
    st.stop()

st.caption(f"🔧 {len(tools)} MCP tools available")


# ---------------------------------------------------------------------------
# Render history
# ---------------------------------------------------------------------------

def render_content_blocks(blocks: list[dict[str, Any]]) -> None:
    for block in blocks:
        bt = block.get("type")
        if bt == "text" and block.get("text"):
            st.markdown(block["text"])
        elif bt == "tool_use":
            tool_name = block.get("name", "?")
            tool_input = block.get("input", {})
            with st.expander(f"🔧 called `{tool_name}`", expanded=False):
                if tool_input:
                    st.code(json.dumps(tool_input, indent=2), language="json")
                else:
                    st.caption("(no arguments)")
        elif bt == "tool_result":
            with st.expander("📊 tool result", expanded=False):
                content = block.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(
                        str(c.get("text", c)) if isinstance(c, dict) else str(c)
                        for c in content
                    )
                st.code(str(content)[:4000], language="text")


for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message("assistant" if role == "assistant" else "user"):
        content = msg["content"]
        if isinstance(content, str):
            st.markdown(content)
        else:
            render_content_blocks(content)


# ---------------------------------------------------------------------------
# Input + tool-use loop
# ---------------------------------------------------------------------------

def run_conversation(user_text: str) -> None:
    """Append user message, run the tool-use loop, append assistant response."""
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    anthropic = Anthropic()

    # Convert history into Anthropic message format.
    api_messages: list[dict[str, Any]] = []
    for m in st.session_state.messages:
        api_messages.append({"role": m["role"], "content": m["content"]})

    with st.chat_message("assistant"):
        for hop in range(8):  # safety cap
            response = anthropic.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=api_messages,
            )
            # Serialize assistant content blocks into plain dicts.
            assistant_blocks: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_blocks.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
            render_content_blocks(assistant_blocks)
            api_messages.append({"role": "assistant", "content": assistant_blocks})
            st.session_state.messages.append({"role": "assistant", "content": assistant_blocks})

            if response.stop_reason != "tool_use":
                break

            # Run every tool call in this hop and collect results.
            tool_result_blocks: list[dict[str, Any]] = []
            for block in assistant_blocks:
                if block["type"] != "tool_use":
                    continue
                try:
                    result_text = asyncio.run(_call_mcp_tool(block["name"], block["input"] or {}))
                except Exception as exc:
                    result_text = f"Error calling {block['name']}: {exc}"
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result_text,
                    }
                )
            render_content_blocks(tool_result_blocks)
            api_messages.append({"role": "user", "content": tool_result_blocks})
            st.session_state.messages.append({"role": "user", "content": tool_result_blocks})
        else:
            st.warning("Stopped after 8 tool-use hops — likely a loop.")


# Pending prompt from sidebar
pending = st.session_state.pop("pending_prompt", None)
if pending:
    run_conversation(pending)

user_input = st.chat_input("Ask about DORA, PRs, incidents, the team...")
if user_input:
    run_conversation(user_input)
