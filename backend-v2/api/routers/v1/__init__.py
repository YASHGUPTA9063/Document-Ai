"""
API v1 router aggregation
=========================
Sub-routers declare their canonical, resource-prefixed paths
(`/documents/upload`, `/documents/{id}/status`, `/batches/{id}/checklist`, …).
`main.py` mounts them under `/api/v1`.

Three of those paths were flat in an earlier build — `/upload`,
`/upload/batch`, `/status/{id}` — and a deployed frontend may still call them.
Rather than re-declaring those handlers (the upload endpoint alone takes five
query parameters, and a drifting copy is exactly the bug this migration exists
to remove), the legacy router re-registers *the same endpoint callables* under
their old paths. One implementation, two addresses.

Turn the aliases off with ENABLE_LEGACY_ROOT_ROUTES=false once no such
frontend is deployed.
"""

from fastapi import APIRouter
from fastapi.routing import APIRoute

from .documents import router as documents_router
from .claims import router as claims_router
from .workflow import router as workflow_router
from .settings import router as settings_router

# Order matters: literal paths must be registered before any pattern that
# could swallow them.
ROUTERS = [
    documents_router,
    claims_router,
    workflow_router,
    settings_router,
]

# old flat path  ->  canonical path it now lives at
LEGACY_PATH_ALIASES: dict[str, str] = {
    "/upload": "/documents/upload",
    "/upload/batch": "/documents/upload/batch",
    "/status/{document_id}": "/documents/{document_id}/status",
}


def build_v1_router() -> APIRouter:
    """The canonical surface: every handler under /api/v1."""
    v1 = APIRouter(prefix="/api/v1")
    for router in ROUTERS:
        v1.include_router(router)
    return v1


def _find_route(path: str) -> APIRoute | None:
    for router in ROUTERS:
        for route in router.routes:
            if isinstance(route, APIRoute) and route.path == path:
                return route
    return None


def build_root_router() -> APIRouter:
    """
    The legacy surface, served at the root.

    Everything already at a resource-prefixed path is re-exposed unchanged;
    the three renamed paths additionally get their old spelling back, bound to
    the identical endpoint function.
    """
    root = APIRouter()
    for router in ROUTERS:
        root.include_router(router)

    for legacy_path, canonical_path in LEGACY_PATH_ALIASES.items():
        route = _find_route(canonical_path)
        if route is None:
            # A canonical path was renamed without updating this table. Loud,
            # because the silent version is a 404 only the old frontend sees.
            raise RuntimeError(
                f"Legacy alias {legacy_path} points at {canonical_path}, "
                f"which no router declares."
            )
        root.add_api_route(
            legacy_path,
            route.endpoint,
            methods=list(route.methods),
            response_model=route.response_model,
            tags=route.tags,
            summary=route.summary,
            description=route.description,
            include_in_schema=False,  # keep /docs showing one surface
        )

    return root


__all__ = ["ROUTERS", "LEGACY_PATH_ALIASES", "build_root_router", "build_v1_router"]
