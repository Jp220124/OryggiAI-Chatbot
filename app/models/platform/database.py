"""
TenantDatabase Model
Represents database connections configured by tenants
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import quote_plus

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, CheckConstraint, Index
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.orm import relationship

from app.models.platform.base import PlatformBase

if TYPE_CHECKING:
    from app.models.platform.tenant import Tenant
    from app.models.platform.user import TenantUser
    from app.models.platform.schema import SchemaCache, FewShotExample


class DatabaseType(str, Enum):
    """Supported database types"""
    MSSQL = "mssql"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    ORACLE = "oracle"


class AnalysisStatus(str, Enum):
    """Schema analysis status"""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConnectionMode(str, Enum):
    """Database connection mode for gateway support"""
    AUTO = "auto"  # Try direct first, fallback to gateway if connected
    GATEWAY_ONLY = "gateway_only"  # Only use gateway (for firewalled databases)
    DIRECT_ONLY = "direct_only"  # Only use direct connection (legacy)


class TenantDatabase(PlatformBase):
    """
    TenantDatabase Model - Database connections for each tenant.

    Stores encrypted connection credentials and tracks schema
    analysis status for auto-onboarding.
    """

    __tablename__ = "tenant_databases"

    # PERFORMANCE: Composite indexes for admin dashboard queries
    __table_args__ = (
        # Index for admin service get_all_tenants_with_status()
        # Used in: checking gateway connections per tenant
        Index('ix_tenant_databases_tenant_gateway_active',
              'tenant_id', 'gateway_connected', 'is_active'),
    )

    # ==================== Tenant Relationship ====================
    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="NO ACTION"),
        nullable=False,
        index=True
    )

    # ==================== Database Identity ====================
    name = Column(NVARCHAR(255), nullable=False)
    description = Column(NVARCHAR(500), nullable=True)

    # ==================== Connection Details ====================
    db_type = Column(NVARCHAR(50), nullable=False)
    host = Column(NVARCHAR(255), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(NVARCHAR(255), nullable=False)
    username = Column(NVARCHAR(255), nullable=False)
    password_encrypted = Column(Text, nullable=False)  # Fernet encrypted

    # ==================== Connection Options ====================
    use_ssl = Column(Boolean, default=False)
    ssl_certificate = Column(Text, nullable=True)
    connection_timeout = Column(Integer, default=30)
    query_timeout = Column(Integer, default=60)

    # ==================== Analysis Status ====================
    is_active = Column(Boolean, default=True, index=True)
    schema_analyzed = Column(Boolean, default=False)
    analysis_status = Column(
        NVARCHAR(50),
        default=AnalysisStatus.PENDING.value,
        index=True
    )
    analysis_error = Column(Text, nullable=True)
    last_analysis_at = Column(DateTime, nullable=True)

    # ==================== Auto-Detected Information ====================
    detected_organization_type = Column(NVARCHAR(100), nullable=True)
    detected_modules = Column(Text, nullable=True)  # JSON array
    table_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)

    # ==================== Sync Settings ====================
    auto_sync_enabled = Column(Boolean, default=False)
    sync_interval_hours = Column(Integer, default=24)
    last_sync_at = Column(DateTime, nullable=True)

    # ==================== ChromaDB References ====================
    schema_collection_id = Column(NVARCHAR(255), nullable=True)
    fewshot_collection_id = Column(NVARCHAR(255), nullable=True)

    # ==================== Gateway Configuration ====================
    connection_mode = Column(
        NVARCHAR(50),
        default=ConnectionMode.AUTO.value,
        nullable=False
    )
    gateway_connected = Column(Boolean, default=False)
    gateway_connected_at = Column(DateTime, nullable=True)
    gateway_api_key_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("api_keys.id", ondelete="NO ACTION"),
        nullable=True
    )

    # ==================== Created By ====================
    created_by = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_users.id"),
        nullable=True
    )

    # ==================== Relationships ====================
    tenant: "Tenant" = relationship(
        "Tenant",
        back_populates="databases"
    )

    created_by_user: "TenantUser" = relationship(
        "TenantUser",
        back_populates="created_databases"
    )

    schema_cache: List["SchemaCache"] = relationship(
        "SchemaCache",
        back_populates="tenant_database",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    few_shot_examples: List["FewShotExample"] = relationship(
        "FewShotExample",
        back_populates="tenant_database",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # ==================== Constraints ====================
    __table_args__ = (
        CheckConstraint(
            db_type.in_([dt.value for dt in DatabaseType]),
            name="CHK_tenant_databases_db_type"
        ),
        CheckConstraint(
            analysis_status.in_([s.value for s in AnalysisStatus]),
            name="CHK_tenant_databases_status"
        ),
    )

    # ==================== Properties ====================
    @property
    def is_ready(self) -> bool:
        """Check if database is ready for queries"""
        return (
            self.is_active and
            self.schema_analyzed and
            self.analysis_status == AnalysisStatus.COMPLETED.value
        )

    @property
    def connection_display(self) -> str:
        """Get display string for connection (no password)"""
        return f"{self.db_type}://{self.username}@{self.host}:{self.port}/{self.database_name}"

    # ==================== Methods ====================
    def get_connection_string(self, decrypted_password: str) -> str:
        """
        Build SQLAlchemy connection string.

        Args:
            decrypted_password: Decrypted database password

        Returns:
            SQLAlchemy connection URL
        """
        db_drivers = {
            DatabaseType.MSSQL.value: "mssql+pyodbc",
            DatabaseType.POSTGRESQL.value: "postgresql+psycopg2",
            DatabaseType.MYSQL.value: "mysql+pymysql",
            DatabaseType.SQLITE.value: "sqlite",
            DatabaseType.ORACLE.value: "oracle+cx_oracle"
        }

        driver = db_drivers.get(self.db_type, "mssql+pyodbc")

        if self.db_type == DatabaseType.SQLITE.value:
            return f"{driver}:///{self.database_name}"

        # URL-encode username and password to handle special characters like @
        encoded_username = quote_plus(self.username)
        encoded_password = quote_plus(decrypted_password)

        if self.db_type == DatabaseType.MSSQL.value:
            # SQL Server specific connection string
            return (
                f"{driver}://{encoded_username}:{encoded_password}"
                f"@{self.host}:{self.port}/{self.database_name}"
                f"?driver=ODBC+Driver+17+for+SQL+Server"
            )

        return (
            f"{driver}://{encoded_username}:{encoded_password}"
            f"@{self.host}:{self.port}/{self.database_name}"
        )

    def start_analysis(self) -> None:
        """Mark analysis as started"""
        self.analysis_status = AnalysisStatus.ANALYZING.value
        self.analysis_error = None

    def complete_analysis(
        self,
        table_count: int,
        view_count: int,
        organization_type: str = None,
        modules: list = None
    ) -> None:
        """Mark analysis as completed"""
        import json

        self.analysis_status = AnalysisStatus.COMPLETED.value
        self.schema_analyzed = True
        self.last_analysis_at = datetime.utcnow()
        self.table_count = table_count
        self.view_count = view_count
        self.detected_organization_type = organization_type

        if modules:
            self.detected_modules = json.dumps(modules)

    def fail_analysis(self, error: str) -> None:
        """Mark analysis as failed"""
        self.analysis_status = AnalysisStatus.FAILED.value
        self.analysis_error = error
        self.schema_analyzed = False

    def deactivate(self) -> None:
        """Deactivate database connection"""
        self.is_active = False

    def activate(self) -> None:
        """Activate database connection"""
        self.is_active = True

    def __repr__(self) -> str:
        return (
            f"<TenantDatabase(id={self.id}, name='{self.name}', "
            f"type='{self.db_type}', status='{self.analysis_status}')>"
        )
