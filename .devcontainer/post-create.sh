#!/usr/bin/env bash
# Runs once when the Codespace is first created.
# Prepares env, installs Python deps, brings up the stack, waits for it,
# and seeds demo data so the dashboard is populated when the user arrives.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> Writing devlake-config/env (demo-mode defaults)"
ENV_FILE="devlake-config/env"
if [[ ! -f "${ENV_FILE}" ]]; then
  # Derive values from env.example, fill sensible demo defaults. No GitHub PAT
  # required — the demo seeder skips the real pipeline entirely.
  ENCRYPTION_SECRET="$(openssl rand -hex 32)"
  cat > "${ENV_FILE}" <<EOF
DEVLAKE_ADMIN_USER=admin
DEVLAKE_ADMIN_PASS=admin
MYSQL_ROOT_PASSWORD=demopassroot
MYSQL_USER=devlake
MYSQL_PASSWORD=demopass
MYSQL_DATABASE=lake

# Demo mode — no real GitHub ingest, so these are unused but must be set
GITHUB_TOKEN=ghp_demo_mode_no_real_token_needed
GITHUB_ORG_OR_USER=demo-org
GITHUB_REPOS=

DB_URL=mysql+pymysql://devlake:demopass@localhost:3306/lake
MCP_PORT=8811
MCP_HOST=0.0.0.0

GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin

DEVLAKE_ENCRYPTION_SECRET=${ENCRYPTION_SECRET}
TZ=UTC
EOF
fi

echo "==> Installing Python deps"
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r scripts/requirements.txt

echo "==> Bringing up docker compose stack"
docker compose --env-file "${ENV_FILE}" up -d

echo "==> Waiting for MySQL to accept connections..."
for _ in $(seq 1 60); do
  if docker compose --env-file "${ENV_FILE}" exec -T mysql \
       mysqladmin ping -h localhost -pdemopassroot >/dev/null 2>&1; then
    echo "   MySQL ready."
    break
  fi
  sleep 2
done

echo "==> Waiting for DevLake to finish schema migrations..."
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8080/ping >/dev/null 2>&1; then
    echo "   DevLake ready."
    break
  fi
  sleep 2
done

# Give DevLake a few seconds to finish creating its domain tables before
# we try to ALTER them.
sleep 10

echo "==> Seeding demo data (no real GitHub pipeline needed)"
python scripts/seed-demo.py --lookback-days 180 || {
  echo "   (if this failed, DevLake may still be warming up — try:"
  echo "    source venv/bin/activate && python scripts/seed-demo.py)"
}

cat <<EOF

===========================================================================
Codespace ready.

  Grafana (DORA dashboard): forwarded port 3002 (admin / admin)
  DevLake config UI:        forwarded port 4000
  MCP server:               forwarded port 8811

Next:
  1. Click the Grafana port in the Ports tab to open the dashboard in your
     browser. Filter to "Synthetic data = true" — the demo data only lives
     in the synthetic layer.
  2. Follow docs/vpe-demo.md for the 15-minute walkthrough.
  3. Wire the MCP to Claude Desktop per docs/mcp-setup.md, OR use the
     Streamable HTTP endpoint directly from any MCP client.
===========================================================================
EOF
