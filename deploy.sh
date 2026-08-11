#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# deploy.sh — Build and launch Document-AI on the Azure VM
#
# Usage (on the VM):
#   chmod +x deploy.sh
#   ./deploy.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

PUBLIC_IP="172.200.163.232"

echo "═══════════════════════════════════════════════════════════════"
echo "  Document-AI — Azure VM Deployment"
echo "  Public IP: $PUBLIC_IP"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# 1. Build and start containers
echo "▶ Building and starting containers..."
docker compose up --build -d

echo ""
echo "▶ Waiting for services to become healthy..."
# `docker compose ps --format json` is compose v2 only — on v1 it just prints
# usage text and the loop spins without ever checking anything. Inspect the
# container's health status directly instead, which works on both.
timeout=300
elapsed=0
health="unknown"
while [ $elapsed -lt $timeout ]; do
  cid=$(docker compose ps -q backend)
  health=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "unknown")
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
  echo "   ⚠️  backend did not report healthy in ${timeout}s — check: docker compose logs backend"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo ""
echo "  Frontend:     http://${PUBLIC_IP}:5173"
echo "  Backend API:  http://${PUBLIC_IP}:8000"
echo "  API Docs:     http://${PUBLIC_IP}:8000/docs"
echo ""
echo "  Logs:  docker compose logs -f"
echo "  Stop:  docker compose down"
echo "═══════════════════════════════════════════════════════════════"
