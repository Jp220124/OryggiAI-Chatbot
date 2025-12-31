"""
Admin API Router

Provides API endpoints for the Master Dashboard to access chatbot tenant data.
Includes tenant status, query statistics, and query history.

Security: Protected by admin API key authentication.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query, Depends
from pydantic import BaseModel

from app.config import settings
from app.services.admin_service import get_admin_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== API Key Authentication ====================

# Admin API key - should be configured in environment
ADMIN_API_KEY = getattr(settings, 'admin_api_key', 'oryggi-admin-secret-key-2025')


async def verify_admin_api_key(x_admin_api_key: str = Header(None, alias="X-Admin-API-Key")):
    """
    Verify the admin API key for authentication.
    """
    if not x_admin_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Admin-API-Key header"
        )

    if x_admin_api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key"
        )

    return True


# ==================== Response Models ====================

class TenantStatusResponse(BaseModel):
    """Response model for tenant status"""
    id: str
    name: str
    slug: str
    admin_email: str
    status: str
    plan: str
    created_at: Optional[str]
    is_online: bool
    agent_version: Optional[str]
    agent_hostname: Optional[str]
    connected_since: Optional[str]
    total_queries: int
    successful_queries: int
    failed_queries: int
    success_rate: float
    last_query_at: Optional[str]
    last_question: Optional[str]


class QueryLogResponse(BaseModel):
    """Response model for query log"""
    request_id: str
    question: Optional[str]
    sql_query: str
    status: str
    row_count: int
    execution_time_ms: Optional[int]
    generation_time_ms: Optional[int]
    tokens_used: Optional[int]
    llm_model: Optional[str]
    requested_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    conversation_id: Optional[str]


# ==================== API Endpoints ====================

@router.get("/admin/health")
async def admin_health_check():
    """
    Health check endpoint for admin API.
    """
    return {
        "status": "healthy",
        "service": "OryggiAI Chatbot Admin API",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/admin/tenants")
async def get_all_tenants(
    include_inactive: bool = Query(False, description="Include inactive/suspended tenants"),
    limit: int = Query(50, ge=1, le=200, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _: bool = Depends(verify_admin_api_key)
):
    """
    Get all chatbot tenants with their online/offline status.

    Returns:
    - Tenant list with connection status
    - Query statistics per tenant
    - Last activity information

    Headers Required:
    - X-Admin-API-Key: Admin authentication key
    """
    service = get_admin_service()
    result = service.get_all_tenants_with_status(
        include_inactive=include_inactive,
        limit=limit,
        offset=offset
    )

    if "error" in result:
        logger.error(f"[ADMIN_API] Error getting tenants: {result['error']}")

    return result


@router.get("/admin/tenants/{tenant_id}")
async def get_tenant_detail(
    tenant_id: str,
    _: bool = Depends(verify_admin_api_key)
):
    """
    Get detailed information about a specific tenant.

    Returns:
    - Tenant information
    - Database connections
    - Active gateway sessions
    - Session history
    - Query statistics
    - Recent queries with Q&A

    Headers Required:
    - X-Admin-API-Key: Admin authentication key
    """
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")

    service = get_admin_service()
    result = service.get_tenant_detail(tenant_uuid)

    if not result:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return result


@router.get("/admin/tenants/{tenant_id}/queries")
async def get_tenant_queries(
    tenant_id: str,
    limit: int = Query(50, ge=1, le=200, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status: Optional[str] = Query(None, description="Filter by status (success/error)"),
    search: Optional[str] = Query(None, description="Search in questions"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    _: bool = Depends(verify_admin_api_key)
):
    """
    Get detailed query history for a specific tenant.

    Returns paginated list of all queries with:
    - Natural language question asked
    - SQL query generated
    - Execution results
    - Token usage
    - Response times

    Headers Required:
    - X-Admin-API-Key: Admin authentication key
    """
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")

    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    service = get_admin_service()
    result = service.get_tenant_query_history(
        tenant_id=tenant_uuid,
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        start_date=start_dt,
        end_date=end_dt
    )

    if "error" in result:
        logger.error(f"[ADMIN_API] Error getting tenant queries: {result['error']}")

    return result


@router.get("/admin/analytics")
async def get_platform_analytics(
    start_date: Optional[str] = Query(None, description="Analytics start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Analytics end date (ISO format)"),
    _: bool = Depends(verify_admin_api_key)
):
    """
    Get overall platform analytics.

    Returns:
    - Tenant statistics (total, active, online)
    - Query statistics (total, success rate, avg time)
    - Top tenants by query volume
    - Token usage summary

    Headers Required:
    - X-Admin-API-Key: Admin authentication key
    """
    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    service = get_admin_service()
    result = service.get_platform_analytics(
        start_date=start_dt,
        end_date=end_dt
    )

    if "error" in result:
        logger.error(f"[ADMIN_API] Error getting analytics: {result['error']}")

    return result


@router.get("/admin/dashboard")
async def get_admin_dashboard(
    _: bool = Depends(verify_admin_api_key)
):
    """
    Get combined dashboard data for quick overview.

    Returns all data needed for the admin dashboard in a single call:
    - Platform analytics summary
    - Online/offline tenant counts
    - Top 5 most active tenants
    - Recent queries across all tenants

    Headers Required:
    - X-Admin-API-Key: Admin authentication key
    """
    service = get_admin_service()

    # Get analytics
    analytics = service.get_platform_analytics()

    # Get tenants with status (first 20)
    tenants = service.get_all_tenants_with_status(limit=20)

    return {
        "summary": {
            "total_tenants": analytics["tenant_stats"]["total_tenants"],
            "active_tenants": analytics["tenant_stats"]["active_tenants"],
            "online_tenants": analytics["tenant_stats"]["online_tenants"],
            "offline_tenants": analytics["tenant_stats"]["offline_tenants"],
            "total_queries": analytics["query_stats"]["total_queries"],
            "success_rate": analytics["query_stats"]["success_rate"],
            "total_tokens": analytics["query_stats"]["total_tokens_used"],
        },
        "top_tenants": analytics["top_tenants"][:5],
        "recent_tenants": tenants["tenants"][:10],
        "timestamp": datetime.utcnow().isoformat()
    }
