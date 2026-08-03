# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — builder: resolve and install all Python dependencies into a venv
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Toolchain for any dependency without a prebuilt wheel (grpcio, lxml, psycopg2).
# Debian mirrors are fetched over HTTPS — plain HTTP egress is blocked on some
# corporate networks, which makes `apt-get update` fail with "Connection failed".
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libpq-dev \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .

# Split into two installs on purpose.
#
# Step 1 takes everything except torch/torchvision from PyPI. requirements.txt
# already pins every library torch shares with the rest of the stack (numpy,
# pillow, filelock, fsspec, Jinja2, sympy, networkx, typing_extensions), so
# step 2 has nothing left to resolve — installing torch first instead made pip
# pull its own numpy/fsspec/filelock and then uninstall and replace them.
#
# --no-compile skips bytecode generation, which is the memory-hungry part of
# installing transformers/scipy/opencv and was crashing the builder.
RUN grep -vE '^\s*(torch|torchvision)\s*$|^\s*--extra-index-url' requirements.txt > /tmp/req-base.txt \
    && pip install --no-cache-dir --no-compile -r /tmp/req-base.txt

# Step 2: CPU-only torch. Plain PyPI wheels bundle ~2.5GB of CUDA libraries this
# image never uses. --no-deps is safe because step 1 satisfied all of them.
RUN pip install --no-cache-dir --no-compile --no-deps \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # transformers/huggingface cache must live somewhere the non-root user owns
    HF_HOME=/app/.cache/huggingface

# Shared libraries needed at runtime:
#   libglib2.0-0 -> opencv-python-headless
#   libgomp1     -> torch / scikit-image OpenMP runtime
#   libpq5       -> psycopg2
#   curl         -> container healthcheck
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Run as an unprivileged user
RUN useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser . .

# Directories the app writes to at runtime (compose may bind-mount over storage)
RUN mkdir -p /app/storage /app/.cache/huggingface \
    && chown -R appuser:appuser /app/storage /app/.cache

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Default: run the FastAPI app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
