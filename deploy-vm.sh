#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# deploy-vm.sh — Build and launch Document-AI on a Linux VM
#
# Works on Azure, AWS, GCP, or any Linux VM with Docker installed.
#
# Usage (on the VM):
#   chmod +x deploy-vm.sh
#   ./deploy-vm.sh              # auto-detects public IP
#   ./deploy-vm.sh --ip 1.2.3.4 # override public IP
#   ./deploy-vm.sh --with-queue  # also start Redis queue + arq worker
#   ./deploy-vm.sh --with-migrations  # run Alembic migrations
#   ./deploy-vm.sh --tail        # follow container logs after deploy
#
# Environment overrides (can also be set in a .env next to this script):
#   POSTGRES_USER       default: postgres
#   POSTGRES_PASSWORD   default: password
#   POSTGRES_DB         default: document_ai
#   API_WORKERS         default: 2
#   VITE_API_BASE_URL   default: /api/v1 (relative — nginx proxies)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colour helpers ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { printf "${GREEN}▶ %s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}⚠️  %s${NC}\n" "$*"; }
err()   { printf "${RED}❌ %s${NC}\n" "$*"; }
banner(){ printf "${CYAN}%s${NC}\n" "$*"; }

# ── Parse arguments ─────────────────────────────────────────────────
WITH_QUEUE=0
WITH_MIGRATIONS=0
TAIL_LOGS=0
PUBLIC_IP=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)           PUBLIC_IP="$2"; shift 2 ;;
        --with-queue)   WITH_QUEUE=1; shift ;;
        --with-migrations) WITH_MIGRATIONS=1; shift ;;
        --tail)         TAIL_LOGS=1; shift ;;
        -h|--help)
            echo "Usage: $0 [--ip <PUBLIC_IP>] [--with-queue] [--with-migrations] [--tail]"
            exit 0
            ;;
        *) err "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Auto-detect public IP if not provided ────────────────────────────
if [ -z "$PUBLIC_IP" ]; then
    info "Detecting public IP..."
    # Try multiple metadata / external services in order of preference

    # Azure IMDS
    PUBLIC_IP=$(curl -s -m 5 -H "Metadata:true" \
        "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" 2>/dev/null || true)

    if [ -z "$PUBLIC_IP" ]; then
        # AWS IMDSv2
        TOKEN=$(curl -s -m 2 -X PUT "http://169.254.169.254/latest/api/token" \
            -H "X-aws-ec2-metadata-token-ttl-seconds: 30" 2>/dev/null || true)
        if [ -n "$TOKEN" ]; then
            PUBLIC_IP=$(curl -s -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" \
                "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
        fi
    fi

    if [ -z "$PUBLIC_IP" ]; then
        # GCP
        PUBLIC_IP=$(curl -s -m 2 -H "Metadata-Flavor: Google" \
            "http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" 2>/dev/null || true)
    fi

    if [ -z "$PUBLIC_IP" ]; then
        # Generic fallback
        PUBLIC_IP=$(curl -s -m 5 https://ifconfig.me 2>/dev/null || curl -s -m 5 https://api.ipify.org 2>/dev/null || true)
    fi

    if [ -z "$PUBLIC_IP" ]; then
        warn "Could not auto-detect public IP. Using hostname."
        PUBLIC_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || hostname)
    fi
fi

# ── Banner ───────────────────────────────────────────────────────────
echo ""
banner "═══════════════════════════════════════════════════════════════"
banner "  Document-AI — VM Deployment"
banner "  Public IP: $PUBLIC_IP"
banner "═══════════════════════════════════════════════════════════════"
echo ""

# ── Step 0: Docker daemon access ────────────────────────────────────
DOCKER="docker"
COMPOSE="docker compose"

if ! docker info >/dev/null 2>&1; then
    if sudo -n docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
        DOCKER="sudo docker"
        COMPOSE="sudo docker compose"
        warn "No permission on the Docker socket — using sudo for this run."
        echo "   Fix permanently:  sudo usermod -aG docker \$USER && newgrp docker"
        echo ""
    else
        err "Cannot reach the Docker daemon."
        echo "   Is it running?   sudo systemctl start docker"
        echo "   Permissions?     sudo usermod -aG docker \$USER && newgrp docker"
        exit 1
    fi
fi

# Verify docker compose v2 is available
if ! $COMPOSE version >/dev/null 2>&1; then
    err "docker compose (v2) not found. Install it: https://docs.docker.com/compose/install/"
    exit 1
fi

# ── Step 1: Validate required files ─────────────────────────────────
info "Validating project files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for required_file in \
    "$SCRIPT_DIR/docker-compose.yml" \
    "$SCRIPT_DIR/backend-v2/Dockerfile" \
    "$SCRIPT_DIR/backend-v2/.env" \
    "$SCRIPT_DIR/frontend-v2/Dockerfile" \
    "$SCRIPT_DIR/frontend-v2/nginx.conf"; do
    if [ ! -f "$required_file" ]; then
        err "Missing required file: $required_file"
        exit 1
    fi
done
echo "   ✅ All required files present."

# ── Step 2: Build and start containers ──────────────────────────────
COMPOSE_PROFILES_ARG=""
if [ "$WITH_QUEUE" = "1" ]; then
    COMPOSE_PROFILES_ARG="--profile queue"
    info "Queue profile enabled — Redis and the arq worker will start too."
fi

info "Building and starting containers (this may take a few minutes on first run)..."
$COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" $COMPOSE_PROFILES_ARG up --build -d

# ── Step 3: Database migrations (opt-in) ────────────────────────────
if [ "$WITH_MIGRATIONS" = "1" ]; then
    echo ""
    info "Applying database migrations..."
    if $COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" exec -T api alembic upgrade head; then
        echo "   ✅ Migrations applied."
    else
        warn "alembic upgrade failed — the API's init_db() may have already created tables."
        echo "   Check logs: $DOCKER compose logs api"
    fi
fi

# ── Step 4: Wait for backend health ─────────────────────────────────
echo ""
info "Waiting for services to become healthy..."

timeout=300
elapsed=0
health="unknown"

while [ $elapsed -lt $timeout ]; do
    # Get the API container ID
    cid=$($COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" ps -q api 2>/dev/null || true)

    if [ -n "$cid" ]; then
        health=$($DOCKER inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "unknown")
        if [ "$health" = "healthy" ]; then
            break
        fi
    fi

    sleep 5
    elapsed=$((elapsed + 5))
    printf "   ⏳ api: ${health} (%ds / %ds)\n" "$elapsed" "$timeout"
done

if [ "$health" = "healthy" ]; then
    echo "   ✅ Backend API is healthy."
else
    warn "Backend did not report healthy in ${timeout}s."
    echo "   Check: $COMPOSE -f $SCRIPT_DIR/docker-compose.yml logs api"
fi

# ── Step 5: Verify ports are listening ───────────────────────────────
echo ""
info "Verifying exposed ports..."

check_port() {
    local port=$1 name=$2
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || \
       netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
        printf "   ✅ %-18s port %s\n" "$name" "$port"
    else
        printf "   ⚠️  %-18s port %s — not listening yet\n" "$name" "$port"
    fi
}

check_port 5173 "Frontend (nginx)"
check_port 8000 "Backend API"

# ── Step 6: Quick smoke test ─────────────────────────────────────────
echo ""
info "Running smoke tests..."

if curl -fsS "http://localhost:8000/health" >/dev/null 2>&1; then
    echo "   ✅ GET /health — 200 OK"
else
    warn "GET /health did not return 200 — backend may still be starting."
fi

if curl -fsS -o /dev/null "http://localhost:5173/" 2>/dev/null; then
    echo "   ✅ GET / (frontend) — 200 OK"
else
    warn "GET / (frontend) did not return 200."
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
banner "═══════════════════════════════════════════════════════════════"
banner "  ✅ Deployment complete!"
echo ""
printf "  Frontend:       ${CYAN}http://${PUBLIC_IP}:5173${NC}\n"
printf "  Backend API:    ${CYAN}http://${PUBLIC_IP}:8000${NC}\n"
printf "  API Docs:       ${CYAN}http://${PUBLIC_IP}:8000/docs${NC}\n"
printf "  Health:         ${CYAN}http://${PUBLIC_IP}:8000/health${NC}\n"
printf "  Versioned API:  ${CYAN}http://${PUBLIC_IP}:8000/api/v1${NC}\n"
echo ""
printf "  Logs:  ${BOLD}$COMPOSE logs -f${NC}\n"
printf "  Stop:  ${BOLD}$COMPOSE down${NC}\n"
banner "═══════════════════════════════════════════════════════════════"
echo ""

# ── Optional: tail logs ──────────────────────────────────────────────
if [ "$TAIL_LOGS" = "1" ]; then
    info "Tailing container logs (Ctrl+C to stop)..."
    $COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" logs -f
fi
