"""
API v1 Router Aggregation
=========================
Each sub-router declares branch-vm3's original, unprefixed paths
(/upload, /status/{id}, /documents, /claims, /settings/..., /templates, ...).

main.py mounts them twice:
  * at the root — the contract the shipped frontend calls through nginx,
    which rewrites /api/(.*) → backend:8000/$1
  * under /api/v1 — the versioned surface adopted from `development`

Both mounts serve the same handlers, so there is one implementation and no
drift between the two surfaces.
"""

from fastapi import APIRouter

from .documents import router as documents_router
from .claims import router as claims_router
from .workflow import router as workflow_router
from .settings import router as settings_router

# Sub-routers in mount order. Order matters for path resolution: more specific
# literal paths must be registered before any catch-all patterns.
ROUTERS = [
    documents_router,
    claims_router,
    workflow_router,
    settings_router,
]


def build_root_router() -> APIRouter:
    """Router carrying branch-vm3's original paths, mounted at the root."""
    root = APIRouter()
    for r in ROUTERS:
        root.include_router(r)
    return root


def build_v1_router() -> APIRouter:
    """The same handlers, exposed under the versioned /api/v1 prefix."""
    v1 = APIRouter(prefix="/api/v1")
    for r in ROUTERS:
        v1.include_router(r)
    return v1


# Kept as a module-level attribute for parity with `development`'s import style.
api_v1_router = build_v1_router()

__all__ = ["ROUTERS", "build_root_router", "build_v1_router", "api_v1_router"]
