"""
Metrics Models
UsageMetrics - Daily usage tracking per tenant
AuditLog - Security and compliance audit trail
"""

import uuid
from datetime import datetime, date
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Date, BigInteger, DECIMAL
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.orm import relationship

from app.models.platform.base import PlatformBase

if TYPE_CHECKING:
    from app.models.platform.tenant import Tenant
    from app.models.platform.user import TenantUser


class EventType(str, Enum):
    """Audit event types"""
    LOGIN = "login"
    LOGOUT = "logout"
    QUERY = "query"
    ACTION = "action"
    CONFIG_CHANGE = "config_change"
    DATA_ACCESS = "data_access"
    ADMIN = "admin"
    SECURITY = "security"


class EventAction(str, Enum):
    """Audit event actions"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    EXPORT = "export"
    IMPORT = "import"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"


class EventStatus(str, Enum):
    """Audit event status"""
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class UsageMetrics(PlatformBase):
    """
    UsageMetrics Model - Daily usage tracking per tenant.

    Aggregates daily metrics for monitoring, billing, and analytics.
    One record per tenant per day.
    """

    __tablename__ = "usage_metrics"

    # ==================== Tenant Relationship ====================
    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ==================== Time Period ====================
    metric_date = Column(Date, nullable=False, index=True)

    # ==================== Query Metrics ====================
    total_queries = Column(Integer, default=0)
    successful_queries = Column(Integer, default=0)
    failed_queries = Column(Integer, default=0)

    # ==================== Token Usage ====================
    total_tokens_used = Column(BigInteger, default=0)
    input_tokens = Column(BigInteger, default=0)
    output_tokens = Column(BigInteger, default=0)

    # ==================== Performance ====================
    avg_response_time_ms = Column(Integer, nullable=True)
    max_response_time_ms = Column(Integer, nullable=True)

    # ==================== Feature Usage ====================
    sql_queries = Column(Integer, default=0)
    reports_generated = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    actions_executed = Column(Integer, default=0)

    # ==================== User Activity ====================
    active_users = Column(Integer, default=0)
    unique_sessions = Column(Integer, default=0)

    # ==================== Storage ====================
    storage_used_mb = Column(DECIMAL(10, 2), default=0)

    # ==================== Relationships ====================
    tenant: "Tenant" = relationship(
        "Tenant",
        back_populates="usage_metrics"
    )

    # ==================== Unique Constraint ====================
    __table_args__ = (
        # One record per tenant per day
        {"sqlite_autoincrement": True},
    )

    # ==================== Properties ====================
    @property
    def success_rate(self) -> float:
        """Calculate query success rate"""
        if self.total_queries == 0:
            return 0.0
        return self.successful_queries / self.total_queries

    @property
    def total_cost_estimate(self) -> float:
        """Estimate cost based on token usage (simplified)"""
        # Rough estimate: $0.002 per 1K tokens
        return (self.total_tokens_used / 1000) * 0.002

    # ==================== Methods ====================
    def increment_query(self, success: bool, tokens: int = 0, response_time_ms: int = None) -> None:
        """Record a query execution"""
        self.total_queries += 1

        if success:
            self.successful_queries += 1
        else:
            self.failed_queries += 1

        if tokens > 0:
            self.total_tokens_used += tokens

        if response_time_ms is not None:
            # Update average response time
            if self.avg_response_time_ms is None:
                self.avg_response_time_ms = response_time_ms
            else:
                # Running average
                total = self.avg_response_time_ms * (self.total_queries - 1)
                self.avg_response_time_ms = (total + response_time_ms) // self.total_queries

            # Update max response time
            if self.max_response_time_ms is None or response_time_ms > self.max_response_time_ms:
                self.max_response_time_ms = response_time_ms

    def increment_sql_query(self) -> None:
        """Record a SQL query"""
        self.sql_queries += 1

    def increment_report(self) -> None:
        """Record a report generation"""
        self.reports_generated += 1

    def increment_email(self) -> None:
        """Record an email sent"""
        self.emails_sent += 1

    def increment_action(self) -> None:
        """Record an action execution"""
        self.actions_executed += 1

    @classmethod
    def get_or_create_for_today(cls, session, tenant_id: uuid.UUID) -> "UsageMetrics":
        """Get or create metrics record for today"""
        today = date.today()

        metrics = session.query(cls).filter(
            cls.tenant_id == tenant_id,
            cls.metric_date == today
        ).first()

        if not metrics:
            metrics = cls(
                tenant_id=tenant_id,
                metric_date=today
            )
            session.add(metrics)

        return metrics

    def __repr__(self) -> str:
        return (
            f"<UsageMetrics(tenant_id={self.tenant_id}, date={self.metric_date}, "
            f"queries={self.total_queries}, tokens={self.total_tokens_used})>"
        )


class AuditLog(PlatformBase):
    """
    AuditLog Model - Security and compliance audit trail.

    Records all significant events for security monitoring,
    compliance, and debugging purposes.
    """

    __tablename__ = "audit_logs"

    # ==================== Context ====================
    # Note: Using NO ACTION for foreign keys to avoid SQL Server
    # "multiple cascade paths" error
    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="NO ACTION"),
        nullable=True,  # NULL for platform-level events
        index=True
    )

    user_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_users.id", ondelete="NO ACTION"),
        nullable=True,
        index=True
    )

    # ==================== Event Details ====================
    event_type = Column(NVARCHAR(100), nullable=False, index=True)
    event_action = Column(NVARCHAR(100), nullable=False)
    resource_type = Column(NVARCHAR(100), nullable=True)
    resource_id = Column(NVARCHAR(255), nullable=True, index=True)

    # ==================== Request Information ====================
    request_id = Column(NVARCHAR(100), nullable=True)
    ip_address = Column(NVARCHAR(50), nullable=True)
    user_agent = Column(NVARCHAR(500), nullable=True)

    # ==================== Event Data ====================
    description = Column(Text, nullable=True)
    old_value = Column(Text, nullable=True)  # JSON: previous state
    new_value = Column(Text, nullable=True)  # JSON: new state

    # ==================== SQL Query (if applicable) ====================
    sql_query = Column(Text, nullable=True)
    query_duration_ms = Column(Integer, nullable=True)
    rows_affected = Column(Integer, nullable=True)

    # ==================== Status ====================
    status = Column(
        NVARCHAR(50),
        default=EventStatus.SUCCESS.value
    )
    error_message = Column(Text, nullable=True)

    # ==================== Relationships ====================
    tenant: "Tenant" = relationship(
        "Tenant",
        back_populates="audit_logs"
    )

    user: "TenantUser" = relationship(
        "TenantUser",
        back_populates="audit_logs"
    )

    # ==================== Properties ====================
    @property
    def is_success(self) -> bool:
        """Check if event was successful"""
        return self.status == EventStatus.SUCCESS.value

    @property
    def is_security_event(self) -> bool:
        """Check if this is a security-related event"""
        return self.event_type in [
            EventType.LOGIN.value,
            EventType.LOGOUT.value,
            EventType.SECURITY.value
        ]

    # ==================== Methods ====================
    def set_old_value(self, value: dict) -> None:
        """Set old value as JSON"""
        import json
        self.old_value = json.dumps(value) if value else None

    def set_new_value(self, value: dict) -> None:
        """Set new value as JSON"""
        import json
        self.new_value = json.dumps(value) if value else None

    def get_old_value(self) -> dict:
        """Get old value as dict"""
        import json
        if self.old_value:
            try:
                return json.loads(self.old_value)
            except json.JSONDecodeError:
                pass
        return {}

    def get_new_value(self) -> dict:
        """Get new value as dict"""
        import json
        if self.new_value:
            try:
                return json.loads(self.new_value)
            except json.JSONDecodeError:
                pass
        return {}

    @classmethod
    def log_event(
        cls,
        session,
        event_type: str,
        event_action: str,
        tenant_id: uuid.UUID = None,
        user_id: uuid.UUID = None,
        resource_type: str = None,
        resource_id: str = None,
        description: str = None,
        old_value: dict = None,
        new_value: dict = None,
        sql_query: str = None,
        query_duration_ms: int = None,
        rows_affected: int = None,
        status: str = EventStatus.SUCCESS.value,
        error_message: str = None,
        request_id: str = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> "AuditLog":
        """
        Create and persist an audit log entry.

        Args:
            session: SQLAlchemy session
            event_type: Type of event (login, query, action, etc.)
            event_action: Action performed (create, read, update, etc.)
            tenant_id: Optional tenant ID
            user_id: Optional user ID
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            description: Human-readable description
            old_value: Previous state (dict)
            new_value: New state (dict)
            sql_query: SQL query executed (if applicable)
            query_duration_ms: Query duration in ms
            rows_affected: Number of rows affected
            status: Event status
            error_message: Error message (if failed)
            request_id: Request correlation ID
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created AuditLog instance
        """
        import json

        log = cls(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            event_action=event_action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            description=description,
            old_value=json.dumps(old_value) if old_value else None,
            new_value=json.dumps(new_value) if new_value else None,
            sql_query=sql_query,
            query_duration_ms=query_duration_ms,
            rows_affected=rows_affected,
            status=status,
            error_message=error_message,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        session.add(log)
        return log

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, type='{self.event_type}', "
            f"action='{self.event_action}', status='{self.status}')>"
        )
