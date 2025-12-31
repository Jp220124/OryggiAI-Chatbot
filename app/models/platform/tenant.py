"""
Tenant Model
Represents an organization/company using the platform
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, CheckConstraint
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.orm import relationship

from app.models.platform.base import PlatformBase

if TYPE_CHECKING:
    from app.models.platform.user import TenantUser
    from app.models.platform.database import TenantDatabase
    from app.models.platform.metrics import UsageMetrics, AuditLog


class TenantStatus(str, Enum):
    """Tenant account status"""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class TenantPlan(str, Enum):
    """Subscription plan levels"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Tenant(PlatformBase):
    """
    Tenant Model - Represents an organization using the platform.

    Each tenant is completely isolated with their own:
    - Users
    - Database connections
    - Schema cache
    - Few-shot examples
    - Usage metrics
    """

    __tablename__ = "tenants"

    # ==================== Identity ====================
    name = Column(NVARCHAR(255), nullable=False)
    slug = Column(NVARCHAR(100), nullable=False, unique=True, index=True)

    # ==================== Organization Details ====================
    organization_type = Column(NVARCHAR(100), nullable=True)
    industry = Column(NVARCHAR(100), nullable=True)
    company_size = Column(NVARCHAR(50), nullable=True)

    # ==================== Contact ====================
    admin_email = Column(NVARCHAR(255), nullable=False, index=True)
    phone = Column(NVARCHAR(50), nullable=True)
    address = Column(NVARCHAR(500), nullable=True)
    country = Column(NVARCHAR(100), nullable=True)
    timezone = Column(NVARCHAR(50), default="Asia/Kolkata")

    # ==================== Subscription ====================
    status = Column(
        NVARCHAR(50),
        default=TenantStatus.PENDING.value,
        index=True
    )
    plan = Column(
        NVARCHAR(50),
        default=TenantPlan.FREE.value
    )
    trial_ends_at = Column(DateTime, nullable=True)

    # ==================== Feature Flags (JSON) ====================
    features = Column(Text, nullable=True)  # JSON string

    # ==================== Limits ====================
    max_users = Column(Integer, default=5)
    max_databases = Column(Integer, default=1)
    max_queries_per_day = Column(Integer, default=100)
    max_storage_mb = Column(Integer, default=500)

    # ==================== Branding ====================
    logo_url = Column(NVARCHAR(500), nullable=True)
    primary_color = Column(NVARCHAR(20), nullable=True)

    # ==================== Soft Delete ====================
    deleted_at = Column(DateTime, nullable=True)

    # ==================== Relationships ====================
    users: List["TenantUser"] = relationship(
        "TenantUser",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    databases: List["TenantDatabase"] = relationship(
        "TenantDatabase",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    usage_metrics: List["UsageMetrics"] = relationship(
        "UsageMetrics",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    audit_logs: List["AuditLog"] = relationship(
        "AuditLog",
        back_populates="tenant",
        lazy="dynamic"
    )

    # ==================== Constraints ====================
    __table_args__ = (
        CheckConstraint(
            status.in_([s.value for s in TenantStatus]),
            name="CHK_tenants_status"
        ),
        CheckConstraint(
            plan.in_([p.value for p in TenantPlan]),
            name="CHK_tenants_plan"
        ),
    )

    # ==================== Properties ====================
    @property
    def is_active(self) -> bool:
        """Check if tenant is active"""
        return self.status == TenantStatus.ACTIVE.value and self.deleted_at is None

    @property
    def is_trial_expired(self) -> bool:
        """Check if trial period has expired"""
        if self.trial_ends_at is None:
            return False
        return datetime.utcnow() > self.trial_ends_at

    @property
    def user_count(self) -> int:
        """Get count of active users"""
        return self.users.filter_by(is_active=True, deleted_at=None).count()

    @property
    def database_count(self) -> int:
        """Get count of active databases"""
        return self.databases.filter_by(is_active=True).count()

    # ==================== Methods ====================
    def can_add_user(self) -> bool:
        """Check if tenant can add more users"""
        return self.user_count < self.max_users

    def can_add_database(self) -> bool:
        """Check if tenant can add more databases"""
        return self.database_count < self.max_databases

    def activate(self) -> None:
        """Activate tenant account"""
        self.status = TenantStatus.ACTIVE.value

    def suspend(self) -> None:
        """Suspend tenant account"""
        self.status = TenantStatus.SUSPENDED.value

    def cancel(self) -> None:
        """Cancel tenant account"""
        self.status = TenantStatus.CANCELLED.value

    def soft_delete(self) -> None:
        """Soft delete tenant"""
        self.deleted_at = datetime.utcnow()
        self.status = TenantStatus.CANCELLED.value

    def get_plan_limits(self) -> dict:
        """Get limits based on current plan"""
        plan_limits = {
            TenantPlan.FREE.value: {
                "max_users": 5,
                "max_databases": 1,
                "max_queries_per_day": 100,
                "max_storage_mb": 500,
                "features": ["sql_agent", "basic_reports"]
            },
            TenantPlan.STARTER.value: {
                "max_users": 20,
                "max_databases": 3,
                "max_queries_per_day": 1000,
                "max_storage_mb": 2000,
                "features": ["sql_agent", "reports", "email"]
            },
            TenantPlan.PROFESSIONAL.value: {
                "max_users": 100,
                "max_databases": 10,
                "max_queries_per_day": 10000,
                "max_storage_mb": 10000,
                "features": ["sql_agent", "reports", "email", "api_access", "custom_branding"]
            },
            TenantPlan.ENTERPRISE.value: {
                "max_users": -1,  # Unlimited
                "max_databases": -1,
                "max_queries_per_day": -1,
                "max_storage_mb": -1,
                "features": ["all"]
            }
        }
        return plan_limits.get(self.plan, plan_limits[TenantPlan.FREE.value])

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}', slug='{self.slug}', status='{self.status}')>"
