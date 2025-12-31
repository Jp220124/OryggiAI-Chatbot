"""
Query Logging Service

Handles logging of all queries executed through the OryggiAI platform.
Logs both natural language questions and generated SQL queries for:
- Analytics and usage tracking
- Debugging and troubleshooting
- Audit trail and compliance
- AI improvement and training
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func, desc

from app.models.platform.gateway import GatewayQueryLog, QueryStatus
from app.database.platform_connection import platform_db, get_platform_session

logger = logging.getLogger(__name__)


class QueryLoggingService:
    """
    Service for logging and retrieving query execution history.

    Features:
    - Async logging to prevent blocking main request flow
    - Query history retrieval with filtering
    - Analytics aggregation
    """

    def __init__(self):
        pass

    def log_query(
        self,
        tenant_id: uuid.UUID,
        database_id: uuid.UUID,
        sql_query: str,
        natural_language_question: str = None,
        session_id: uuid.UUID = None,
        user_id: uuid.UUID = None,
        conversation_id: str = None,
        llm_model: str = None,
        tokens_used: int = None,
        generation_time_ms: int = None,
    ) -> Optional[str]:
        """
        Log a query execution.

        Args:
            tenant_id: The tenant who made the query
            database_id: The database being queried
            sql_query: The generated SQL query
            natural_language_question: The original question asked
            session_id: Gateway session ID (if via gateway)
            user_id: User who made the query
            conversation_id: Chat conversation ID
            llm_model: AI model used to generate SQL
            tokens_used: Number of tokens consumed
            generation_time_ms: Time taken to generate SQL

        Returns:
            request_id: Unique identifier for this query log
        """
        request_id = str(uuid.uuid4())

        try:
            with platform_db.session_scope() as db:
                query_log = GatewayQueryLog.create_log(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    database_id=database_id,
                    sql_query=sql_query,
                    natural_language_question=natural_language_question,
                    session_id=session_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    llm_model=llm_model,
                    tokens_used=tokens_used,
                    generation_time_ms=generation_time_ms,
                )

                db.add(query_log)
                # session_scope auto-commits

                logger.info(
                    f"[QUERY_LOG] Logged query: tenant={tenant_id}, "
                    f"question='{natural_language_question[:50] if natural_language_question else 'N/A'}...', "
                    f"request_id={request_id}"
                )

                return request_id

        except Exception as e:
            logger.error(f"[QUERY_LOG] Failed to log query: {e}")
            # Don't raise - logging failures shouldn't break the main flow
            return None

    def update_query_result(
        self,
        request_id: str,
        success: bool,
        row_count: int = 0,
        execution_time_ms: int = None,
        error_message: str = None,
        error_code: str = None,
    ) -> bool:
        """
        Update a query log with execution results.

        Args:
            request_id: The query log to update
            success: Whether execution succeeded
            row_count: Number of rows returned
            execution_time_ms: Query execution time
            error_message: Error details if failed
            error_code: Error code if failed

        Returns:
            bool: Whether update succeeded
        """
        try:
            with platform_db.session_scope() as db:
                query_log = db.query(GatewayQueryLog).filter(
                    GatewayQueryLog.request_id == request_id
                ).first()

                if not query_log:
                    logger.warning(f"[QUERY_LOG] Query log not found: {request_id}")
                    return False

                if success:
                    query_log.complete_success(row_count, execution_time_ms)
                else:
                    query_log.complete_error(error_message, error_code)

                # session_scope auto-commits

                logger.info(
                    f"[QUERY_LOG] Updated query result: request_id={request_id}, "
                    f"success={success}, rows={row_count}"
                )

                return True

        except Exception as e:
            logger.error(f"[QUERY_LOG] Failed to update query result: {e}")
            return False

    async def get_tenant_query_history(
        self,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        database_id: uuid.UUID = None,
        user_id: uuid.UUID = None,
        status: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Get query history for a tenant with filtering.

        Args:
            tenant_id: Tenant to get history for
            limit: Maximum records to return
            offset: Pagination offset
            database_id: Filter by specific database
            user_id: Filter by specific user
            status: Filter by status (success/error/timeout)
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Dict with queries list and pagination info
        """
        try:
            with platform_db.session_scope() as db:
                # Build query with filters
                query = db.query(GatewayQueryLog).filter(
                    GatewayQueryLog.tenant_id == tenant_id
                )

                if database_id:
                    query = query.filter(GatewayQueryLog.database_id == database_id)
                if user_id:
                    query = query.filter(GatewayQueryLog.user_id == user_id)
                if status:
                    query = query.filter(GatewayQueryLog.status == status)
                if start_date:
                    query = query.filter(GatewayQueryLog.requested_at >= start_date)
                if end_date:
                    query = query.filter(GatewayQueryLog.requested_at <= end_date)

                # Get total count
                total = query.count()

                # Get paginated results
                logs = query.order_by(
                    GatewayQueryLog.requested_at.desc()
                ).offset(offset).limit(limit).all()

                return {
                    "queries": [
                        {
                            "request_id": log.request_id,
                            "question": log.natural_language_question,
                            "sql_query": log.sql_query,
                            "status": log.status,
                            "row_count": log.row_count,
                            "execution_time_ms": log.execution_time_ms,
                            "error_message": log.error_message,
                            "requested_at": log.requested_at.isoformat() if log.requested_at else None,
                            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                            "llm_model": log.llm_model,
                            "tokens_used": log.tokens_used,
                            "conversation_id": log.conversation_id,
                        }
                        for log in logs
                    ],
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total,
                }

        except Exception as e:
            logger.error(f"[QUERY_LOG] Failed to get query history: {e}")
            return {"queries": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}

    async def get_tenant_analytics(
        self,
        tenant_id: uuid.UUID,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Get query analytics for a tenant.

        Returns aggregated statistics about query usage.
        """
        try:
            with platform_db.session_scope() as db:
                base_query = db.query(GatewayQueryLog).filter(
                    GatewayQueryLog.tenant_id == tenant_id
                )

                if start_date:
                    base_query = base_query.filter(GatewayQueryLog.requested_at >= start_date)
                if end_date:
                    base_query = base_query.filter(GatewayQueryLog.requested_at <= end_date)

                # Total queries
                total_queries = base_query.count()

                # Success count
                success_count = base_query.filter(
                    GatewayQueryLog.status == QueryStatus.SUCCESS.value
                ).count()

                # Error count
                error_count = base_query.filter(
                    GatewayQueryLog.status == QueryStatus.ERROR.value
                ).count()

                # Average execution time
                from sqlalchemy import func as sqlfunc
                avg_result = db.query(sqlfunc.avg(GatewayQueryLog.execution_time_ms)).filter(
                    GatewayQueryLog.tenant_id == tenant_id,
                    GatewayQueryLog.execution_time_ms.isnot(None)
                ).scalar()
                avg_execution_time = avg_result or 0

                # Total tokens used
                tokens_result = db.query(sqlfunc.sum(GatewayQueryLog.tokens_used)).filter(
                    GatewayQueryLog.tenant_id == tenant_id,
                    GatewayQueryLog.tokens_used.isnot(None)
                ).scalar()
                total_tokens = tokens_result or 0

                return {
                    "total_queries": total_queries,
                    "success_count": success_count,
                    "error_count": error_count,
                    "success_rate": (success_count / total_queries * 100) if total_queries > 0 else 0,
                    "avg_execution_time_ms": round(float(avg_execution_time), 2),
                    "total_tokens_used": total_tokens,
                }

        except Exception as e:
            logger.error(f"[QUERY_LOG] Failed to get analytics: {e}")
            return {
                "total_queries": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0,
                "avg_execution_time_ms": 0,
                "total_tokens_used": 0,
            }


# Singleton instance
_query_logging_service: Optional[QueryLoggingService] = None


def get_query_logging_service() -> QueryLoggingService:
    """Get the singleton QueryLoggingService instance."""
    global _query_logging_service
    if _query_logging_service is None:
        _query_logging_service = QueryLoggingService()
    return _query_logging_service


# Convenience functions for easy import
def log_query(**kwargs) -> Optional[str]:
    """Log a query execution."""
    service = get_query_logging_service()
    return service.log_query(**kwargs)


def update_query_result(**kwargs) -> bool:
    """Update a query log with results."""
    service = get_query_logging_service()
    return service.update_query_result(**kwargs)
