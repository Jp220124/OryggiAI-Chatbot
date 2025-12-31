"""
Database Onboarding API
Endpoints for automatic database onboarding
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger
import asyncio

from app.services.auto_onboarding import OnboardingOrchestrator

router = APIRouter(prefix="/onboarding", tags=["Database Onboarding"])

# Store for tracking onboarding progress
onboarding_progress: dict = {}


class DatabaseConnectionRequest(BaseModel):
    """Request model for database connection"""
    connection_string: str = Field(
        ...,
        description="SQLAlchemy connection string",
        example="mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server"
    )
    tenant_id: Optional[str] = Field(
        None,
        description="Optional tenant ID (auto-generated if not provided)"
    )
    tenant_name: Optional[str] = Field(
        None,
        description="Optional tenant/organization name"
    )
    db_schema: str = Field(
        default="dbo",
        description="Database schema name"
    )
    fewshot_count: int = Field(
        default=50,
        description="Number of few-shot examples to generate",
        ge=10,
        le=200
    )
    include_views: bool = Field(
        default=True,
        description="Include database views in analysis"
    )


class TestConnectionRequest(BaseModel):
    """Request model for testing connection"""
    connection_string: str = Field(
        ...,
        description="SQLAlchemy connection string"
    )


class OnboardingResponse(BaseModel):
    """Response model for onboarding operations"""
    success: bool
    tenant_id: str
    message: str
    details: Optional[dict] = None


class OnboardingStatusResponse(BaseModel):
    """Response model for onboarding status"""
    tenant_id: str
    status: str
    progress: int
    current_step: str
    details: Optional[dict] = None


@router.post("/test-connection", response_model=OnboardingResponse)
async def test_database_connection(request: TestConnectionRequest):
    """
    Test database connection before full onboarding

    This endpoint verifies that the connection string is valid
    and the database is accessible.
    """
    try:
        orchestrator = OnboardingOrchestrator()
        result = await orchestrator.test_connection(request.connection_string)

        if result["success"]:
            return OnboardingResponse(
                success=True,
                tenant_id="",
                message=f"Connection successful! Found {result['tables_found']} tables.",
                details=result
            )
        else:
            return OnboardingResponse(
                success=False,
                tenant_id="",
                message=f"Connection failed: {result['message']}",
                details=result
            )

    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start", response_model=OnboardingResponse)
async def start_onboarding(
    request: DatabaseConnectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Start automatic database onboarding

    This initiates the fully automatic onboarding process:
    1. Extract database schema
    2. AI analyzes and understands the database
    3. Generate relevant Q&A examples
    4. Create embeddings for RAG

    The process runs in the background. Use /status/{tenant_id} to check progress.
    """
    import uuid

    tenant_id = request.tenant_id or str(uuid.uuid4())[:8]

    # Initialize progress tracking
    onboarding_progress[tenant_id] = {
        "status": "starting",
        "progress": 0,
        "current_step": "Initializing...",
        "details": None
    }

    # Define progress callback
    async def progress_callback(step: str, progress: int):
        onboarding_progress[tenant_id] = {
            "status": "in_progress" if progress >= 0 else "error",
            "progress": max(progress, 0),
            "current_step": step,
            "details": None
        }

    # Start onboarding in background
    async def run_onboarding():
        try:
            orchestrator = OnboardingOrchestrator()
            result = await orchestrator.onboard_database(
                connection_string=request.connection_string,
                tenant_id=tenant_id,
                tenant_name=request.tenant_name,
                db_schema=request.db_schema,
                fewshot_count=request.fewshot_count,
                include_views=request.include_views,
                progress_callback=progress_callback
            )

            onboarding_progress[tenant_id] = {
                "status": "completed" if result["success"] else "failed",
                "progress": 100 if result["success"] else 0,
                "current_step": "Completed" if result["success"] else "Failed",
                "details": result
            }

        except Exception as e:
            logger.error(f"Onboarding failed: {e}")
            onboarding_progress[tenant_id] = {
                "status": "failed",
                "progress": 0,
                "current_step": f"Error: {str(e)}",
                "details": {"error": str(e)}
            }

    # Run in background
    background_tasks.add_task(asyncio.create_task, run_onboarding())

    return OnboardingResponse(
        success=True,
        tenant_id=tenant_id,
        message="Onboarding started. Check /status/{tenant_id} for progress.",
        details={"tenant_id": tenant_id}
    )


@router.post("/start-sync", response_model=OnboardingResponse)
async def start_onboarding_sync(request: DatabaseConnectionRequest):
    """
    Start automatic database onboarding (synchronous)

    This runs the full onboarding process and waits for completion.
    Use this for smaller databases or when you need immediate results.

    For larger databases, use /start which runs in the background.
    """
    import uuid

    tenant_id = request.tenant_id or str(uuid.uuid4())[:8]

    try:
        orchestrator = OnboardingOrchestrator()

        # Run onboarding synchronously
        result = await orchestrator.onboard_database(
            connection_string=request.connection_string,
            tenant_id=tenant_id,
            tenant_name=request.tenant_name,
            db_schema=request.db_schema,
            fewshot_count=request.fewshot_count,
            include_views=request.include_views
        )

        if result["success"]:
            return OnboardingResponse(
                success=True,
                tenant_id=tenant_id,
                message=f"Onboarding complete! Organization: {result['organization_type']}",
                details=result
            )
        else:
            return OnboardingResponse(
                success=False,
                tenant_id=tenant_id,
                message=f"Onboarding failed: {', '.join(result['errors'])}",
                details=result
            )

    except Exception as e:
        logger.error(f"Onboarding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{tenant_id}", response_model=OnboardingStatusResponse)
async def get_onboarding_status(tenant_id: str):
    """
    Get onboarding progress for a tenant

    Returns current status, progress percentage, and current step.
    """
    if tenant_id not in onboarding_progress:
        # Check if tenant already exists in embeddings
        orchestrator = OnboardingOrchestrator()
        status = orchestrator.get_tenant_status(tenant_id)

        if status["initialized"]:
            return OnboardingStatusResponse(
                tenant_id=tenant_id,
                status="completed",
                progress=100,
                current_step="Already onboarded",
                details=status
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No onboarding found for tenant: {tenant_id}"
            )

    progress = onboarding_progress[tenant_id]
    return OnboardingStatusResponse(
        tenant_id=tenant_id,
        status=progress["status"],
        progress=progress["progress"],
        current_step=progress["current_step"],
        details=progress["details"]
    )


@router.get("/tenant/{tenant_id}", response_model=OnboardingResponse)
async def get_tenant_info(tenant_id: str):
    """
    Get tenant information and readiness status
    """
    try:
        orchestrator = OnboardingOrchestrator()
        status = orchestrator.get_tenant_status(tenant_id)

        if status["initialized"]:
            return OnboardingResponse(
                success=True,
                tenant_id=tenant_id,
                message="Tenant is ready to chat" if status["ready_to_chat"] else "Tenant partially initialized",
                details=status
            )
        else:
            return OnboardingResponse(
                success=False,
                tenant_id=tenant_id,
                message="Tenant not found or not initialized",
                details=status
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tenant/{tenant_id}", response_model=OnboardingResponse)
async def delete_tenant(tenant_id: str):
    """
    Delete all data for a tenant

    This removes all embeddings and configurations for the tenant.
    """
    try:
        orchestrator = OnboardingOrchestrator()
        orchestrator.delete_tenant(tenant_id)

        # Remove from progress tracking
        if tenant_id in onboarding_progress:
            del onboarding_progress[tenant_id]

        return OnboardingResponse(
            success=True,
            tenant_id=tenant_id,
            message=f"Tenant {tenant_id} deleted successfully",
            details=None
        )

    except Exception as e:
        logger.error(f"Failed to delete tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboard-current-db", response_model=OnboardingResponse)
async def onboard_current_database(
    tenant_id: Optional[str] = "default",
    tenant_name: Optional[str] = "OryggiDB",
    fewshot_count: int = 50
):
    """
    Onboard the currently configured database (from .env settings)

    This is a convenience endpoint to onboard the database specified
    in the application's environment variables.
    """
    from app.config import settings

    try:
        orchestrator = OnboardingOrchestrator()

        result = await orchestrator.onboard_database(
            connection_string=settings.database_url,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            db_schema="dbo",
            fewshot_count=fewshot_count,
            include_views=True
        )

        if result["success"]:
            return OnboardingResponse(
                success=True,
                tenant_id=tenant_id,
                message=f"Current database onboarded! Organization: {result['organization_type']}",
                details=result
            )
        else:
            return OnboardingResponse(
                success=False,
                tenant_id=tenant_id,
                message=f"Onboarding failed: {', '.join(result['errors'])}",
                details=result
            )

    except Exception as e:
        logger.error(f"Onboarding current DB failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
