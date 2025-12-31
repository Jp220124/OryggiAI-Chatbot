"""
Query Logs API Endpoints

Provides REST API for viewing query history and analytics.
Useful for auditing, debugging, and usage tracking.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, CurrentUser
from app.database.platform_connection import get_platform_db
from app.services.query_logging_service import get_query_logging_service
from app.models.platform import TenantDatabase


router = APIRouter(prefix="/query-logs", tags=["Query Logs"])


@router.get("/history")
async def get_query_history(
    limit: int = Query(50, ge=1, le=500, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    database_id: Optional[str] = Query(None, description="Filter by database ID"),
    status: Optional[str] = Query(None, description="Filter by status: success, error, timeout"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Get query history for the current tenant.

    Returns a paginated list of all queries executed through the platform,
    including the original questions asked and the SQL queries generated.

    Query Parameters:
    - limit: Max records to return (default 50, max 500)
    - offset: Pagination offset
    - database_id: Filter by specific database
    - status: Filter by status (success/error/timeout)
    - start_date: Filter by start date (ISO format)
    - end_date: Filter by end date (ISO format)
    """
    try:
        service = get_query_logging_service()

        # Parse dates if provided
        parsed_start_date = None
        parsed_end_date = None
        if start_date:
            try:
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format.")
        if end_date:
            try:
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format.")

        # Get query history
        history = await service.get_tenant_query_history(
            tenant_id=current_user.tenant_id,
            limit=limit,
            offset=offset,
            database_id=UUID(database_id) if database_id else None,
            status=status,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )

        return {
            "success": True,
            **history
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get query history: {str(e)}")


@router.get("/analytics")
async def get_query_analytics(
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Get query analytics for the current tenant.

    Returns aggregated statistics about query usage including:
    - Total queries
    - Success/error counts
    - Average execution time
    - Token usage

    Query Parameters:
    - start_date: Filter by start date (ISO format)
    - end_date: Filter by end date (ISO format)
    """
    try:
        service = get_query_logging_service()

        # Parse dates if provided
        parsed_start_date = None
        parsed_end_date = None
        if start_date:
            try:
                parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format.")
        if end_date:
            try:
                parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format.")

        # Get analytics
        analytics = await service.get_tenant_analytics(
            tenant_id=current_user.tenant_id,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
        )

        return {
            "success": True,
            **analytics
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


@router.get("/databases/{database_id}/history")
async def get_database_query_history(
    database_id: str,
    limit: int = Query(50, ge=1, le=500, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Get query history for a specific database.

    Convenience endpoint for filtering by database.
    """
    try:
        # Verify database belongs to tenant
        tenant_db = db.query(TenantDatabase).filter(
            TenantDatabase.id == UUID(database_id),
            TenantDatabase.tenant_id == current_user.tenant_id,
        ).first()

        if not tenant_db:
            raise HTTPException(status_code=404, detail="Database not found")

        service = get_query_logging_service()

        history = await service.get_tenant_query_history(
            tenant_id=current_user.tenant_id,
            database_id=UUID(database_id),
            limit=limit,
            offset=offset,
        )

        return {
            "success": True,
            "database_id": database_id,
            "database_name": tenant_db.name,
            **history
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get query history: {str(e)}")


@router.get("/recent")
async def get_recent_queries(
    limit: int = Query(10, ge=1, le=50, description="Number of recent queries to return"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Get the most recent queries for the current tenant.

    Quick endpoint for dashboard display showing latest activity.
    """
    try:
        service = get_query_logging_service()

        history = await service.get_tenant_query_history(
            tenant_id=current_user.tenant_id,
            limit=limit,
            offset=0,
        )

        return {
            "success": True,
            "queries": history.get("queries", []),
            "count": len(history.get("queries", [])),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent queries: {str(e)}")
