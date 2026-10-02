"""
API Routers Package
"""
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.uploads import router as uploads_router
from app.api.records import router as records_router
from app.api.reconcile import router as reconcile_router
from app.api.rate_cards import router as rate_cards_router
from app.api.fee_audit import router as fee_audit_router
from app.api.exceptions import router as exceptions_router
from app.api.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(uploads_router)
api_router.include_router(records_router)
api_router.include_router(reconcile_router)
api_router.include_router(rate_cards_router)
api_router.include_router(fee_audit_router)
api_router.include_router(exceptions_router)
api_router.include_router(analytics_router)

__all__ = ["api_router"]
