# common_api/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

from common_api.routers import users, chats, messages, analysis, sync
from common_api.utils import verify_api_key
from common_api.config import settings

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Chat Analysis API",
    description="API for Telegram chat analysis with Odoo integration",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware - используем правильные имена полей
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # свойство, а не поле
    allow_credentials=settings.cors_allow_credentials,  # поле с подчеркиванием
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Health Check ==========
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/health/detailed", tags=["health"])
async def detailed_health_check(api_key: str = Depends(verify_api_key)):
    """Detailed health check with database status"""
    from src.database.session import check_database_connection

    db_status = await check_database_connection()

    return {
        "status": "healthy" if db_status else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "components": {
            "database": "connected" if db_status else "disconnected",
            "api": "running"
        }
    }


# ========== Exception Handlers ==========
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else None  # используем settings.debug
        }
    )


# ========== Include Routers ==========
app.include_router(users.router, prefix="/api/v1")
app.include_router(chats.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")


# ========== Root ==========
@app.get("/", tags=["root"])
async def root():
    return {
        "name": "Chat Analysis API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "common_api.main:app",  # исправлен путь
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )