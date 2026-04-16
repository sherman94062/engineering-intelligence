#!/usr/bin/env python3
"""Configure a DevLake GitHub connection + scopes + blueprint.

Idempotent: running it twice won't duplicate connections; it updates in place.
Reads GITHUB_TOKEN, GITHUB_ORG_OR_USER, GITHUB_REPOS from devlake-config/env.
"""

from __future__ import annotations

import sys
from typing import Any

import requests

from _devlake_api import DevLakeClient, env_or_die, os

CONNECTION_NAME = "github-local"
SCOPE_CONFIG_NAME = "code-cicd-review"
# Entities we want DevLake to collect. TICKET is intentionally omitted so
# repos that have Issues disabled on GitHub don't fail the pipeline.
SCOPE_CONFIG_ENTITIES = ["CODE", "CICD", "CODEREVIEW", "CROSS"]


def find_connection(client: DevLakeClient, name: str) -> dict[str, Any] | None:
    conns = client.get("/plugins/github/connections") or []
    for c in conns:
        if c.get("name") == name:
            return c
    return None


def upsert_scope_config(client: DevLakeClient, conn_id: int) -> int:
    """Create or reuse a scope config that omits TICKET. Returns its id."""
    path = f"/plugins/github/connections/{conn_id}/scope-configs"
    existing = client.get(path)
    if isinstance(existing, dict):
        existing = existing.get("data") or existing.get("scope_configs") or []
    if isinstance(existing, list):
        for sc in existing:
            if isinstance(sc, dict) and sc.get("name") == SCOPE_CONFIG_NAME:
                print(f"  scope config '{SCOPE_CONFIG_NAME}' exists id={sc.get('id')}")
                return int(sc["id"])
    body = {
        "name": SCOPE_CONFIG_NAME,
        "entities": SCOPE_CONFIG_ENTITIES,
        "connectionId": conn_id,
    }
    print(f"  creating scope config '{SCOPE_CONFIG_NAME}' (entities={SCOPE_CONFIG_ENTITIES})")
    created = client.post(path, json=body)
    if isinstance(created, dict) and "id" in created:
        return int(created["id"])
    # Some versions wrap under "data"
    if isinstance(created, dict) and isinstance(created.get("data"), dict):
        return int(created["data"]["id"])
    raise RuntimeError(f"unexpected scope-config response: {created!r}")


def upsert_connection(client: DevLakeClient, token: str) -> dict[str, Any]:
    existing = find_connection(client, CONNECTION_NAME)
    payload = {
        "name": CONNECTION_NAME,
        "endpoint": "https://api.github.com/",
        "authMethod": "AccessToken",
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


def _unwrap_scope_list(raw: Any) -> list[dict[str, Any]]:
    """DevLake's scopes endpoint returns a list in some versions and
    {"scopes": [...]} or {"data": [...]} in others. Normalise."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict)]
    if isinstance(raw, dict):
        for key in ("scopes", "data", "results"):
            inner = raw.get(key)
            if isinstance(inner, list):
                return [s for s in inner if isinstance(s, dict)]
    return []


def _scope_key(scope: dict[str, Any]) -> str | None:
    for key in ("name", "fullName", "id"):
        val = scope.get(key)
        if isinstance(val, str):
            return val
    return None


def _gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_github_repo(token: str, owner: str, repo: str) -> dict[str, Any] | None:
    """Fetch full repo metadata from GitHub. Returns None on 404."""
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_gh_headers(token),
        timeout=30,
    )
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise RuntimeError(
            f"GitHub lookup for {owner}/{repo} failed "
            f"({resp.status_code}): {resp.text}"
        )
    return resp.json()


def list_all_github_repos(token: str, owner: str) -> list[tuple[str, int]]:
    """Page through /users/:owner/repos and return (name, id) for each."""
    out: list[tuple[str, int]] = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/users/{owner}/repos",
            headers=_gh_headers(token),
            params={"per_page": 100, "page": page, "type": "owner"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GitHub list-repos for {owner} failed "
                f"({resp.status_code}): {resp.text}"
            )
        batch = resp.json()
        if not batch:
            break
        out.extend((r["name"], int(r["id"])) for r in batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def _scope_github_id(scope: dict[str, Any]) -> int | None:
    for key in ("githubId", "github_id", "id"):
        val = scope.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


def upsert_scopes(
    client: DevLakeClient,
    conn_id: int,
    owner: str,
    repos: list[str],
    token: str,
    scope_config_id: int,
) -> list[dict[str, Any]]:
    """Returns a normalised list of scope dicts that always include the
    numeric githubId — downstream callers need it to wire blueprints."""
    raw = client.get(f"/plugins/github/connections/{conn_id}/scopes")
    existing_by_name = {
        key: scope
        for scope in _unwrap_scope_list(raw)
        if (key := _scope_key(scope))
    }

    to_create: list[dict[str, Any]] = []
    skipped: list[str] = []
    for repo in repos:
        full = f"{owner}/{repo}"
        meta = fetch_github_repo(token, owner, repo)
        if meta is None:
            print(f"  ! {full} not found on GitHub — skipping")
            skipped.append(full)
            continue
        github_id = int(meta["id"])
        print(f"  resolved {full} -> githubId={github_id}")
        to_create.append(
            {
                "id": full,
                "name": full,
                "connectionId": conn_id,
                "fullName": full,
                "owner": owner,
                "repo": repo,
                "githubId": github_id,
                "HTMLUrl": meta.get("html_url", ""),
                "htmlUrl": meta.get("html_url", ""),
                "cloneUrl": meta.get("clone_url", ""),
                "CloneUrl": meta.get("clone_url", ""),
                "description": meta.get("description") or "",
                "ownerId": (meta.get("owner") or {}).get("id", 0),
                "ownerLogin": (meta.get("owner") or {}).get("login", owner),
                "language": meta.get("language") or "",
                "createdDate": meta.get("created_at"),
                "updatedDate": meta.get("updated_at"),
                "hasIssues": bool(meta.get("has_issues", True)),
                "scopeConfigId": scope_config_id,
            }
        )
    if skipped:
        print(f"  skipped {len(skipped)} missing repos: {', '.join(skipped)}")

    if not to_create:
        print("  no valid scopes to write")
        return []

    print(f"  upserting {len(to_create)} scopes via PUT")
    # DevLake's PUT only persists connectionId/githubId/name/fullName. The
    # rest (cloneUrl, HTMLUrl, ownerId, language, dates) has to be PATCHed
    # on each scope after creation.
    client.put(
        f"/plugins/github/connections/{conn_id}/scopes",
        json={"data": [{
            "id": s["id"],
            "name": s["name"],
            "connectionId": s["connectionId"],
            "fullName": s["fullName"],
            "owner": s["owner"],
            "repo": s["repo"],
            "githubId": s["githubId"],
        } for s in to_create]},
    )

    print(f"  patching {len(to_create)} scopes with metadata + scopeConfigId")
    for s in to_create:
        patch_body = {
            "cloneUrl": s.get("cloneUrl", ""),
            "HTMLUrl": s.get("HTMLUrl", ""),
            "description": s.get("description", ""),
            "ownerId": s.get("ownerId", 0),
            "language": s.get("language", ""),
            "createdDate": s.get("createdDate"),
            "updatedDate": s.get("updatedDate"),
            "scopeConfigId": s["scopeConfigId"],
        }
        client.patch(
            f"/plugins/github/connections/{conn_id}/scopes/{s['githubId']}",
            json=patch_body,
        )
    return [{"githubId": s["githubId"], "name": s["name"]} for s in to_create]


def upsert_blueprint(
    client: DevLakeClient,
    conn_id: int,
    scope_refs: list[dict[str, Any]],
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

    # DevLake's blueprint references scopes by the plugin's primary key,
    # which for GitHub is the numeric repo ID (as a string).
    scopes = [
        {"scopeId": str(s["githubId"]), "scopeName": s["name"]}
        for s in scope_refs
    ]
    if not scopes:
        raise RuntimeError(
            "No valid scopes to attach to the blueprint. "
            "Check GITHUB_REPOS in devlake-config/env."
        )
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
    repos_csv = os.getenv("GITHUB_REPOS", "").strip()
    repos: list[str]
    if repos_csv in {"", "*"}:
        print(f"==> GITHUB_REPOS unset — auto-discovering repos under {owner}")
        discovered = list_all_github_repos(token, owner)
        repos = [name for name, _ in discovered]
        print(f"   found {len(repos)} repos: {', '.join(repos)}")
    else:
        repos = [r.strip() for r in repos_csv.split(",") if r.strip()]
    if not repos:
        print("error: no repos to configure", file=sys.stderr)
        return 1

    client = DevLakeClient.from_env()
    client.wait_ready()

    print(f"==> GitHub connection '{CONNECTION_NAME}'")
    conn = upsert_connection(client, token)
    conn_id = conn["id"]

    print(f"==> Scope config")
    scope_config_id = upsert_scope_config(client, conn_id)

    print(f"==> Scopes ({len(repos)} repos under {owner})")
    scope_refs = upsert_scopes(client, conn_id, owner, repos, token, scope_config_id)

    print("==> Blueprint")
    bp = upsert_blueprint(client, conn_id, scope_refs)
    print(f"   blueprint id={bp.get('id')} ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
