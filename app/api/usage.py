"""
Usage Statistics API Routes
Endpoints for viewing usage metrics and audit logs
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from loguru import logger

from app.database.platform_connection import get_platform_db
from app.api.deps import CurrentUserDep, AdminDep
from app.services.usage_service import usage_service


router = APIRouter()


# =============================================================================
# Usage Statistics Endpoints
# =============================================================================

@router.get(
    "/today",
    summary="Get today's usage",
    description="Get usage statistics for today"
)
async def get_today_usage(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Get today's usage metrics for the current tenant.

    Returns:
        - total_queries: Total queries executed today
        - successful_queries: Number of successful queries
        - failed_queries: Number of failed queries
        - success_rate: Success rate percentage
        - total_tokens_used: Total LLM tokens consumed
        - avg_response_time_ms: Average response time
        - estimated_cost: Estimated cost in USD
    """
    try:
        return usage_service.get_today_usage(db, current_user.tenant_id)
    except Exception as e:
        logger.error(f"Failed to get today's usage: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage data")


@router.get(
    "/summary",
    summary="Get usage summary",
    description="Get aggregated usage statistics for a time period"
)
async def get_usage_summary(
    current_user: CurrentUserDep,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: Session = Depends(get_platform_db)
):
    """
    Get usage summary for a specified time period.

    Args:
        days: Number of days to include (default: 30, max: 365)

    Returns:
        Aggregated usage statistics including:
        - Total queries across the period
        - Success rate
        - Token consumption
        - Feature usage breakdown
        - Peak active users
        - Estimated costs
    """
    try:
        return usage_service.get_usage_summary(db, current_user.tenant_id, days)
    except Exception as e:
        logger.error(f"Failed to get usage summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage data")


@router.get(
    "/daily",
    summary="Get daily usage breakdown",
    description="Get day-by-day usage metrics"
)
async def get_daily_usage(
    current_user: CurrentUserDep,
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    db: Session = Depends(get_platform_db)
):
    """
    Get daily usage breakdown for charting.

    Args:
        days: Number of days to include (default: 7, max: 90)

    Returns:
        List of daily usage records with:
        - date
        - total_queries
        - successful_queries
        - tokens_used
        - avg_response_time_ms
        - active_users
    """
    try:
        return usage_service.get_daily_usage(db, current_user.tenant_id, days)
    except Exception as e:
        logger.error(f"Failed to get daily usage: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage data")


@router.get(
    "/limits",
    summary="Check usage limits",
    description="Check current usage against plan limits"
)
async def check_usage_limits(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Check current usage against tenant's plan limits.

    Returns:
        - allowed: Whether more queries are allowed
        - current_usage: Number of queries used today
        - limit: Daily query limit (-1 = unlimited)
        - remaining: Queries remaining today
        - usage_percent: Percentage of limit used
    """
    try:
        return usage_service.check_query_limit(db, current_user.tenant_id)
    except Exception as e:
        logger.error(f"Failed to check limits: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check usage limits")


# =============================================================================
# Audit Log Endpoints
# =============================================================================

@router.get(
    "/audit",
    summary="Get audit logs",
    description="Get audit trail for the tenant (admin only)"
)
async def get_audit_logs(
    current_user: AdminDep,
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_platform_db)
):
    """
    Get audit logs for the current tenant.

    Requires admin role.

    Args:
        limit: Maximum records to return (default: 50, max: 500)
        event_type: Filter by event type (login, query, action, etc.)
        start_date: Filter by start date
        end_date: Filter by end date

    Returns:
        List of audit log entries with event details
    """
    try:
        return usage_service.get_audit_logs(
            db=db,
            tenant_id=current_user.tenant_id,
            limit=limit,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        logger.error(f"Failed to get audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get(
    "/audit/events",
    summary="Get available event types",
    description="Get list of available event types for filtering"
)
async def get_event_types(current_user: CurrentUserDep):
    """
    Get list of available audit event types.

    Returns:
        List of event types that can be used for filtering audit logs
    """
    from app.models.platform.metrics import EventType, EventAction

    return {
        "event_types": [e.value for e in EventType],
        "event_actions": [a.value for a in EventAction]
    }


# =============================================================================
# Dashboard Summary Endpoint
# =============================================================================

@router.get(
    "/dashboard",
    summary="Get dashboard summary",
    description="Get comprehensive dashboard data in a single call"
)
async def get_dashboard_summary(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Get comprehensive dashboard data in a single API call.

    Returns all data needed for the usage dashboard:
    - Today's usage
    - 7-day trend
    - 30-day summary
    - Current limits status
    """
    try:
        # Gather all data in parallel would be better, but for simplicity:
        today = usage_service.get_today_usage(db, current_user.tenant_id)
        daily = usage_service.get_daily_usage(db, current_user.tenant_id, days=7)
        summary = usage_service.get_usage_summary(db, current_user.tenant_id, days=30)
        limits = usage_service.check_query_limit(db, current_user.tenant_id)

        return {
            "today": today,
            "daily_trend": daily,
            "monthly_summary": summary,
            "limits": limits,
            "tenant_id": str(current_user.tenant_id),
            "user_role": current_user.role
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")
