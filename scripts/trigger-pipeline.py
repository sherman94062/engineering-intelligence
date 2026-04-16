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
        finished = pipeline.get("finishedTasks") or 0
        total = pipeline.get("totalTasks") or 0
        print(
            f"   [{int(time.time() - start)}s] status={status} "
            f"tasks={finished}/{total}"
        )
        # Pipeline is terminal once every task has a result, regardless of
        # whether the aggregate status is _SUCCESS, _PARTIAL, or _FAILED.
        terminal = total > 0 and finished >= total
        if status in {"TASK_COMPLETED", "TASK_SUCCESS", "SUCCESS"} or (
            terminal and status == "TASK_PARTIAL"
        ):
            failed = _dump_failed_tasks(client, pipeline_id)
            if failed:
                print(
                    f"==> Pipeline finished with {failed} failed task(s). "
                    "Successful tasks still ingested their data.",
                    file=sys.stderr,
                )
                return 2
            print("==> Pipeline finished successfully.")
            return 0
        if status in {"TASK_FAILED", "TASK_CANCELLED", "FAILED", "CANCELLED"}:
            print(f"error: pipeline ended with status={status}", file=sys.stderr)
            _dump_failed_tasks(client, pipeline_id)
            return 2
        if time.time() - start > TIMEOUT_SECONDS:
            print("error: pipeline timed out", file=sys.stderr)
            return 3
        time.sleep(POLL_SECONDS)


def _dump_failed_tasks(client: DevLakeClient, pipeline_id: int) -> int:
    """Print every failed task's first few lines of message. Returns the
    count of failed tasks so the caller can adjust its exit code."""
    try:
        tasks = client.get(f"/pipelines/{pipeline_id}/tasks") or {}
    except Exception as exc:
        print(f"  (could not fetch task list: {exc})", file=sys.stderr)
        return 0
    if isinstance(tasks, dict):
        tasks = tasks.get("tasks") or tasks.get("data") or []
    failed = 0
    for t in tasks:
        if not isinstance(t, dict):
            continue
        status = t.get("status") or t.get("result")
        if status in {"TASK_FAILED", "FAILED"}:
            failed += 1
            plugin = t.get("plugin", "?")
            subtasks = t.get("subtaskName") or t.get("subtask_name") or ""
            msg = (t.get("message") or "").strip()
            print(
                f"  - task id={t.get('id')} plugin={plugin} "
                f"subtask={subtasks} status={status}",
                file=sys.stderr,
            )
            if msg:
                for line in msg.splitlines()[:6]:
                    print(f"    | {line}", file=sys.stderr)
    return failed


if __name__ == "__main__":
    sys.exit(main())
