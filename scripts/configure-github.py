#!/usr/bin/env python3
"""Configure a DevLake GitHub connection + scopes + blueprint.

Idempotent: running it twice won't duplicate connections; it updates in place.
Reads GITHUB_TOKEN, GITHUB_ORG_OR_USER, GITHUB_REPOS from devlake-config/env.
"""

from __future__ import annotations

import sys
from typing import Any

from _devlake_api import DevLakeClient, env_or_die, os

CONNECTION_NAME = "github-local"


def find_connection(client: DevLakeClient, name: str) -> dict[str, Any] | None:
    conns = client.get("/plugins/github/connections") or []
    for c in conns:
        if c.get("name") == name:
            return c
    return None


def upsert_connection(client: DevLakeClient, token: str) -> dict[str, Any]:
    existing = find_connection(client, CONNECTION_NAME)
    payload = {
        "name": CONNECTION_NAME,
        "endpoint": "https://api.github.com/",
        "token": token,
        "proxy": "",
        "rateLimitPerHour": 4000,
    }
    if existing:
        conn_id = existing["id"]
        print(f"  updating existing GitHub connection id={conn_id}")
        return client.patch(f"/plugins/github/connections/{conn_id}", json=payload)
    print("  creating GitHub connection")
    return client.post("/plugins/github/connections", json=payload)


def upsert_scopes(
    client: DevLakeClient,
    conn_id: int,
    owner: str,
    repos: list[str],
) -> list[dict[str, Any]]:
    existing = {
        s["name"]: s
        for s in (client.get(f"/plugins/github/connections/{conn_id}/scopes") or [])
    }
    scopes = []
    for repo in repos:
        full = f"{owner}/{repo}"
        body = {
            "id": full,
            "name": full,
            "connectionId": conn_id,
            "owner": owner,
            "repo": repo,
        }
        if full in existing:
            print(f"  scope {full} exists")
            scopes.append(existing[full])
        else:
            print(f"  creating scope {full}")
            scopes.append(
                client.post(
                    f"/plugins/github/connections/{conn_id}/scopes",
                    json=[body],
                )
            )
    return scopes


def upsert_blueprint(
    client: DevLakeClient,
    conn_id: int,
    owner: str,
    repos: list[str],
) -> dict[str, Any]:
    name = "github-blueprint"
    existing = next(
        (
            b
            for b in (client.get("/blueprints") or {}).get("blueprints", [])
            if b.get("name") == name
        ),
        None,
    )

    scopes = [
        {"scopeId": f"{owner}/{repo}", "scopeName": f"{owner}/{repo}"} for repo in repos
    ]
    body = {
        "name": name,
        "projectName": "",
        "mode": "NORMAL",
        "enable": True,
        "cronConfig": "0 0 * * *",
        "isManual": False,
        "skipOnFail": True,
        "timeAfter": None,
        "connections": [
            {
                "pluginName": "github",
                "connectionId": conn_id,
                "scopes": scopes,
            }
        ],
    }
    if existing:
        bp_id = existing["id"]
        print(f"  updating existing blueprint id={bp_id}")
        return client.patch(f"/blueprints/{bp_id}", json=body)
    print("  creating blueprint")
    return client.post("/blueprints", json=body)


def main() -> int:
    token = env_or_die("GITHUB_TOKEN")
    owner = env_or_die("GITHUB_ORG_OR_USER")
    repos_csv = os.getenv("GITHUB_REPOS", "")
    repos = [r.strip() for r in repos_csv.split(",") if r.strip()]
    if not repos:
        print("error: GITHUB_REPOS is empty", file=sys.stderr)
        return 1

    client = DevLakeClient.from_env()
    client.wait_ready()

    print(f"==> GitHub connection '{CONNECTION_NAME}'")
    conn = upsert_connection(client, token)
    conn_id = conn["id"]

    print(f"==> Scopes ({len(repos)} repos under {owner})")
    upsert_scopes(client, conn_id, owner, repos)

    print("==> Blueprint")
    bp = upsert_blueprint(client, conn_id, owner, repos)
    print(f"   blueprint id={bp.get('id')} ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
