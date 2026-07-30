
# ─────────────────────────────────────────────────────────────────────────
# Builder stage — compiles/installs Python deps into an isolated prefix.
# Kept separate from the runtime image so build tools (gcc etc.) and pip's
# cache never end up in the final image.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Some networks block plain HTTP egress (port 80) but allow HTTPS — rewrite
# Debian's default mirror scheme so `apt-get update` doesn't depend on it.
RUN sed -i 's/URIs: http:/URIs: https:/' /etc/apt/sources.list.d/debian.sources

# Build-time headers for any dep without a prebuilt manylinux wheel
# (cryptography/lxml/scipy usually ship wheels, this is a cheap safety net).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch/torchvision default to the CUDA build off PyPI (multi-GB). This app
# only ever runs DINOv2 inference on CPU (see utils/signature_verifier.py),
# so pull the dedicated CPU wheels instead and let the rest resolve normally.
RUN grep -viE '^(torch|torchvision)==' requirements.txt > requirements.cpu.txt && \
    pip install --user --extra-index-url https://download.pytorch.org/whl/cpu \
        torch==2.12.1+cpu torchvision==0.27.1+cpu && \
    pip install --user -r requirements.cpu.txt

# ─────────────────────────────────────────────────────────────────────────
# Runtime stage
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    HF_HOME=/app/storage/.cache/huggingface \
    STORAGE_DIR=/app/storage

# Shared runtime libs needed by opencv-python-headless (libgl1/libglib2.0-0),
# torch/scipy/scikit-image OpenMP kernels (libgomp1), and curl for the
# healthcheck. No compilers, no dev headers.
RUN sed -i 's/URIs: http:/URIs: https:/' /etc/apt/sources.list.d/debian.sources
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

# /app/storage and /app/data are named-volume mountpoints. Docker seeds an empty
# volume with the ownership of the image directory it covers, so both must exist
# and be owned by appuser here — otherwise they mount root-owned and the non-root
# process can't write (SQLite fails with "unable to open database file").
RUN mkdir -p /app/storage/crops /app/storage/ocr_blocks /app/storage/.cache/huggingface /app/data \
    && chown -R appuser:appuser /app/storage /app/data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Single process only: startup preloads the DINOv2 model and spins up the
# Mistral workflow worker as an in-process asyncio task (see main.py's
# lifespan handler) — running >1 uvicorn worker would duplicate both.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
