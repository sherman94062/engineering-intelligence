#!/usr/bin/env python3
"""Trigger a one-shot pipeline run for the github-blueprint and wait for it."""

from __future__ import annotations

import sys
import time

from _devlake_api import DevLakeClient

BLUEPRINT_NAME = "github-blueprint"
POLL_SECONDS = 10
TIMEOUT_SECONDS = 60 * 60  # 1h ceiling — real ingest can be long on first run


def main() -> int:
    client = DevLakeClient.from_env()
    client.wait_ready()

    blueprints = (client.get("/blueprints") or {}).get("blueprints", [])
    bp = next((b for b in blueprints if b.get("name") == BLUEPRINT_NAME), None)
    if not bp:
        print(
            f"error: blueprint '{BLUEPRINT_NAME}' not found — run configure-github.py first",
            file=sys.stderr,
        )
        return 1

    print(f"==> Triggering blueprint id={bp['id']} ({BLUEPRINT_NAME})")
    run = client.post(f"/blueprints/{bp['id']}/trigger")
    pipeline_id = run.get("id") or run.get("pipelineId")
    if not pipeline_id:
        print(f"error: no pipeline id in trigger response: {run}", file=sys.stderr)
        return 1

    print(f"   pipeline id={pipeline_id} — polling every {POLL_SECONDS}s...")
    start = time.time()
    while True:
        pipeline = client.get(f"/pipelines/{pipeline_id}")
        status = pipeline.get("status", "UNKNOWN")
        print(f"   [{int(time.time() - start)}s] status={status}")
        if status in {"TASK_COMPLETED", "TASK_SUCCESS", "SUCCESS"}:
            print("==> Pipeline finished successfully.")
            return 0
        if status in {"TASK_FAILED", "TASK_CANCELLED", "FAILED", "CANCELLED"}:
            print(f"error: pipeline ended with status={status}", file=sys.stderr)
            return 2
        if time.time() - start > TIMEOUT_SECONDS:
            print("error: pipeline timed out", file=sys.stderr)
            return 3
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
