"""API v1 master router."""

from fastapi import APIRouter

from app.api.v1.images import router as images_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.posts import router as posts_router
from app.api.v1.suggestions import router as suggestions_router
from app.api.v1.costs import router as costs_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(images_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(posts_router)
api_v1_router.include_router(suggestions_router)
api_v1_router.include_router(costs_router)
