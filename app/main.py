"""
Advance Chatbot - Main Application
FastAPI Entry Point for Agentic AI Chatbot
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from contextlib import asynccontextmanager
from loguru import logger
import sys
import os

from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_database, close_database
from app.rag import chroma_manager, few_shot_manager
from app.api import chat_router, actions_router, auth_router, tenant_router
from app.api.reports import router as reports_router
from app.api.onboarding import router as onboarding_router
from app.api.usage import router as usage_router
from app.api.gateway import router as gateway_router
from app.api.query_logs import router as query_logs_router
from app.api.admin import router as admin_router

# Fix for Playwright on Windows - use SelectorEventLoop instead of ProactorEventLoop
import asyncio
import platform
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure Loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level
)

# Add file logging
os.makedirs(settings.log_dir, exist_ok=True)
logger.add(
    f"{settings.log_dir}/{settings.log_file}",
    rotation=settings.log_rotation,
    retention=settings.log_retention,
    level=settings.log_level
)

# Add audit logging
if settings.enable_audit_log:
    logger.add(
        f"{settings.log_dir}/{settings.audit_log_file}",
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        level="INFO",
        filter=lambda record: "AUDIT" in record["extra"]
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan Manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("=" * 80)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 80)

    try:
        # Initialize database connection
        logger.info("Initializing database connection...")
        init_database()

        # Initialize platform database for multi-tenant authentication
        logger.info("Initializing platform database...")
        from app.database.platform_connection import platform_db
        platform_db.initialize()

        # Initialize RAG system (ChromaDB)
        logger.info("Initializing ChromaDB vector store...")
        chroma_manager.initialize()

        # Optional: Auto-index schema on startup if empty
        stats = chroma_manager.get_collection_stats()
        if stats["count"] == 0:
            logger.info("No schema embeddings found, indexing database schema...")
            # Use the new Google re-indexer if provider is google
            if settings.embedding_provider == "google":
                from reindex_schemas_google import reindex_schemas_google
                result = reindex_schemas_google()
                embeddings_count = result["total_embeddings"] if result else 0
            else:
                from app.rag import index_database_schema
                embeddings_count = index_database_schema()
            logger.info(f"Created {embeddings_count} schema embeddings")
        else:
            logger.info(f"Found {stats['count']} existing schema embeddings")

        # Initialize Few-Shot Manager
        logger.info("Initializing Few-Shot Example Manager...")
        few_shot_manager.initialize()
        few_shot_stats = few_shot_manager.get_stats()
        logger.info(f"Loaded {few_shot_stats['total_examples']} few-shot examples")

        # Register Report Generators
        logger.info("Registering report generators...")
        from app.reports.registry import register_all_generators
        register_all_generators()

        # TODO: Initialize LangGraph agent (Phase 2)

        logger.info("All services initialized successfully")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("=" * 80)
    logger.info("Shutting down application...")
    try:
        close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

    logger.info("=" * 80)


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Agentic AI Chatbot with RAG, Report Generation, and Action Execution",
    lifespan=lifespan
)

# CORS Middleware - Include dashboard origins for Master Dashboard integration
dashboard_origins = [
    "https://103.197.77.163:8443",
    "https://103.197.77.163",
    "http://103.197.77.163:8080",
    "http://103.197.77.163:3000",
    "http://localhost:3000",
]
all_origins = list(set(settings.cors_origins + dashboard_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Frontend
app.mount("/ui", StaticFiles(directory="frontend", html=True), name="frontend")
# Also mount tenant pages directly at /tenant for cleaner URLs
app.mount("/tenant", StaticFiles(directory="frontend/tenant", html=True), name="tenant")
# Mount admin dashboard for Master Dashboard integration
app.mount("/admin", StaticFiles(directory="frontend/admin", html=True), name="admin")


# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors
    """
    import traceback
    error_detail = str(exc)
    error_traceback = traceback.format_exc()
    logger.error(f"Unhandled exception: {error_detail}\n{error_traceback}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": error_detail,  # Always show error for debugging
            "traceback": error_traceback if settings.debug else None
        }
    )


# Health Check Endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns application status
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment
    }


# Root Endpoint - Redirect to Tenant Login
@app.get("/")
async def root():
    """
    Root endpoint - redirects to tenant login page
    """
    return RedirectResponse(url="/tenant/login.html", status_code=302)


# API Info Endpoint (for developers)
@app.get("/api")
async def api_info():
    """
    API information endpoint for developers
    """
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "description": "Agentic AI Chatbot with RAG, Report Generation, and Action Execution",
        "docs": "/docs",
        "health": "/health",
        "tenant_portal": "/tenant/login.html"
    }


# Register API routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(tenant_router, prefix="/api/tenant", tags=["Tenant Management"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])
app.include_router(actions_router, prefix="/api/actions", tags=["Actions"])
app.include_router(onboarding_router, prefix="/api", tags=["Database Onboarding"])
app.include_router(usage_router, prefix="/api/usage", tags=["Usage Statistics"])
app.include_router(gateway_router, prefix="/api", tags=["Gateway"])
app.include_router(query_logs_router, prefix="/api", tags=["Query Logs"])
app.include_router(admin_router, prefix="/api", tags=["Admin Dashboard"])


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.host}:{settings.port}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
