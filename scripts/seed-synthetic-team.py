#!/usr/bin/env python3
"""Seed a synthetic 12-engineer team into DevLake's MySQL schema.

Real GitHub activity (ingested by DevLake) gives us authentic commit and
deployment signal. This seeder layers team-dynamics signal on top: PR reviews,
incidents, contributor variance, and AI-adoption spread. Every synthetic row
is tagged with source = 'synthetic' so real and simulated data are always
distinguishable.

Run after the first real GitHub pipeline completes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import random
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / "devlake-config" / "env"
PROFILES_FILE = REPO_ROOT / "synthetic" / "team-profiles.yml"
INCIDENTS_FILE = REPO_ROOT / "synthetic" / "incident-scenarios.yml"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

SYNTHETIC_TAG = "synthetic"

# Tables we tag with a 'source' column and write to.
TARGET_TABLES = [
    "accounts",
    "commits",
    "repos",
    "repo_commits",
    "pull_requests",
    "pull_request_commits",
    "pull_request_comments",
    "cicd_pipelines",
    "cicd_pipeline_commits",
    "issues",
    "board_issues",
]


# ----------------------------------------------------------------------
# Schema helpers
# ----------------------------------------------------------------------

def ensure_source_column(engine: Engine, dry_run: bool) -> None:
    """Add a nullable `source` column to each target table if missing.

    Non-destructive: existing rows keep source = NULL (real data). Only rows
    we insert set source = 'synthetic'.
    """
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT LOWER(table_name) AS tbl
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND column_name = 'source'
                """
            )
        ).all()
        existing = {r.tbl for r in rows}

        for table in TARGET_TABLES:
            if table in existing:
                continue
            stmt = f"ALTER TABLE `{table}` ADD COLUMN `source` VARCHAR(32) NULL"
            if dry_run:
                print(f"[dry-run] {stmt}")
                continue
            try:
                conn.execute(text(stmt))
                print(f"  added `source` column to {table}")
            except Exception as exc:  # table may not exist yet (pipeline not run)
                print(f"  skip {table}: {exc}")


def purge_synthetic(engine: Engine, dry_run: bool) -> None:
    """Delete every row tagged source='synthetic' across target tables."""
    with engine.begin() as conn:
        for table in TARGET_TABLES:
            stmt = f"DELETE FROM `{table}` WHERE `source` = :src"
            if dry_run:
                print(f"[dry-run] DELETE FROM {table} WHERE source='synthetic'")
                continue
            try:
                result = conn.execute(text(stmt), {"src": SYNTHETIC_TAG})
                print(f"  purged {result.rowcount} rows from {table}")
            except Exception as exc:
                print(f"  skip {table}: {exc}")


# ----------------------------------------------------------------------
# Data types
# ----------------------------------------------------------------------

@dataclass
class Persona:
    key: str
    label: str
    count: int
    commits_per_week: dict
    lines_per_commit: dict
    commit_burst_probability: float
    pr_iterations: dict
    pr_review_comments: dict
    post_merge_churn_rate: float
    incident_creation_probability: float
    review_activity_rate: float
    cycle_time_hours: dict
    ai_signal_label: str


@dataclass
class Engineer:
    id: str
    user_name: str
    full_name: str
    email: str
    persona: Persona


@dataclass
class Repo:
    id: str
    name: str
    owner: str


@dataclass
class Commit:
    sha: str
    repo: Repo
    author: Engineer
    authored_date: dt.datetime
    additions: int
    deletions: int
    message: str


@dataclass
class PullRequest:
    id: str
    repo: Repo
    author: Engineer
    title: str
    created_date: dt.datetime
    merged_date: dt.datetime
    closed_date: dt.datetime
    merge_commit_sha: str
    pr_key: int
    commits: list[Commit] = field(default_factory=list)
    reviewers: list[Engineer] = field(default_factory=list)
    review_comments: int = 0


# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------

FIRST_NAMES = [
    "Ada", "Blake", "Cass", "Devi", "Ely", "Finn", "Gwen", "Hana",
    "Ivo", "Juno", "Kai", "Lior", "Mira", "Nash", "Oren", "Priya",
    "Quinn", "Remy", "Shae", "Tova",
]
LAST_NAMES = [
    "Albrecht", "Barba", "Chen", "Demir", "Eskew", "Flores",
    "Gupta", "Harada", "Ibarra", "Kwon", "Lin", "Mensah",
    "Novak", "Okoye", "Patel", "Rhee", "Sato", "Tagaq",
]


def gauss_positive_int(rng: random.Random, spec: dict, floor: int = 1) -> int:
    mean = float(spec["mean"])
    stddev = float(spec.get("stddev", max(1.0, mean * 0.2)))
    return max(floor, int(round(rng.gauss(mean, stddev))))


def gauss_positive_float(rng: random.Random, spec: dict, floor: float = 0.1) -> float:
    mean = float(spec["mean"])
    stddev = float(spec.get("stddev", max(0.1, mean * 0.2)))
    return max(floor, rng.gauss(mean, stddev))


def make_engineers(rng: random.Random, personas: list[Persona]) -> list[Engineer]:
    used_handles: set[str] = set()
    engineers: list[Engineer] = []
    for persona in personas:
        for _ in range(persona.count):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            base_handle = f"{first.lower()}.{last.lower()}"
            handle = base_handle
            suffix = 2
            while handle in used_handles:
                handle = f"{base_handle}{suffix}"
                suffix += 1
            used_handles.add(handle)
            engineer_id = f"synthetic:github:{handle}"
            engineers.append(
                Engineer(
                    id=engineer_id,
                    user_name=handle,
                    full_name=f"{first} {last}",
                    email=f"{handle}@synthetic.example.com",
                    persona=persona,
                )
            )
    return engineers


def load_real_repos(engine: Engine) -> list[Repo]:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, name
                FROM repos
                WHERE (source IS NULL OR source != :src)
                """
            ),
            {"src": SYNTHETIC_TAG},
        ).all()
    repos = []
    for row in rows:
        name = row.name or ""
        owner = os.getenv("GITHUB_ORG_OR_USER", "sherman94062")
        if "/" in name:
            owner, short = name.split("/", 1)
            repos.append(Repo(id=row.id, name=short, owner=owner))
        else:
            repos.append(Repo(id=row.id, name=name or str(row.id), owner=owner))
    return repos


def sha_from(*parts: Any) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()


def generate_commits(
    rng: random.Random,
    engineers: list[Engineer],
    repos: list[Repo],
    lookback_days: int,
) -> list[Commit]:
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=lookback_days)
    commits: list[Commit] = []

    weeks = max(1, lookback_days // 7)
    for eng in engineers:
        persona = eng.persona
        total_commits = 0
        for _ in range(weeks):
            total_commits += gauss_positive_int(rng, persona.commits_per_week, floor=0)
        for _ in range(total_commits):
            repo = rng.choice(repos)
            offset_seconds = rng.uniform(0, lookback_days * 86400)
            when = start + dt.timedelta(seconds=offset_seconds)
            additions = gauss_positive_int(rng, persona.lines_per_commit, floor=1)
            deletions = max(0, int(additions * rng.uniform(0.05, 0.4)))
            # Occasional burst: tight cluster of follow-up commits
            msg = _synth_commit_message(rng, persona)
            commits.append(
                Commit(
                    sha=sha_from(eng.id, repo.id, when.isoformat(), additions),
                    repo=repo,
                    author=eng,
                    authored_date=when,
                    additions=additions,
                    deletions=deletions,
                    message=msg,
                )
            )
            if rng.random() < persona.commit_burst_probability:
                for k in range(rng.randint(1, 3)):
                    burst_when = when + dt.timedelta(minutes=rng.randint(1, 14))
                    add2 = gauss_positive_int(rng, persona.lines_per_commit, floor=1)
                    commits.append(
                        Commit(
                            sha=sha_from(eng.id, repo.id, burst_when.isoformat(), add2, k),
                            repo=repo,
                            author=eng,
                            authored_date=burst_when,
                            additions=add2,
                            deletions=max(0, int(add2 * rng.uniform(0.05, 0.3))),
                            message=_synth_commit_message(rng, persona, follow_up=True),
                        )
                    )
    commits.sort(key=lambda c: c.authored_date)
    return commits


def _synth_commit_message(rng: random.Random, persona: Persona, follow_up: bool = False) -> str:
    verbs = ["refactor", "tune", "wire up", "add", "cleanup", "fix", "harden", "simplify"]
    subjects = [
        "ingest path", "retry logic", "pagination", "rate limiter",
        "schema migration", "cache key", "dashboard query", "metric definition",
        "error handling", "auth middleware", "tool invocation",
    ]
    verb = rng.choice(verbs)
    subject = rng.choice(subjects)
    prefix = "wip: " if follow_up else ""
    tail = " [ai]" if persona.ai_signal_label == "high" and rng.random() < 0.5 else ""
    return f"{prefix}{verb} {subject}{tail}"


def group_commits_into_prs(
    rng: random.Random,
    commits: list[Commit],
    engineers: list[Engineer],
) -> list[PullRequest]:
    by_author_repo: dict[tuple[str, str], list[Commit]] = {}
    for c in commits:
        by_author_repo.setdefault((c.author.id, c.repo.id), []).append(c)

    prs: list[PullRequest] = []
    for (author_id, repo_id), authored in by_author_repo.items():
        authored.sort(key=lambda c: c.authored_date)
        author = authored[0].author
        repo = authored[0].repo
        persona = author.persona

        # Group every 3-7 consecutive commits into a PR
        i = 0
        while i < len(authored):
            size = rng.randint(3, 7)
            slice_ = authored[i:i + size]
            i += size
            if not slice_:
                continue
            first_commit = slice_[0]
            last_commit = slice_[-1]
            cycle_hours = gauss_positive_float(rng, persona.cycle_time_hours, floor=0.5)
            created = first_commit.authored_date
            merged = last_commit.authored_date + dt.timedelta(hours=cycle_hours)
            pr_id = f"synthetic:github:{repo.id}:pr:{sha_from(author_id, repo_id, created.isoformat())[:10]}"
            pr_key = int(sha_from(pr_id)[:8], 16) % 1_000_000

            # Pick reviewers based on each other's review_activity_rate
            reviewers = [
                e for e in engineers
                if e.id != author.id and rng.random() < e.persona.review_activity_rate * 0.35
            ]
            if not reviewers and engineers:
                reviewers = [rng.choice([e for e in engineers if e.id != author.id])]

            iterations = gauss_positive_int(rng, persona.pr_iterations, floor=1)
            review_comments = gauss_positive_int(rng, persona.pr_review_comments, floor=0)
            # More iterations -> more comments (architecture-code gap proxy)
            review_comments = int(review_comments * (1 + 0.25 * (iterations - 1)))

            pr = PullRequest(
                id=pr_id,
                repo=repo,
                author=author,
                title=first_commit.message.capitalize(),
                created_date=created,
                merged_date=merged,
                closed_date=merged,
                merge_commit_sha=last_commit.sha,
                pr_key=pr_key,
                commits=slice_,
                reviewers=reviewers,
                review_comments=review_comments,
            )
            prs.append(pr)
    return prs


# ----------------------------------------------------------------------
# Inserts
# ----------------------------------------------------------------------

def _bulk_insert(conn, table: str, rows: list[dict], columns: list[str]) -> int:
    if not rows:
        return 0
    col_list = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    stmt = text(
        f"INSERT IGNORE INTO `{table}` ({col_list}) VALUES ({placeholders})"
    )
    count = 0
    # Chunk to keep memory + statement size reasonable.
    chunk = 500
    for i in range(0, len(rows), chunk):
        result = conn.execute(stmt, rows[i:i + chunk])
        count += result.rowcount or 0
    return count


def insert_accounts(conn, engineers: list[Engineer]) -> int:
    rows = [
        {
            "id": e.id,
            "email": e.email,
            "full_name": e.full_name,
            "user_name": e.user_name,
            "organization": "sherman94062",
            "created_date": dt.datetime.now(dt.timezone.utc),
            "source": SYNTHETIC_TAG,
        }
        for e in engineers
    ]
    return _bulk_insert(
        conn,
        "accounts",
        rows,
        ["id", "email", "full_name", "user_name", "organization", "created_date", "source"],
    )


def insert_commits(conn, commits: list[Commit]) -> int:
    rows = []
    repo_rows = []
    for c in commits:
        rows.append(
            {
                "sha": c.sha,
                "additions": c.additions,
                "deletions": c.deletions,
                "dev_eq": c.additions + c.deletions,
                "message": c.message[:250],
                "author_id": c.author.id,
                "author_name": c.author.full_name,
                "author_email": c.author.email,
                "authored_date": c.authored_date,
                "committer_id": c.author.id,
                "committer_name": c.author.full_name,
                "committer_email": c.author.email,
                "committed_date": c.authored_date,
                "source": SYNTHETIC_TAG,
            }
        )
        repo_rows.append(
            {"repo_id": c.repo.id, "commit_sha": c.sha, "source": SYNTHETIC_TAG}
        )
    n_commits = _bulk_insert(
        conn,
        "commits",
        rows,
        [
            "sha", "additions", "deletions", "dev_eq", "message",
            "author_id", "author_name", "author_email", "authored_date",
            "committer_id", "committer_name", "committer_email", "committed_date",
            "source",
        ],
    )
    _bulk_insert(conn, "repo_commits", repo_rows, ["repo_id", "commit_sha", "source"])
    return n_commits


def insert_prs(conn, prs: list[PullRequest]) -> int:
    pr_rows = []
    pr_commit_rows = []
    pr_comment_rows = []
    for pr in prs:
        pr_rows.append(
            {
                "id": pr.id,
                "base_repo_id": pr.repo.id,
                "head_repo_id": pr.repo.id,
                "status": "MERGED",
                "original_status": "closed",
                "title": pr.title[:250],
                "description": f"Synthetic PR for {pr.repo.name}",
                "url": f"https://github.com/{pr.repo.owner}/{pr.repo.name}/pull/{pr.pr_key}",
                "author_name": pr.author.user_name,
                "author_id": pr.author.id,
                "pull_request_key": pr.pr_key,
                "created_date": pr.created_date,
                "merged_date": pr.merged_date,
                "closed_date": pr.closed_date,
                "merge_commit_sha": pr.merge_commit_sha,
                "head_ref": f"feature/synth-{pr.pr_key}",
                "base_ref": "main",
                "source": SYNTHETIC_TAG,
            }
        )
        for c in pr.commits:
            pr_commit_rows.append(
                {"pull_request_id": pr.id, "commit_sha": c.sha, "source": SYNTHETIC_TAG}
            )
        # Spread review comments across the PR's review window
        total_comments = pr.review_comments
        for idx in range(total_comments):
            reviewer = (
                pr.reviewers[idx % len(pr.reviewers)] if pr.reviewers else pr.author
            )
            when = pr.created_date + (pr.merged_date - pr.created_date) * (
                (idx + 1) / (total_comments + 1)
            )
            comment_id = f"{pr.id}:comment:{idx}"
            pr_comment_rows.append(
                {
                    "id": comment_id,
                    "pull_request_id": pr.id,
                    "body": _synth_review_comment(idx),
                    "account_id": reviewer.id,
                    "created_date": when,
                    "type": "DIFF" if idx % 3 else "GENERAL",
                    "source": SYNTHETIC_TAG,
                }
            )
    n = _bulk_insert(
        conn,
        "pull_requests",
        pr_rows,
        [
            "id", "base_repo_id", "head_repo_id", "status", "original_status",
            "title", "description", "url", "author_name", "author_id",
            "pull_request_key", "created_date", "merged_date", "closed_date",
            "merge_commit_sha", "head_ref", "base_ref", "source",
        ],
    )
    _bulk_insert(
        conn,
        "pull_request_commits",
        pr_commit_rows,
        ["pull_request_id", "commit_sha", "source"],
    )
    _bulk_insert(
        conn,
        "pull_request_comments",
        pr_comment_rows,
        [
            "id", "pull_request_id", "body", "account_id", "created_date",
            "type", "source",
        ],
    )
    return n


def _synth_review_comment(idx: int) -> str:
    pool = [
        "Can you pull this out into a helper? We use the same pattern above.",
        "Nit: rename for clarity.",
        "Does this need a test covering the failure path?",
        "What's the behaviour if the upstream returns 429? I don't see a retry here.",
        "LGTM once the lint warnings are addressed.",
        "This feels like it should live in the ingest module, not here.",
        "Worth adding a metric for this branch so we can see it in Grafana.",
        "Edge case: empty list — does the current code handle that?",
    ]
    return pool[idx % len(pool)]


def insert_pipelines_and_incidents(
    conn,
    rng: random.Random,
    prs: list[PullRequest],
    incident_cfg: dict,
) -> tuple[int, int]:
    pipeline_rows = []
    pipeline_commit_rows = []
    incident_rows = []
    archetypes = incident_cfg["archetypes"]
    weights = [a["weight"] for a in archetypes]
    deploy_incident_rate = float(incident_cfg.get("deploy_incident_rate", 0.08))

    for pr in prs:
        pipeline_id = f"synthetic:pipeline:{pr.id}"
        deploy_start = pr.merged_date + dt.timedelta(minutes=rng.randint(1, 25))
        duration = rng.randint(90, 900)
        deploy_finish = deploy_start + dt.timedelta(seconds=duration)

        # Decide whether this deploy triggers an incident.
        triggers_incident = rng.random() < deploy_incident_rate * (
            1.0 + 0.5 * pr.author.persona.incident_creation_probability * 10
        )
        result = "FAILURE" if triggers_incident and rng.random() < 0.4 else "SUCCESS"

        pipeline_rows.append(
            {
                "id": pipeline_id,
                "name": f"deploy {pr.repo.name}#{pr.pr_key}",
                "result": result,
                "status": "DONE",
                "type": "DEPLOYMENT",
                "duration_sec": duration,
                "environment": "production",
                "created_date": deploy_start,
                "finished_date": deploy_finish,
                "cicd_scope_id": pr.repo.id,
                "source": SYNTHETIC_TAG,
            }
        )
        pipeline_commit_rows.append(
            {
                "pipeline_id": pipeline_id,
                "commit_sha": pr.merge_commit_sha,
                "branch": "main",
                "repo_id": pr.repo.id,
                "repo_url": f"https://github.com/{pr.repo.owner}/{pr.repo.name}",
                "source": SYNTHETIC_TAG,
            }
        )

        if triggers_incident:
            arche = rng.choices(archetypes, weights=weights, k=1)[0]
            lag_min = rng.randint(
                int(arche["trigger"]["post_deploy_minutes"]["min"]),
                int(arche["trigger"]["post_deploy_minutes"]["max"]),
            )
            created = deploy_finish + dt.timedelta(minutes=lag_min)
            ttr_hours = max(
                0.25,
                rng.gauss(
                    arche["ttr_hours"]["mean"],
                    arche["ttr_hours"].get("stddev", arche["ttr_hours"]["mean"] * 0.3),
                ),
            )
            resolved = created + dt.timedelta(hours=ttr_hours)
            incident_id = f"synthetic:incident:{pipeline_id}"
            incident_rows.append(
                {
                    "id": incident_id,
                    "issue_key": f"INC-{pr.pr_key}",
                    "title": f"{arche['label']} after {pr.repo.name}#{pr.pr_key}",
                    "description": arche["description_template"].format(
                        repo=pr.repo.name,
                        sha=pr.merge_commit_sha[:7],
                        feature="ingest",
                        model=f"{pr.repo.name}_daily",
                    ),
                    "type": "INCIDENT",
                    "original_type": arche["key"],
                    "status": "DONE",
                    "original_status": "closed",
                    "priority": arche["severity"].upper(),
                    "severity": arche["severity"],
                    "created_date": created,
                    "updated_date": resolved,
                    "resolution_date": resolved,
                    "lead_time_minutes": int(ttr_hours * 60),
                    "source": SYNTHETIC_TAG,
                }
            )

    n_pipelines = _bulk_insert(
        conn,
        "cicd_pipelines",
        pipeline_rows,
        [
            "id", "name", "result", "status", "type", "duration_sec",
            "environment", "created_date", "finished_date", "cicd_scope_id",
            "source",
        ],
    )
    _bulk_insert(
        conn,
        "cicd_pipeline_commits",
        pipeline_commit_rows,
        ["pipeline_id", "commit_sha", "branch", "repo_id", "repo_url", "source"],
    )
    n_incidents = _bulk_insert(
        conn,
        "issues",
        incident_rows,
        [
            "id", "issue_key", "title", "description", "type", "original_type",
            "status", "original_status", "priority", "severity",
            "created_date", "updated_date", "resolution_date",
            "lead_time_minutes", "source",
        ],
    )
    return n_pipelines, n_incidents


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------

def load_personas(path: Path) -> tuple[int, list[Persona]]:
    cfg = yaml.safe_load(path.read_text())
    personas = [Persona(**p) for p in cfg["personas"]]
    return int(cfg.get("seed", 0)), personas


def load_incident_cfg(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def build_engine() -> Engine:
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("error: DB_URL not set", file=sys.stderr)
        sys.exit(1)
    return create_engine(db_url, pool_pre_ping=True, future=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engineers", type=int, default=None,
                   help="Override total engineer count (default: sum of persona counts)")
    p.add_argument("--lookback-days", type=int, default=180)
    p.add_argument("--ai-adoption-rate", type=float, default=None,
                   help="Override the fraction of engineers using AI-heavy personas")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reset", action="store_true",
                   help="Purge then re-seed in one step")
    p.add_argument("--purge", action="store_true",
                   help="Only purge synthetic records; do not reseed")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    engine = build_engine()

    seed, personas = load_personas(PROFILES_FILE)
    incident_cfg = load_incident_cfg(INCIDENTS_FILE)

    if args.ai_adoption_rate is not None:
        _rescale_personas_for_adoption(personas, args.ai_adoption_rate)
    if args.engineers is not None:
        _rescale_personas_for_total(personas, args.engineers)

    ensure_source_column(engine, args.dry_run)

    if args.purge or args.reset:
        print("==> Purging existing synthetic records")
        purge_synthetic(engine, args.dry_run)
        if args.purge:
            return 0

    rng = random.Random(seed)
    print("==> Loading real repos from DevLake")
    repos = load_real_repos(engine)
    if not repos:
        print(
            "error: no repos found — run the GitHub ingest pipeline first",
            file=sys.stderr,
        )
        return 1
    print(f"   {len(repos)} repos available")

    engineers = make_engineers(rng, personas)
    print(f"==> Generated {len(engineers)} synthetic engineers")

    commits = generate_commits(rng, engineers, repos, args.lookback_days)
    print(f"==> Generated {len(commits)} synthetic commits")

    prs = group_commits_into_prs(rng, commits, engineers)
    print(f"==> Grouped into {len(prs)} pull requests")

    if args.dry_run:
        print("[dry-run] skipping inserts")
        return 0

    with engine.begin() as conn:
        n_acc = insert_accounts(conn, engineers)
        n_commits = insert_commits(conn, commits)
        n_prs = insert_prs(conn, prs)
        n_pipe, n_inc = insert_pipelines_and_incidents(conn, rng, prs, incident_cfg)
    print(
        f"==> Wrote accounts={n_acc} commits={n_commits} prs={n_prs} "
        f"pipelines={n_pipe} incidents={n_inc}"
    )
    return 0


def _rescale_personas_for_total(personas: list[Persona], total: int) -> None:
    current = sum(p.count for p in personas)
    if current == total or current == 0:
        return
    ratio = total / current
    remaining = total
    for p in personas[:-1]:
        p.count = max(1, int(round(p.count * ratio)))
        remaining -= p.count
    personas[-1].count = max(1, remaining)


def _rescale_personas_for_adoption(personas: list[Persona], rate: float) -> None:
    # Rate is the share of engineers whose persona is labelled AI-heavy.
    rate = max(0.0, min(1.0, rate))
    ai_keys = {"ai_power_user", "ai_adopter"}
    total = sum(p.count for p in personas)
    ai_target = int(round(total * rate))
    non_ai_target = total - ai_target
    ai_personas = [p for p in personas if p.key in ai_keys]
    non_ai_personas = [p for p in personas if p.key not in ai_keys]
    _split(ai_personas, ai_target)
    _split(non_ai_personas, non_ai_target)


def _split(buckets: list[Persona], total: int) -> None:
    if not buckets:
        return
    current = sum(p.count for p in buckets)
    if current == 0:
        buckets[0].count = total
        return
    ratio = total / current
    remaining = total
    for p in buckets[:-1]:
        p.count = max(1, int(round(p.count * ratio)))
        remaining -= p.count
    buckets[-1].count = max(1, remaining)


if __name__ == "__main__":
    sys.exit(main())
