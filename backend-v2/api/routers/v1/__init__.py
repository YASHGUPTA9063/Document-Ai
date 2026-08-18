from fastapi import APIRouter

from .documents import router as documents_router
from .claims import router as claims_router
from .workflow import router as workflow_router
from .settings import router as settings_router

api_v1_router = APIRouter(prefix="/api/v1")

# We mount without prefix here so they retain their own prefixes (/documents, /claims, etc.)
# If we want all endpoints under /api/v1, we mount them to api_v1_router
api_v1_router.include_router(documents_router)
api_v1_router.include_router(claims_router)
api_v1_router.include_router(workflow_router)
api_v1_router.include_router(settings_router)
