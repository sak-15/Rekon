"""
API Routers Package
"""
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.uploads import router as uploads_router
from app.api.records import router as records_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(uploads_router)
api_router.include_router(records_router)

__all__ = ["api_router"]

