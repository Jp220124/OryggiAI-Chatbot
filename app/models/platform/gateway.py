"""
Gateway Models

Database models for tracking gateway sessions and query logs.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Float, Index
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.orm import relationship

from app.models.platform.base import PlatformBase

if TYPE_CHECKING:
    from app.models.platform.tenant import Tenant
    from app.models.platform.database import TenantDatabase


class SessionStatus(str, Enum):
    """Gateway session status"""
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    TIMEOUT = "timeout"
    ERROR = "error"


class QueryStatus(str, Enum):
    """Gateway query execution status"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class GatewaySession(PlatformBase):
    """
    Tracks gateway agent connection sessions.

    Records connection history, agent information, and session metrics.
    """

    __tablename__ = "gateway_sessions"

    # ==================== Session Identity ====================
    session_id = Column(NVARCHAR(100), unique=True, index=True, nullable=False)

    # ==================== Relationships ====================
    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="NO ACTION"),
        nullable=False,
        index=True
    )

    database_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_databases.id", ondelete="NO ACTION"),
        nullable=False,
        index=True
    )

    api_key_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("api_keys.id", ondelete="NO ACTION"),
        nullable=True
    )

    # ==================== Agent Information ====================
    agent_version = Column(NVARCHAR(50), nullable=True)
    agent_hostname = Column(NVARCHAR(255), nullable=True)
    agent_os = Column(NVARCHAR(100), nullable=True)
    agent_ip = Column(NVARCHAR(50), nullable=True)

    # ==================== Session Timing ====================
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    disconnected_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)

    # ==================== Session Status ====================
    status = Column(
        NVARCHAR(50),
        default=SessionStatus.ACTIVE.value,
        index=True
    )
    disconnect_reason = Column(NVARCHAR(500), nullable=True)

    # ==================== Session Metrics ====================
    queries_executed = Column(Integer, default=0)
    total_query_time_ms = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    bytes_transferred = Column(Integer, default=0)

    # ==================== Relationships ====================
    tenant: "Tenant" = relationship("Tenant", backref="gateway_sessions")
    database: "TenantDatabase" = relationship("TenantDatabase", backref="gateway_sessions")
    query_logs: list["GatewayQueryLog"] = relationship(
        "GatewayQueryLog",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    # ==================== Properties ====================
    @property
    def duration_seconds(self) -> Optional[int]:
        """Get session duration in seconds"""
        if not self.connected_at:
            return None
        end_time = self.disconnected_at or datetime.utcnow()
        return int((end_time - self.connected_at).total_seconds())

    @property
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status == SessionStatus.ACTIVE.value

    # ==================== Methods ====================
    def record_heartbeat(self) -> None:
        """Update last heartbeat timestamp"""
        self.last_heartbeat_at = datetime.utcnow()

    def record_query(self, execution_time_ms: int, bytes_count: int = 0) -> None:
        """Record a successful query"""
        self.queries_executed += 1
        self.total_query_time_ms += execution_time_ms
        self.bytes_transferred += bytes_count

    def record_error(self) -> None:
        """Record a query error"""
        self.errors_count += 1

    def disconnect(self, reason: str = "normal") -> None:
        """Mark session as disconnected"""
        self.status = SessionStatus.DISCONNECTED.value
        self.disconnected_at = datetime.utcnow()
        self.disconnect_reason = reason

    def timeout(self) -> None:
        """Mark session as timed out"""
        self.status = SessionStatus.TIMEOUT.value
        self.disconnected_at = datetime.utcnow()
        self.disconnect_reason = "heartbeat_timeout"

    def __repr__(self) -> str:
        return (
            f"<GatewaySession(id={self.session_id}, "
            f"status='{self.status}', queries={self.queries_executed})>"
        )


class GatewayQueryLog(PlatformBase):
    """
    Audit log for queries executed through the gateway.

    Provides detailed tracking of each query for debugging and compliance.
    Logs both the natural language question AND the generated SQL query.
    """

    __tablename__ = "gateway_query_logs"

    # PERFORMANCE: Composite indexes for admin dashboard queries
    __table_args__ = (
        # Index for admin service get_all_tenants_with_status()
        # Used in: stats aggregation by tenant with status filtering
        Index('ix_gateway_query_logs_tenant_status_requested',
              'tenant_id', 'status', 'requested_at'),

        # Index for filtering by tenant and date range
        # Used in: get_tenant_query_history() with date filtering
        Index('ix_gateway_query_logs_tenant_requested',
              'tenant_id', 'requested_at'),
    )

    # ==================== Request Identity ====================
    request_id = Column(NVARCHAR(100), unique=True, index=True, nullable=False)

    # ==================== Relationships ====================
    session_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("gateway_sessions.id", ondelete="CASCADE"),
        nullable=True,  # Made nullable for direct API queries without gateway
        index=True
    )

    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="NO ACTION"),
        nullable=False,
        index=True
    )

    database_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_databases.id", ondelete="NO ACTION"),
        nullable=False,
        index=True
    )

    user_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_users.id", ondelete="NO ACTION"),
        nullable=True,
        index=True
    )

    conversation_id = Column(NVARCHAR(100), nullable=True, index=True)

    # ==================== Question & Query Details ====================
    # NEW: The original natural language question from the user
    natural_language_question = Column(Text, nullable=True)

    # The SQL query generated by AI
    sql_query = Column(Text, nullable=False)
    query_hash = Column(NVARCHAR(64), nullable=True, index=True)  # SHA256 of query

    # ==================== AI Generation Details ====================
    llm_model = Column(NVARCHAR(100), nullable=True)  # Which AI model generated this
    tokens_used = Column(Integer, nullable=True)  # Token consumption
    generation_time_ms = Column(Integer, nullable=True)  # Time to generate SQL

    # ==================== Execution Results ====================
    status = Column(NVARCHAR(50), default=QueryStatus.SUCCESS.value)
    row_count = Column(Integer, default=0)
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(NVARCHAR(50), nullable=True)

    # ==================== Timing ====================
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # ==================== Relationships ====================
    session: GatewaySession = relationship("GatewaySession", back_populates="query_logs")
    tenant: "Tenant" = relationship("Tenant", backref="gateway_query_logs")

    # ==================== Properties ====================
    @property
    def latency_ms(self) -> Optional[int]:
        """Total latency from request to completion"""
        if not self.completed_at or not self.requested_at:
            return None
        return int((self.completed_at - self.requested_at).total_seconds() * 1000)

    # ==================== Class Methods ====================
    @classmethod
    def create_log(
        cls,
        request_id: str,
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
    ) -> "GatewayQueryLog":
        """Create a new query log entry"""
        import hashlib

        return cls(
            request_id=request_id,
            session_id=session_id,
            tenant_id=tenant_id,
            database_id=database_id,
            natural_language_question=natural_language_question,
            sql_query=sql_query,
            query_hash=hashlib.sha256(sql_query.encode()).hexdigest(),
            user_id=user_id,
            conversation_id=conversation_id,
            llm_model=llm_model,
            tokens_used=tokens_used,
            generation_time_ms=generation_time_ms,
            requested_at=datetime.utcnow(),
        )

    def complete_success(
        self,
        row_count: int,
        execution_time_ms: int,
    ) -> None:
        """Mark query as successfully completed"""
        self.status = QueryStatus.SUCCESS.value
        self.row_count = row_count
        self.execution_time_ms = execution_time_ms
        self.completed_at = datetime.utcnow()

    def complete_error(
        self,
        error_message: str,
        error_code: str = None,
    ) -> None:
        """Mark query as failed"""
        self.status = QueryStatus.ERROR.value
        self.error_message = error_message
        self.error_code = error_code
        self.completed_at = datetime.utcnow()

    def complete_timeout(self) -> None:
        """Mark query as timed out"""
        self.status = QueryStatus.TIMEOUT.value
        self.error_message = "Query execution timed out"
        self.completed_at = datetime.utcnow()

    def __repr__(self) -> str:
        question_preview = self.natural_language_question[:50] if self.natural_language_question else 'N/A'
        return (
            f"<GatewayQueryLog(request_id='{self.request_id}', "
            f"question='{question_preview}...', "
            f"status='{self.status}', rows={self.row_count})>"
        )
