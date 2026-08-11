#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# deploy.sh — Build and launch Document-AI on the Azure VM
#
# Usage (on the VM):
#   chmod +x deploy.sh
#   ./deploy.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

PUBLIC_IP="40.67.146.28"

echo "═══════════════════════════════════════════════════════════════"
echo "  Document-AI — Azure VM Deployment"
echo "  Public IP: $PUBLIC_IP"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# 0. Docker daemon access. A fresh VM user isn't in the `docker` group yet, so
# talking to /var/run/docker.sock fails with "permission denied". Fall back to
# sudo for this run and tell the user how to make it stick.
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo -n docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
    echo "⚠️  No permission on the Docker socket — using sudo for this run."
    echo "   Fix it permanently with:  sudo usermod -aG docker \$USER && newgrp docker"
    echo ""
  else
    echo "❌ Cannot reach the Docker daemon."
    echo "   Is it running?   sudo systemctl start docker"
    echo "   Permissions?     sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
  fi
fi

# 1. Build and start containers
echo "▶ Building and starting containers..."
$DOCKER compose up --build -d

echo ""
echo "▶ Waiting for services to become healthy..."
# `docker compose ps --format json` is compose v2 only — on v1 it just prints
# usage text and the loop spins without ever checking anything. Inspect the
# container's health status directly instead, which works on both.
timeout=300
elapsed=0
health="unknown"
while [ $elapsed -lt $timeout ]; do
  cid=$($DOCKER compose ps -q backend)
  health=$($DOCKER inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "unknown")
  # `[ ... ] && break` would return non-zero on a miss and `set -e` would kill
  # the script mid-wait — keep this as a plain if.
  if [ "$health" = "healthy" ]; then
    break
  fi
  sleep 5
  elapsed=$((elapsed + 5))
  echo "   ⏳ backend: ${health} (${elapsed}s / ${timeout}s)"
done

if [ "$health" = "healthy" ]; then
  echo "   ✅ backend is healthy"
else
  echo "   ⚠️  backend did not report healthy in ${timeout}s — check: $DOCKER compose logs backend"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo ""
echo "  Frontend:     http://${PUBLIC_IP}:5173"
echo "  Backend API:  http://${PUBLIC_IP}:8000"
echo "  API Docs:     http://${PUBLIC_IP}:8000/docs"
echo ""
echo "  Logs:  $DOCKER compose logs -f"
echo "  Stop:  $DOCKER compose down"
echo "═══════════════════════════════════════════════════════════════"
