#!/usr/bin/env bash
# Runs every time the user attaches to the Codespace (not just first run).
# Ensures the docker stack is up (Codespaces can suspend it).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

ENV_FILE="devlake-config/env"
if [[ -f "${ENV_FILE}" ]]; then
  # Bring the stack back up if it was suspended
  docker compose --env-file "${ENV_FILE}" up -d >/dev/null 2>&1 || true
fi

echo ""
echo "Welcome back to engineering-intelligence."
echo "  - Dashboard:  http://localhost:3002/d/devlake-dora-overview/"
echo "  - Demo guide: docs/vpe-demo.md"
echo ""
