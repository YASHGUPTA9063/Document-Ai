#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# deploy-azure.sh — one file to deploy Document-AI on a fresh Azure VM
#
# Installs Docker if it is missing, builds the images and starts the
# whole stack: postgres, redis, api, dispatcher, workflow-worker and the
# nginx frontend. Safe to re-run — it rebuilds and restarts in place and
# keeps the data volumes and the Postgres password from the first run.
#
# Usage (on the VM, from the repo root):
#   chmod +x deploy-azure.sh
#   ./deploy-azure.sh                  # install Docker, build, start
#   ./deploy-azure.sh --expose-api     # also publish :8000 (Swagger /docs)
#   ./deploy-azure.sh --ip 1.2.3.4     # different public IP for the URLs
#   ./deploy-azure.sh status           # containers + health
#   ./deploy-azure.sh logs [service]   # follow logs (api, workflow-worker…)
#   ./deploy-azure.sh restart          # restart without rebuilding
#   ./deploy-azure.sh stop             # stop everything, keep the data
#
# Before the first run, backend-v2/.env must hold the real secrets:
# MISTRAL_API_KEY, MISTRAL_WORKFLOW_ID and the Studio agent IDs.
#
# The app is served on port 80 only: nginx serves the UI and proxies
# /api/ to the backend, so the NSG needs just 22 (SSH) and 80 (HTTP).
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

PUBLIC_IP="172.171.242.207"
EXPOSE_API=0
ACTION="up"
LOG_ARGS=()

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()  { printf "${GREEN}▶ %s${NC}\n" "$*"; }
ok()    { printf "   ✅ %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠️  %s${NC}\n" "$*"; }
err()   { printf "${RED}❌ %s${NC}\n" "$*" >&2; }
banner(){ printf "${CYAN}%s${NC}\n" "$*"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        up|status|logs|restart|stop) ACTION="$1"; shift
            if [ "$ACTION" = "logs" ]; then LOG_ARGS=("$@"); break; fi ;;
        --ip)          PUBLIC_IP="$2"; shift 2 ;;
        --expose-api)  EXPOSE_API=1; shift ;;
        -h|--help)     sed -n '2,25p' "$0"; exit 0 ;;
        *) err "Unknown option: $1 (see --help)"; exit 1 ;;
    esac
done

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_ENV="$DIR/.env"
BACKEND_ENV="$DIR/backend-v2/.env"
PROJECT="document-ai"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

# ── Docker ───────────────────────────────────────────────────────────
APT_UPDATED=0
apt_install() {
    if [ "$APT_UPDATED" = "0" ]; then
        $SUDO apt-get update -qq
        APT_UPDATED=1
    fi
    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
}

install_docker() {
    if ! command -v curl >/dev/null 2>&1; then apt_install curl ca-certificates; fi

    # Ubuntu's own packaging (docker.io 29.x on 24.04) is what Azure's Ubuntu
    # images get from `apt install docker.io`. Its compose and buildx plugins
    # are separate packages with Ubuntu names — docker-compose-v2 and
    # docker-buildx — and Docker's upstream docker-ce packages conflict with
    # it, so never run get.docker.com on top of an existing docker.io.
    local ubuntu_pkgs=1
    if command -v docker >/dev/null 2>&1; then
        dpkg -s docker.io >/dev/null 2>&1 || ubuntu_pkgs=0
    else
        info "Installing Docker (docker.io, docker-compose-v2, docker-buildx)..."
        apt_install docker.io docker-compose-v2 docker-buildx
        ok "Docker installed."
    fi

    $SUDO systemctl enable --now docker >/dev/null 2>&1 || true

    # `docker compose build` refuses to run without buildx on recent compose.
    if ! $SUDO docker compose version >/dev/null 2>&1; then
        info "Installing the docker compose plugin..."
        if [ "$ubuntu_pkgs" = "1" ]; then apt_install docker-compose-v2; else apt_install docker-compose-plugin; fi
    fi
    if ! $SUDO docker buildx version >/dev/null 2>&1; then
        info "Installing the docker buildx plugin..."
        if [ "$ubuntu_pkgs" = "1" ]; then apt_install docker-buildx; else apt_install docker-buildx-plugin; fi
    fi
    ok "$($SUDO docker --version | cut -d, -f1); compose $($SUDO docker compose version --short)"

    # Takes effect on the next login; this run falls back to sudo below.
    if [ -n "$SUDO" ] && ! id -nG "$USER" | grep -qw docker; then
        $SUDO usermod -aG docker "$USER" || true
    fi
}

resolve_docker() {
    if docker info >/dev/null 2>&1; then
        DOCKER="docker"
    elif $SUDO docker info >/dev/null 2>&1; then
        DOCKER="$SUDO docker"
    else
        err "Cannot reach the Docker daemon — try: sudo systemctl start docker"
        exit 1
    fi
    COMPOSE="$DOCKER compose --project-directory $DIR -f $DIR/docker-compose.yml -p $PROJECT"
}

# ── Host preparation ─────────────────────────────────────────────────
ensure_swap() {
    # torch + DINOv2 loads in the api (per uvicorn worker) and the
    # workflow worker. On an 8 GB-or-smaller VM a swapfile keeps the OOM
    # killer away during the first build and model load.
    local mem_kb
    mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    if [ "$mem_kb" -lt 8200000 ] && [ -z "$(swapon --show --noheadings 2>/dev/null)" ]; then
        info "RAM is $((mem_kb / 1024 / 1024)) GB and there is no swap — adding a 4 GB swapfile..."
        $SUDO fallocate -l 4G /swapfile 2>/dev/null || $SUDO dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none
        $SUDO chmod 600 /swapfile
        $SUDO mkswap /swapfile >/dev/null
        $SUDO swapon /swapfile
        grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
        ok "Swap enabled."
    fi

    local free_gb
    free_gb=$(df -Pk / | awk 'NR==2 {print int($4 / 1024 / 1024)}')
    if [ "$free_gb" -lt 15 ]; then
        warn "Only ${free_gb} GB free on / — the images need ~10 GB. Grow the OS disk if the build fails."
    fi
}

open_host_firewall() {
    # Ubuntu's ufw is off on Azure images (the NSG is the firewall), but
    # if someone enabled it, keep SSH and HTTP reachable.
    if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -q "Status: active"; then
        info "ufw is active — allowing 22/tcp and 80/tcp..."
        $SUDO ufw allow 22/tcp >/dev/null
        $SUDO ufw allow 80/tcp >/dev/null
        if [ "$EXPOSE_API" = "1" ]; then $SUDO ufw allow 8000/tcp >/dev/null; fi
    fi
}

# ── Configuration ────────────────────────────────────────────────────
env_value() {  # env_value <file> <KEY> — last assignment, quotes stripped
    grep -E "^$2=" "$1" 2>/dev/null | tail -1 | cut -d= -f2- | sed -E 's/^["'\'']//; s/["'\'']$//; s/[[:space:]]+$//' || true
}

check_backend_env() {
    info "Checking backend-v2/.env..."
    if [ ! -f "$BACKEND_ENV" ]; then
        err "backend-v2/.env is missing."
        echo "   cp backend-v2/.env.example backend-v2/.env  and fill in the Mistral key and agent IDs."
        exit 1
    fi

    # Copied over from Windows? CRLF would end up inside every value.
    sed -i 's/\r$//' "$BACKEND_ENV"

    local missing=() key value
    for key in MISTRAL_API_KEY CLASSIFIER_AGENT_ID VALIDATOR_AGENT_ID REVIEWER_AGENT_ID \
               SIGNATURE_VISION_AGENT_ID SIGNATURE_JUDGE_AGENT_ID; do
        value=$(env_value "$BACKEND_ENV" "$key")
        if [ -z "$value" ] || [[ "$value" == *xxxxxxxx* ]] || [ "$value" = "your_mistral_api_key_here" ]; then
            missing+=("$key")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        err "Required values are unset in backend-v2/.env: ${missing[*]}"
        exit 1
    fi

    if [ -z "$(env_value "$BACKEND_ENV" MISTRAL_WORKFLOW_ID)" ]; then
        warn "MISTRAL_WORKFLOW_ID is empty — the stack will start but no upload can be processed."
    fi
    ok "Mistral key and required agent IDs present."
}

write_compose_env() {
    # Compose reads ./.env for ${VAR} substitution in docker-compose.yml.
    # The backend's own settings stay in backend-v2/.env.
    local pg_pass api_workers api_bind
    pg_pass=$(env_value "$ROOT_ENV" POSTGRES_PASSWORD)
    api_workers=$(env_value "$ROOT_ENV" API_WORKERS)

    if [ -z "$pg_pass" ]; then
        if $DOCKER volume inspect "${PROJECT}_postgres_data" >/dev/null 2>&1; then
            # Postgres only reads POSTGRES_PASSWORD when it initialises an
            # empty volume; an existing one keeps the compose default.
            pg_pass="password"
            warn "Existing Postgres volume found — keeping its original password."
        else
            pg_pass=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
        fi
    fi

    if [ "$EXPOSE_API" = "1" ]; then api_bind="0.0.0.0:8000"; else api_bind="127.0.0.1:8000"; fi

    umask 077
    cat > "$ROOT_ENV" <<EOF
# Written by deploy-azure.sh — host-specific, do not commit.
PUBLIC_IP=$PUBLIC_IP
FRONTEND_PORT=80
API_BIND=$api_bind
API_WORKERS=${api_workers:-2}
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$pg_pass
POSTGRES_DB=document_ai
VITE_API_BASE_URL=/api/v1
EOF
    umask 022
    ok "Wrote .env (frontend :80, api bound to $api_bind)."
}

# ── Health ───────────────────────────────────────────────────────────
wait_for_api() {
    info "Waiting for the API (first boot runs migrations and downloads DINOv2)..."
    local timeout=600 elapsed=0 cid state health=""
    while [ $elapsed -lt $timeout ]; do
        cid=$($COMPOSE ps -q api 2>/dev/null || true)
        if [ -n "$cid" ]; then
            state=$($DOCKER inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo unknown)
            health=$($DOCKER inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" 2>/dev/null || true)
            if [ "$health" = "healthy" ]; then ok "API is healthy."; return 0; fi
            if [ "$state" = "restarting" ] || [ "$state" = "exited" ]; then
                err "The api container is $state. Last log lines:"
                $COMPOSE logs --tail=40 api || true
                exit 1
            fi
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        printf "   ⏳ api: %s (%ds / %ds)\n" "${health:-starting}" "$elapsed" "$timeout"
    done
    err "API not healthy after ${timeout}s — check: ./deploy-azure.sh logs api"
    exit 1
}

smoke_test() {
    info "Smoke tests..."
    if curl -fsS -o /dev/null http://127.0.0.1:8000/health; then ok "GET :8000/health"; else warn "GET :8000/health failed"; fi
    if curl -fsS -o /dev/null http://127.0.0.1/; then ok "GET :80/ (frontend)"; else warn "GET :80/ failed"; fi
    if curl -fsS -o /dev/null http://127.0.0.1/api/v1/settings/features; then
        ok "GET :80/api/v1/settings/features (nginx → api)"
    else
        warn "nginx → api proxy check failed"
    fi

    local ready
    ready=$(curl -s http://127.0.0.1:8000/ready || true)
    if [[ "$ready" == *'"status":"ready"'* ]]; then
        ok "GET /ready — deployment is ready"
    else
        warn "GET /ready reports not ready: ${ready:0:300}"
    fi
}

print_summary() {
    local ip
    ip=$(env_value "$ROOT_ENV" PUBLIC_IP); ip=${ip:-$PUBLIC_IP}
    echo ""
    banner "═══════════════════════════════════════════════════════════════"
    banner "  Document-AI is running"
    echo ""
    printf "  App:          ${CYAN}http://%s${NC}\n" "$ip"
    printf "  API (proxy):  ${CYAN}http://%s/api/v1${NC}\n" "$ip"
    if [ "$(env_value "$ROOT_ENV" API_BIND)" = "0.0.0.0:8000" ]; then
        printf "  Swagger:      ${CYAN}http://%s:8000/docs${NC}\n" "$ip"
    else
        printf "  Swagger:      ssh -L 8000:127.0.0.1:8000 <user>@%s  →  http://localhost:8000/docs\n" "$ip"
    fi
    echo ""
    printf "  Azure NSG inbound: ${BOLD}22/tcp${NC} (your IP only), ${BOLD}80/tcp${NC} (Internet)\n"
    echo ""
    printf "  Status:   ${BOLD}./deploy-azure.sh status${NC}\n"
    printf "  Logs:     ${BOLD}./deploy-azure.sh logs workflow-worker${NC}\n"
    printf "  Stop:     ${BOLD}./deploy-azure.sh stop${NC}\n"
    printf "  Scale:    ${BOLD}$COMPOSE up -d --scale workflow-worker=2${NC}\n"
    banner "═══════════════════════════════════════════════════════════════"
}

# ── Actions ──────────────────────────────────────────────────────────
case "$ACTION" in
    up)
        echo ""
        banner "═══════════════════════════════════════════════════════════════"
        banner "  Document-AI — Azure VM deployment ($PUBLIC_IP)"
        banner "═══════════════════════════════════════════════════════════════"
        install_docker
        resolve_docker
        ensure_swap
        open_host_firewall
        check_backend_env
        write_compose_env

        info "Building images and starting containers (first build takes 5–15 min)..."
        $COMPOSE up -d --build --remove-orphans

        wait_for_api
        smoke_test
        echo ""
        $COMPOSE ps
        print_summary
        ;;
    status)
        resolve_docker
        $COMPOSE ps
        curl -s http://127.0.0.1:8000/ready && echo "" || warn "API not answering on 127.0.0.1:8000"
        ;;
    logs)
        resolve_docker
        $COMPOSE logs -f --tail=200 "${LOG_ARGS[@]}"
        ;;
    restart)
        resolve_docker
        $COMPOSE restart
        wait_for_api
        ;;
    stop)
        resolve_docker
        # No -v: postgres_data, redis_data and app_storage survive.
        $COMPOSE down
        ok "Stopped. Data volumes kept; ./deploy-azure.sh brings it back."
        ;;
esac
