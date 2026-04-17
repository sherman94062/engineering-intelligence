#!/usr/bin/env python3
"""Demo-mode seeder — stand up the full synthetic stack without a real
GitHub pipeline.

The normal flow is:
  1. Real GitHub ingest populates `repos`, `commits`, etc.
  2. `seed-synthetic-team.py` overlays a synthetic team.

For demos and Codespaces we want to skip step 1 — no GitHub PAT needed.
This script inserts a handful of realistic-looking "demo" repo rows
directly into DevLake's `repos` table, then invokes the normal synthetic
seeder so the 12-engineer team has a place to live.

Every row inserted here is tagged `source = 'synthetic'` so a later run
of `seed-synthetic-team.py --purge` cleans everything up.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / "devlake-config" / "env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

SYNTHETIC_TAG = "synthetic"

# Repos the demo pretends exist. Names loosely match what CLAUDE.md
# describes so the dashboard tells a consistent story.
DEMO_REPOS = [
    ("demo:GithubRepo:0:1", "demo-org/platform-api",    "Go",         "Core platform service"),
    ("demo:GithubRepo:0:2", "demo-org/web-frontend",    "TypeScript", "Customer-facing web app"),
    ("demo:GithubRepo:0:3", "demo-org/data-pipeline",   "Python",     "Nightly ETL + feature store"),
    ("demo:GithubRepo:0:4", "demo-org/mobile-ios",      "Swift",      "iOS app"),
]


def build_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("error: DB_URL not set in env", file=sys.stderr)
        sys.exit(1)
    return create_engine(db_url, pool_pre_ping=True, future=True)


def ensure_source_column(conn) -> None:
    """Mirror what seed-synthetic-team.py does, but only for `repos`."""
    existing = {
        r.tbl
        for r in conn.execute(
            text(
                """
                SELECT LOWER(table_name) AS tbl
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND column_name = 'source'
                """
            )
        ).all()
    }
    if "repos" not in existing:
        conn.execute(text("ALTER TABLE `repos` ADD COLUMN `source` VARCHAR(32) NULL"))
        print("  added `source` column to repos")


def insert_demo_repos(conn) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    rows = [
        {
            "id": repo_id,
            "name": name,
            "url": f"https://github.com/{name}",
            "description": desc,
            "language": lang,
            "forked_from": "",
            "created_date": now - dt.timedelta(days=365),
            "updated_date": now,
            "source": SYNTHETIC_TAG,
        }
        for repo_id, name, lang, desc in DEMO_REPOS
    ]
    stmt = text(
        """
        INSERT IGNORE INTO `repos`
          (id, name, url, description, language, forked_from,
           created_date, updated_date, source)
        VALUES
          (:id, :name, :url, :description, :language, :forked_from,
           :created_date, :updated_date, :source)
        """
    )
    result = conn.execute(stmt, rows)
    return result.rowcount or 0


def main() -> int:
    engine = build_engine()
    with engine.begin() as conn:
        ensure_source_column(conn)
        n = insert_demo_repos(conn)
        print(f"==> Inserted {n} demo repo rows")

    print("==> Invoking seed-synthetic-team.py to build the 12-engineer team")
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "seed-synthetic-team.py")]
    # Forward any extra CLI args — e.g. --lookback-days, --engineers
    cmd.extend(sys.argv[1:])
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print("error: seed-synthetic-team.py failed", file=sys.stderr)
        return result.returncode

    print()
    print("Demo data ready.")
    print("  Grafana: http://localhost:3002/d/devlake-dora-overview/  (admin/admin)")
    print("  Claude:  wire the MCP per docs/mcp-setup.md, then try docs/vpe-demo.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
