from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant SaaS Payment & Settlement Reconciliation Engine API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.api import api_router

# Set up CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root():
    """
    Root entry point of the Rekon API.
    """
    return {
        "message": "Welcome to Rekon API",
        "description": "SaaS Payment & Settlement Reconciliation Engine",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify backend operational readiness.
    Used by Docker, orchestrators, and monitoring services.
    """
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
    }


# Mount API V1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

