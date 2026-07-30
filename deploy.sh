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
docker-compose up --build -d

echo ""
echo "▶ Waiting for services to become healthy..."
# Give the backend up to 90s to pass its healthcheck
timeout=90
elapsed=0
until docker-compose ps --format json | grep -q '"healthy"' || [ $elapsed -ge $timeout ]; do
  sleep 5
  elapsed=$((elapsed + 5))
  echo "   ⏳ Waiting... (${elapsed}s / ${timeout}s)"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo ""
echo "  Frontend:     http://${PUBLIC_IP}:5173"
echo "  Backend API:  http://${PUBLIC_IP}:8000"
echo "  API Docs:     http://${PUBLIC_IP}:8000/docs"
echo ""
echo "  Logs:  docker-compose logs -f"
echo "  Stop:  docker-compose down"
echo "═══════════════════════════════════════════════════════════════"
