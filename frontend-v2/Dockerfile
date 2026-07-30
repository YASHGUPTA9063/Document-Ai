
# ─────────────────────────────────────────────────────────────────────────
# Build stage — installs deps and produces a static Vite build.
# ─────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Copy lockfile first so this layer only invalidates when deps actually change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes VITE_* vars into the JS bundle at build time — must be supplied
# as a build arg, not a runtime env var. Relative by default: nginx proxies
# /api to the backend (see nginx.conf), so the bundle carries no hostname and
# works from any IP or DNS name the VM is reached on. Override with an
# absolute URL only when the backend is served from a different origin.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ─────────────────────────────────────────────────────────────────────────
# Runtime stage — serves the static build with nginx.
# ─────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
