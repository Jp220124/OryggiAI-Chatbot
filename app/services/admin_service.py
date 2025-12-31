"""
Admin Service

Provides aggregated data about all chatbot tenants for the Master Dashboard.
Includes tenant status, query statistics, and detailed query history.

PERFORMANCE OPTIMIZED: Uses JOINs and subqueries instead of N+1 patterns.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict

from sqlalchemy import func, desc, case, and_, or_
from sqlalchemy.orm import joinedload

from app.models.platform.tenant import Tenant, TenantStatus
from app.models.platform.database import TenantDatabase
from app.models.platform.gateway import GatewaySession, GatewayQueryLog, SessionStatus, QueryStatus
from app.database.platform_connection import platform_db
# Import gateway_manager at module level (not inside loops)
from app.gateway.connection_manager import gateway_manager

logger = logging.getLogger(__name__)


class AdminService:
    """
    Service for admin/master dashboard data aggregation.

    Provides:
    - All tenants with online/offline status
    - Query statistics per tenant
    - Query history with questions and answers
    - Overall platform analytics
    """

    def __init__(self):
        pass

    def get_all_tenants_with_status(
        self,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get all chatbot tenants with their online/offline status.

        PERFORMANCE OPTIMIZED: Uses batch queries instead of N+1 pattern.
        - Single query for all tenants
        - Single query for all connected databases
        - Single query for all query stats (grouped by tenant_id)
        - Single query for all last queries (using subquery)

        Returns:
            Dict with tenants list and their connection status
        """
        try:
            with platform_db.session_scope() as db:
                # Base tenant query
                query = db.query(Tenant)

                if not include_inactive:
                    query = query.filter(
                        Tenant.status == TenantStatus.ACTIVE.value,
                        Tenant.deleted_at.is_(None)
                    )

                # Get total count
                total = query.count()

                # Get paginated tenants (Query 1)
                tenants = query.order_by(Tenant.created_at.desc()).offset(offset).limit(limit).all()

                if not tenants:
                    return {
                        "tenants": [],
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "has_more": False,
                        "online_count": 0,
                        "offline_count": 0,
                    }

                # Get all tenant IDs for batch queries
                tenant_ids = [tenant.id for tenant in tenants]

                # BATCH QUERY 2: Get ALL connected databases for all tenants at once
                connected_databases = db.query(TenantDatabase).filter(
                    TenantDatabase.tenant_id.in_(tenant_ids),
                    TenantDatabase.gateway_connected == True,
                    TenantDatabase.is_active == True
                ).all()

                # Group databases by tenant_id for quick lookup
                databases_by_tenant = defaultdict(list)
                for db_item in connected_databases:
                    databases_by_tenant[db_item.tenant_id].append(db_item)

                # BATCH QUERY 3: Get query stats for ALL tenants at once (grouped)
                stats_query = db.query(
                    GatewayQueryLog.tenant_id,
                    func.count(GatewayQueryLog.id).label('total_queries'),
                    func.sum(case((GatewayQueryLog.status == QueryStatus.SUCCESS.value, 1), else_=0)).label('success_count'),
                    func.sum(case((GatewayQueryLog.status == QueryStatus.ERROR.value, 1), else_=0)).label('error_count'),
                ).filter(
                    GatewayQueryLog.tenant_id.in_(tenant_ids)
                ).group_by(GatewayQueryLog.tenant_id).all()

                # Create lookup dict for stats
                stats_by_tenant = {
                    row.tenant_id: {
                        'total_queries': row.total_queries or 0,
                        'success_count': row.success_count or 0,
                        'error_count': row.error_count or 0,
                    }
                    for row in stats_query
                }

                # BATCH QUERY 4: Get last query for ALL tenants using a subquery with row_number
                # This is more efficient than fetching for each tenant
                from sqlalchemy import text
                from sqlalchemy.sql import func as sql_func

                # Subquery to get max requested_at per tenant
                last_query_subq = db.query(
                    GatewayQueryLog.tenant_id,
                    sql_func.max(GatewayQueryLog.requested_at).label('max_requested_at')
                ).filter(
                    GatewayQueryLog.tenant_id.in_(tenant_ids)
                ).group_by(GatewayQueryLog.tenant_id).subquery()

                # Join to get full records of last queries
                last_queries = db.query(GatewayQueryLog).join(
                    last_query_subq,
                    and_(
                        GatewayQueryLog.tenant_id == last_query_subq.c.tenant_id,
                        GatewayQueryLog.requested_at == last_query_subq.c.max_requested_at
                    )
                ).all()

                # Create lookup dict for last queries
                last_query_by_tenant = {q.tenant_id: q for q in last_queries}

                # Build tenant data using pre-fetched data (no more N+1!)
                tenant_data = []
                for tenant in tenants:
                    # Check gateway connection status from pre-fetched databases
                    tenant_databases = databases_by_tenant.get(tenant.id, [])

                    is_online = False
                    agent_version = None
                    agent_hostname = None
                    connected_since = None

                    for connected_database in tenant_databases:
                        # Verify the connection is actually live in the gateway manager
                        if gateway_manager.is_connected(str(connected_database.id)):
                            is_online = True
                            session_info = gateway_manager.get_session_info(str(connected_database.id))
                            if session_info:
                                agent_version = session_info.agent_version
                                agent_hostname = session_info.agent_hostname
                                connected_since = session_info.connected_at.isoformat() if session_info.connected_at else None
                            break  # Found an active connection

                    # Get stats from pre-fetched data
                    stats = stats_by_tenant.get(tenant.id, {
                        'total_queries': 0,
                        'success_count': 0,
                        'error_count': 0,
                    })

                    # Get last query from pre-fetched data
                    last_query = last_query_by_tenant.get(tenant.id)

                    tenant_data.append({
                        "id": str(tenant.id),
                        "name": tenant.name,
                        "slug": tenant.slug,
                        "admin_email": tenant.admin_email,
                        "status": tenant.status,
                        "plan": tenant.plan,
                        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,

                        # Connection status (from in-memory gateway manager)
                        "is_online": is_online,
                        "agent_version": agent_version,
                        "agent_hostname": agent_hostname,
                        "connected_since": connected_since,

                        # Query statistics (from batch query)
                        "total_queries": stats['total_queries'],
                        "successful_queries": stats['success_count'],
                        "failed_queries": stats['error_count'],
                        "success_rate": round(stats['success_count'] / max(stats['total_queries'], 1) * 100, 1),

                        # Last activity (from batch query)
                        "last_query_at": last_query.requested_at.isoformat() if last_query else None,
                        "last_question": last_query.natural_language_question if last_query else None,
                    })

                logger.info(f"[ADMIN] Fetched {len(tenant_data)} tenants with 4 queries (optimized from N+1)")

                return {
                    "tenants": tenant_data,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total,
                    "online_count": sum(1 for t in tenant_data if t["is_online"]),
                    "offline_count": sum(1 for t in tenant_data if not t["is_online"]),
                }

        except Exception as e:
            logger.error(f"[ADMIN] Failed to get tenants with status: {e}", exc_info=True)
            return {
                "tenants": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "online_count": 0,
                "offline_count": 0,
                "error": str(e)
            }

    def get_tenant_detail(self, tenant_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific tenant.

        Returns:
            Dict with tenant details, databases, sessions, and recent queries
        """
        try:
            with platform_db.session_scope() as db:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

                if not tenant:
                    return None

                # Get databases
                databases = db.query(TenantDatabase).filter(
                    TenantDatabase.tenant_id == tenant_id,
                    TenantDatabase.is_active == True
                ).all()

                # Get active gateway connections from in-memory manager
                # (gateway_manager imported at module level for performance)

                # Get databases that have gateway_connected = True
                gateway_databases = db.query(TenantDatabase).filter(
                    TenantDatabase.tenant_id == tenant_id,
                    TenantDatabase.gateway_connected == True,
                    TenantDatabase.is_active == True
                ).all()

                # Check which are actually connected in the gateway manager
                active_sessions = []
                for gw_db in gateway_databases:
                    if gateway_manager.is_connected(str(gw_db.id)):
                        session_info = gateway_manager.get_session_info(str(gw_db.id))
                        if session_info:
                            active_sessions.append(session_info)

                # Get recent session history
                recent_sessions = db.query(GatewaySession).filter(
                    GatewaySession.tenant_id == tenant_id
                ).order_by(GatewaySession.connected_at.desc()).limit(10).all()

                # Get query statistics
                query_stats = db.query(
                    func.count(GatewayQueryLog.id).label('total_queries'),
                    func.sum(case((GatewayQueryLog.status == QueryStatus.SUCCESS.value, 1), else_=0)).label('success_count'),
                    func.sum(case((GatewayQueryLog.status == QueryStatus.ERROR.value, 1), else_=0)).label('error_count'),
                    func.avg(GatewayQueryLog.execution_time_ms).label('avg_execution_time'),
                    func.sum(GatewayQueryLog.tokens_used).label('total_tokens'),
                ).filter(
                    GatewayQueryLog.tenant_id == tenant_id
                ).first()

                # Get recent queries
                recent_queries = db.query(GatewayQueryLog).filter(
                    GatewayQueryLog.tenant_id == tenant_id
                ).order_by(GatewayQueryLog.requested_at.desc()).limit(20).all()

                return {
                    "tenant": {
                        "id": str(tenant.id),
                        "name": tenant.name,
                        "slug": tenant.slug,
                        "admin_email": tenant.admin_email,
                        "status": tenant.status,
                        "plan": tenant.plan,
                        "industry": tenant.industry,
                        "company_size": tenant.company_size,
                        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                        "max_queries_per_day": tenant.max_queries_per_day,
                        "max_databases": tenant.max_databases,
                        "max_users": tenant.max_users,
                    },
                    "databases": [
                        {
                            "id": str(db_item.id),
                            "name": db_item.name,
                            "db_type": db_item.db_type,
                            "is_active": db_item.is_active,
                            "schema_analyzed": db_item.schema_analyzed,
                            "created_at": db_item.created_at.isoformat() if db_item.created_at else None,
                        }
                        for db_item in databases
                    ],
                    "connection_status": {
                        "is_online": len(active_sessions) > 0,
                        "active_sessions": len(active_sessions),
                        "sessions": [
                            {
                                "session_id": session.session_id,
                                "database_id": session.database_id,
                                "agent_version": session.agent_version,
                                "agent_hostname": session.agent_hostname,
                                "connected_at": session.connected_at.isoformat() if session.connected_at else None,
                                "last_heartbeat": session.last_heartbeat.isoformat() if session.last_heartbeat else None,
                                "db_status": session.db_status.value if hasattr(session.db_status, 'value') else str(session.db_status),
                                "queries_executed": session.queries_executed,
                            }
                            for session in active_sessions
                        ]
                    },
                    "session_history": [
                        {
                            "session_id": session.session_id,
                            "status": session.status,
                            "connected_at": session.connected_at.isoformat() if session.connected_at else None,
                            "disconnected_at": session.disconnected_at.isoformat() if session.disconnected_at else None,
                            "queries_executed": session.queries_executed,
                            "errors_count": session.errors_count,
                        }
                        for session in recent_sessions
                    ],
                    "statistics": {
                        "total_queries": query_stats.total_queries or 0,
                        "successful_queries": query_stats.success_count or 0,
                        "failed_queries": query_stats.error_count or 0,
                        "success_rate": round((query_stats.success_count or 0) / (query_stats.total_queries or 1) * 100, 1),
                        "avg_execution_time_ms": round(float(query_stats.avg_execution_time or 0), 2),
                        "total_tokens_used": query_stats.total_tokens or 0,
                    },
                    "recent_queries": [
                        {
                            "request_id": query.request_id,
                            "question": query.natural_language_question,
                            "sql_query": query.sql_query,
                            "status": query.status,
                            "row_count": query.row_count,
                            "execution_time_ms": query.execution_time_ms,
                            "tokens_used": query.tokens_used,
                            "llm_model": query.llm_model,
                            "requested_at": query.requested_at.isoformat() if query.requested_at else None,
                            "error_message": query.error_message,
                        }
                        for query in recent_queries
                    ]
                }

        except Exception as e:
            logger.error(f"[ADMIN] Failed to get tenant detail: {e}")
            return None

    def get_tenant_query_history(
        self,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        status: str = None,
        search: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Get detailed query history for a tenant.

        Args:
            tenant_id: The tenant to get history for
            limit: Max records to return
            offset: Pagination offset
            status: Filter by status (success/error)
            search: Search in questions
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Dict with queries list and pagination info
        """
        try:
            with platform_db.session_scope() as db:
                query = db.query(GatewayQueryLog).filter(
                    GatewayQueryLog.tenant_id == tenant_id
                )

                # Apply filters
                if status:
                    query = query.filter(GatewayQueryLog.status == status)
                if search:
                    query = query.filter(
                        GatewayQueryLog.natural_language_question.ilike(f"%{search}%")
                    )
                if start_date:
                    query = query.filter(GatewayQueryLog.requested_at >= start_date)
                if end_date:
                    query = query.filter(GatewayQueryLog.requested_at <= end_date)

                # Get total count
                total = query.count()

                # Get paginated results
                queries = query.order_by(
                    GatewayQueryLog.requested_at.desc()
                ).offset(offset).limit(limit).all()

                return {
                    "queries": [
                        {
                            "request_id": q.request_id,
                            "question": q.natural_language_question,
                            "sql_query": q.sql_query,
                            "status": q.status,
                            "row_count": q.row_count,
                            "execution_time_ms": q.execution_time_ms,
                            "generation_time_ms": q.generation_time_ms,
                            "tokens_used": q.tokens_used,
                            "llm_model": q.llm_model,
                            "requested_at": q.requested_at.isoformat() if q.requested_at else None,
                            "completed_at": q.completed_at.isoformat() if q.completed_at else None,
                            "error_message": q.error_message,
                            "conversation_id": q.conversation_id,
                        }
                        for q in queries
                    ],
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total,
                }

        except Exception as e:
            logger.error(f"[ADMIN] Failed to get tenant query history: {e}")
            return {
                "queries": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "error": str(e)
            }

    def get_platform_analytics(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Get overall platform analytics.

        Returns aggregated statistics across all tenants.
        """
        try:
            with platform_db.session_scope() as db:
                # Default to last 30 days
                if not start_date:
                    start_date = datetime.utcnow() - timedelta(days=30)
                if not end_date:
                    end_date = datetime.utcnow()

                # Tenant counts
                total_tenants = db.query(func.count(Tenant.id)).filter(
                    Tenant.deleted_at.is_(None)
                ).scalar()

                active_tenants = db.query(func.count(Tenant.id)).filter(
                    Tenant.status == TenantStatus.ACTIVE.value,
                    Tenant.deleted_at.is_(None)
                ).scalar()

                # Online tenants (using in-memory gateway manager for accurate count)
                # (gateway_manager imported at module level for performance)
                all_sessions = gateway_manager.get_all_sessions()
                online_tenant_ids = set(s.tenant_id for s in all_sessions if s.is_active)
                online_tenants = len(online_tenant_ids)

                # Query statistics (within date range)
                query_stats = db.query(
                    func.count(GatewayQueryLog.id).label('total_queries'),
                    func.sum(case((GatewayQueryLog.status == QueryStatus.SUCCESS.value, 1), else_=0)).label('success_count'),
                    func.sum(case((GatewayQueryLog.status == QueryStatus.ERROR.value, 1), else_=0)).label('error_count'),
                    func.avg(GatewayQueryLog.execution_time_ms).label('avg_execution_time'),
                    func.sum(GatewayQueryLog.tokens_used).label('total_tokens'),
                    func.count(func.distinct(GatewayQueryLog.tenant_id)).label('tenants_with_queries'),
                ).filter(
                    GatewayQueryLog.requested_at >= start_date,
                    GatewayQueryLog.requested_at <= end_date
                ).first()

                # Queries per day (last 7 days) - simplified without grouping
                seven_days_ago = datetime.utcnow() - timedelta(days=7)
                recent_query_count = db.query(func.count(GatewayQueryLog.id)).filter(
                    GatewayQueryLog.requested_at >= seven_days_ago
                ).scalar() or 0

                # Top tenants by query count
                top_tenants = db.query(
                    Tenant.name,
                    Tenant.slug,
                    func.count(GatewayQueryLog.id).label('query_count')
                ).join(
                    GatewayQueryLog, GatewayQueryLog.tenant_id == Tenant.id
                ).filter(
                    GatewayQueryLog.requested_at >= start_date,
                    GatewayQueryLog.requested_at <= end_date
                ).group_by(
                    Tenant.id, Tenant.name, Tenant.slug
                ).order_by(
                    desc('query_count')
                ).limit(10).all()

                return {
                    "tenant_stats": {
                        "total_tenants": total_tenants or 0,
                        "active_tenants": active_tenants or 0,
                        "online_tenants": online_tenants or 0,
                        "offline_tenants": (active_tenants or 0) - (online_tenants or 0),
                    },
                    "query_stats": {
                        "total_queries": query_stats.total_queries or 0,
                        "successful_queries": query_stats.success_count or 0,
                        "failed_queries": query_stats.error_count or 0,
                        "success_rate": round((query_stats.success_count or 0) / (query_stats.total_queries or 1) * 100, 1),
                        "avg_execution_time_ms": round(float(query_stats.avg_execution_time or 0), 2),
                        "total_tokens_used": query_stats.total_tokens or 0,
                        "tenants_with_activity": query_stats.tenants_with_queries or 0,
                    },
                    "top_tenants": [
                        {
                            "name": tenant.name,
                            "slug": tenant.slug,
                            "query_count": tenant.query_count,
                        }
                        for tenant in top_tenants
                    ],
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                    }
                }

        except Exception as e:
            logger.error(f"[ADMIN] Failed to get platform analytics: {e}")
            return {
                "tenant_stats": {
                    "total_tenants": 0,
                    "active_tenants": 0,
                    "online_tenants": 0,
                    "offline_tenants": 0,
                },
                "query_stats": {
                    "total_queries": 0,
                    "successful_queries": 0,
                    "failed_queries": 0,
                    "success_rate": 0,
                    "avg_execution_time_ms": 0,
                    "total_tokens_used": 0,
                    "tenants_with_activity": 0,
                },
                "top_tenants": [],
                "error": str(e)
            }


# Singleton instance
_admin_service: Optional[AdminService] = None


def get_admin_service() -> AdminService:
    """Get the singleton AdminService instance."""
    global _admin_service
    if _admin_service is None:
        _admin_service = AdminService()
    return _admin_service
