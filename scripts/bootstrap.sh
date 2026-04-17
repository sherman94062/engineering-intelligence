#!/usr/bin/env bash
# bootstrap.sh — idempotent first-run setup for devlake-mcp.
# Brings up the stack, waits for DevLake, configures GitHub, and triggers ingest.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/devlake-config/env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "error: ${ENV_FILE} not found. Copy devlake-config/env.example and fill it in." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

echo "==> Bringing up docker compose stack..."
docker compose --env-file "${ENV_FILE}" -f "${REPO_ROOT}/docker-compose.yml" up -d

echo "==> Waiting for DevLake REST API at http://localhost:8080/ping ..."
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8080/ping >/dev/null 2>&1; then
    echo "   DevLake is up."
    break
  fi
  sleep 2
done

if ! curl -fsS http://localhost:8080/ping >/dev/null 2>&1; then
  echo "error: DevLake did not become ready. Check: docker compose logs devlake" >&2
  exit 1
fi

echo "==> Configuring GitHub connection + blueprint..."
python "${REPO_ROOT}/scripts/configure-github.py"

echo "==> Triggering first pipeline run..."
python "${REPO_ROOT}/scripts/trigger-pipeline.py"

cat <<EOF

Bootstrap complete.

Next:
  - Grafana:         http://localhost:3002  (${GF_SECURITY_ADMIN_USER} / ${GF_SECURITY_ADMIN_PASSWORD})
  - DevLake config:  http://localhost:4000  (${DEVLAKE_ADMIN_USER} / ${DEVLAKE_ADMIN_PASS})
  - DevLake API:     http://localhost:8080

Once the ingest pipeline completes, seed the synthetic team layer:
  python scripts/seed-synthetic-team.py

Then start the MCP server (if not using the containerized one):
  cd mcp && uv pip install -e . && uv run server.py
EOF
