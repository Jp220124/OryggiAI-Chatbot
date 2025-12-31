"""
Usage Tracking Service
Provides functions for tracking and retrieving tenant usage metrics
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from app.models.platform import UsageMetrics, AuditLog, Tenant
from app.models.platform.metrics import EventType, EventAction, EventStatus


class UsageService:
    """
    Service for tracking and analyzing tenant usage metrics.

    Provides methods to:
    - Track query executions
    - Record feature usage (reports, emails, actions)
    - Get usage statistics and summaries
    - Check usage limits
    """

    @staticmethod
    def track_query(
        db: Session,
        tenant_id: uuid.UUID,
        success: bool,
        tokens: int = 0,
        response_time_ms: int = None,
        is_sql_query: bool = True,
        user_id: uuid.UUID = None,
        sql_query: str = None,
        rows_affected: int = None,
        ip_address: str = None,
        request_id: str = None
    ) -> UsageMetrics:
        """
        Track a query execution.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            success: Whether query succeeded
            tokens: Number of tokens used
            response_time_ms: Response time in milliseconds
            is_sql_query: Whether this was a SQL query
            user_id: User who made the query
            sql_query: The SQL query executed
            rows_affected: Number of rows affected
            ip_address: Client IP address
            request_id: Request correlation ID

        Returns:
            Updated UsageMetrics record
        """
        try:
            # Get or create today's metrics
            metrics = UsageMetrics.get_or_create_for_today(db, tenant_id)

            # Update metrics
            metrics.increment_query(success, tokens, response_time_ms)

            if is_sql_query:
                metrics.increment_sql_query()

            # Log to audit
            AuditLog.log_event(
                session=db,
                event_type=EventType.QUERY.value,
                event_action=EventAction.EXECUTE.value,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="query",
                sql_query=sql_query[:1000] if sql_query else None,  # Limit SQL length
                query_duration_ms=response_time_ms,
                rows_affected=rows_affected,
                status=EventStatus.SUCCESS.value if success else EventStatus.FAILURE.value,
                ip_address=ip_address,
                request_id=request_id
            )

            db.commit()
            return metrics

        except Exception as e:
            logger.error(f"Failed to track query: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    def track_report(
        db: Session,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID = None,
        report_type: str = None,
        ip_address: str = None
    ) -> UsageMetrics:
        """Track a report generation"""
        try:
            metrics = UsageMetrics.get_or_create_for_today(db, tenant_id)
            metrics.increment_report()

            AuditLog.log_event(
                session=db,
                event_type=EventType.ACTION.value,
                event_action=EventAction.CREATE.value,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="report",
                description=f"Generated report: {report_type}" if report_type else "Report generated",
                ip_address=ip_address
            )

            db.commit()
            return metrics
        except Exception as e:
            logger.error(f"Failed to track report: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    def track_email(
        db: Session,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID = None,
        recipient_count: int = 1,
        ip_address: str = None
    ) -> UsageMetrics:
        """Track an email sent"""
        try:
            metrics = UsageMetrics.get_or_create_for_today(db, tenant_id)
            metrics.increment_email()

            AuditLog.log_event(
                session=db,
                event_type=EventType.ACTION.value,
                event_action=EventAction.EXECUTE.value,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="email",
                description=f"Sent email to {recipient_count} recipient(s)",
                ip_address=ip_address
            )

            db.commit()
            return metrics
        except Exception as e:
            logger.error(f"Failed to track email: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    def track_action(
        db: Session,
        tenant_id: uuid.UUID,
        action_type: str,
        user_id: uuid.UUID = None,
        description: str = None,
        ip_address: str = None
    ) -> UsageMetrics:
        """Track a custom action execution"""
        try:
            metrics = UsageMetrics.get_or_create_for_today(db, tenant_id)
            metrics.increment_action()

            AuditLog.log_event(
                session=db,
                event_type=EventType.ACTION.value,
                event_action=EventAction.EXECUTE.value,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="action",
                description=description or f"Executed action: {action_type}",
                ip_address=ip_address
            )

            db.commit()
            return metrics
        except Exception as e:
            logger.error(f"Failed to track action: {str(e)}")
            db.rollback()
            raise

    @staticmethod
    def track_login(
        db: Session,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        success: bool,
        ip_address: str = None,
        user_agent: str = None,
        error_message: str = None
    ) -> None:
        """Track a login attempt"""
        try:
            AuditLog.log_event(
                session=db,
                event_type=EventType.LOGIN.value,
                event_action=EventAction.LOGIN_SUCCESS.value if success else EventAction.LOGIN_FAILED.value,
                tenant_id=tenant_id,
                user_id=user_id if success else None,
                resource_type="session",
                status=EventStatus.SUCCESS.value if success else EventStatus.FAILURE.value,
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.commit()
        except Exception as e:
            logger.error(f"Failed to track login: {str(e)}")
            db.rollback()

    @staticmethod
    def get_today_usage(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """Get today's usage statistics"""
        metrics = UsageMetrics.get_or_create_for_today(db, tenant_id)

        return {
            "date": str(metrics.metric_date),
            "total_queries": metrics.total_queries,
            "successful_queries": metrics.successful_queries,
            "failed_queries": metrics.failed_queries,
            "success_rate": round(metrics.success_rate * 100, 2),
            "total_tokens_used": metrics.total_tokens_used,
            "avg_response_time_ms": metrics.avg_response_time_ms,
            "max_response_time_ms": metrics.max_response_time_ms,
            "sql_queries": metrics.sql_queries,
            "reports_generated": metrics.reports_generated,
            "emails_sent": metrics.emails_sent,
            "actions_executed": metrics.actions_executed,
            "active_users": metrics.active_users,
            "estimated_cost": round(metrics.total_cost_estimate, 4)
        }

    @staticmethod
    def get_usage_summary(
        db: Session,
        tenant_id: uuid.UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage summary for a time period.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            days: Number of days to include

        Returns:
            Dict with aggregated usage statistics
        """
        start_date = date.today() - timedelta(days=days)

        # Query aggregated metrics
        result = db.query(
            func.sum(UsageMetrics.total_queries).label("total_queries"),
            func.sum(UsageMetrics.successful_queries).label("successful_queries"),
            func.sum(UsageMetrics.failed_queries).label("failed_queries"),
            func.sum(UsageMetrics.total_tokens_used).label("total_tokens"),
            func.avg(UsageMetrics.avg_response_time_ms).label("avg_response_time"),
            func.sum(UsageMetrics.sql_queries).label("sql_queries"),
            func.sum(UsageMetrics.reports_generated).label("reports"),
            func.sum(UsageMetrics.emails_sent).label("emails"),
            func.sum(UsageMetrics.actions_executed).label("actions"),
            func.max(UsageMetrics.active_users).label("peak_active_users")
        ).filter(
            UsageMetrics.tenant_id == tenant_id,
            UsageMetrics.metric_date >= start_date
        ).first()

        total_queries = result.total_queries or 0
        successful_queries = result.successful_queries or 0

        return {
            "period_days": days,
            "start_date": str(start_date),
            "end_date": str(date.today()),
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": result.failed_queries or 0,
            "success_rate": round((successful_queries / total_queries * 100) if total_queries > 0 else 0, 2),
            "total_tokens": result.total_tokens or 0,
            "avg_response_time_ms": round(result.avg_response_time or 0, 2),
            "sql_queries": result.sql_queries or 0,
            "reports_generated": result.reports or 0,
            "emails_sent": result.emails or 0,
            "actions_executed": result.actions or 0,
            "peak_active_users": result.peak_active_users or 0,
            "estimated_cost": round(((result.total_tokens or 0) / 1000) * 0.002, 4)
        }

    @staticmethod
    def get_daily_usage(
        db: Session,
        tenant_id: uuid.UUID,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get daily usage breakdown"""
        start_date = date.today() - timedelta(days=days)

        metrics = db.query(UsageMetrics).filter(
            UsageMetrics.tenant_id == tenant_id,
            UsageMetrics.metric_date >= start_date
        ).order_by(UsageMetrics.metric_date.desc()).all()

        return [
            {
                "date": str(m.metric_date),
                "total_queries": m.total_queries,
                "successful_queries": m.successful_queries,
                "tokens_used": m.total_tokens_used,
                "avg_response_time_ms": m.avg_response_time_ms,
                "active_users": m.active_users
            }
            for m in metrics
        ]

    @staticmethod
    def check_query_limit(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """
        Check if tenant has exceeded their daily query limit.

        Returns:
            Dict with limit status and usage info
        """
        # Get tenant and their plan limits
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return {"allowed": False, "error": "Tenant not found"}

        max_queries = tenant.max_queries_per_day

        # Get today's usage
        metrics = UsageMetrics.get_or_create_for_today(db, tenant_id)
        current_queries = metrics.total_queries or 0  # Handle None

        # -1 means unlimited
        if max_queries == -1:
            return {
                "allowed": True,
                "current_usage": current_queries,
                "limit": "unlimited",
                "remaining": "unlimited"
            }

        remaining = max_queries - current_queries

        return {
            "allowed": remaining > 0,
            "current_usage": current_queries,
            "limit": max_queries,
            "remaining": max(0, remaining),
            "usage_percent": round((current_queries / max_queries) * 100, 2) if max_queries > 0 else 0
        }

    @staticmethod
    def get_audit_logs(
        db: Session,
        tenant_id: uuid.UUID,
        limit: int = 50,
        event_type: str = None,
        user_id: uuid.UUID = None,
        start_date: date = None,
        end_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs for a tenant.

        Args:
            db: Database session
            tenant_id: Tenant UUID
            limit: Maximum records to return
            event_type: Filter by event type
            user_id: Filter by user
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of audit log entries
        """
        query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)

        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time()))

        if end_date:
            query = query.filter(AuditLog.created_at <= datetime.combine(end_date, datetime.max.time()))

        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

        return [
            {
                "id": str(log.id),
                "event_type": log.event_type,
                "event_action": log.event_action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "description": log.description,
                "status": log.status,
                "error_message": log.error_message,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "user_id": str(log.user_id) if log.user_id else None
            }
            for log in logs
        ]


# Global service instance
usage_service = UsageService()
