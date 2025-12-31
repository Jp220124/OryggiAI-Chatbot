"""
User Models
TenantUser - Users belonging to a tenant
RefreshToken - JWT refresh token storage
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.orm import relationship

from app.models.platform.base import PlatformBase

if TYPE_CHECKING:
    from app.models.platform.tenant import Tenant
    from app.models.platform.database import TenantDatabase
    from app.models.platform.metrics import AuditLog
    from app.models.platform.api_key import ApiKey


class UserRole(str, Enum):
    """User role levels"""
    OWNER = "owner"      # Full control, can delete tenant
    ADMIN = "admin"      # Full control except tenant deletion
    MANAGER = "manager"  # Can manage users and databases
    USER = "user"        # Standard user access
    VIEWER = "viewer"    # Read-only access


class TenantUser(PlatformBase):
    """
    TenantUser Model - Users belonging to a specific tenant.

    Each user is scoped to a single tenant and has role-based
    permissions within that tenant's context.
    """

    __tablename__ = "tenant_users"

    # ==================== Tenant Relationship ====================
    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ==================== Identity ====================
    email = Column(NVARCHAR(255), nullable=False, index=True)
    password_hash = Column(NVARCHAR(255), nullable=False)

    # ==================== Profile ====================
    first_name = Column(NVARCHAR(100), nullable=True)
    last_name = Column(NVARCHAR(100), nullable=True)
    display_name = Column(NVARCHAR(200), nullable=True)
    avatar_url = Column(NVARCHAR(500), nullable=True)
    phone = Column(NVARCHAR(50), nullable=True)

    # ==================== Role & Permissions ====================
    role = Column(
        NVARCHAR(50),
        default=UserRole.USER.value,
        index=True
    )
    permissions = Column(Text, nullable=True)  # JSON array

    # ==================== Status ====================
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)

    # ==================== Authentication ====================
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(NVARCHAR(50), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # ==================== Password Reset ====================
    password_reset_token = Column(NVARCHAR(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)

    # ==================== Two-Factor Auth ====================
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(NVARCHAR(255), nullable=True)

    # ==================== User Preferences (JSON) ====================
    preferences = Column(Text, nullable=True)

    # ==================== Soft Delete ====================
    deleted_at = Column(DateTime, nullable=True)

    # ==================== Relationships ====================
    tenant: "Tenant" = relationship(
        "Tenant",
        back_populates="users"
    )

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    api_keys = relationship(
        "ApiKey",
        back_populates="user",
        lazy="dynamic"
    )

    audit_logs = relationship(
        "AuditLog",
        back_populates="user",
        lazy="dynamic"
    )

    # Databases created by this user
    created_databases = relationship(
        "TenantDatabase",
        back_populates="created_by_user",
        lazy="dynamic"
    )

    # ==================== Constraints ====================
    __table_args__ = (
        CheckConstraint(
            role.in_([r.value for r in UserRole]),
            name="CHK_tenant_users_role"
        ),
    )

    # ==================== Properties ====================
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.email.split("@")[0]

    @property
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    @property
    def can_login(self) -> bool:
        """Check if user can login"""
        return (
            self.is_active and
            not self.is_locked and
            self.deleted_at is None
        )

    # ==================== Methods ====================
    def record_login(self, ip_address: str = None) -> None:
        """Record successful login"""
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 30) -> None:
        """Record failed login attempt"""
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    def verify_email(self) -> None:
        """Mark email as verified"""
        self.is_verified = True
        self.email_verified_at = datetime.utcnow()

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        # Owners and admins have all permissions
        if self.role in [UserRole.OWNER.value, UserRole.ADMIN.value]:
            return True

        # Check custom permissions
        if self.permissions:
            import json
            try:
                perms = json.loads(self.permissions)
                return permission in perms
            except json.JSONDecodeError:
                pass

        # Default role-based permissions
        role_permissions = {
            UserRole.MANAGER.value: ["read", "write", "manage_users"],
            UserRole.USER.value: ["read", "write"],
            UserRole.VIEWER.value: ["read"]
        }

        return permission in role_permissions.get(self.role, [])

    def is_owner(self) -> bool:
        """Check if user is tenant owner"""
        return self.role == UserRole.OWNER.value

    def is_admin(self) -> bool:
        """Check if user is admin or owner"""
        return self.role in [UserRole.OWNER.value, UserRole.ADMIN.value]

    def soft_delete(self) -> None:
        """Soft delete user"""
        self.deleted_at = datetime.utcnow()
        self.is_active = False

    def __repr__(self) -> str:
        return f"<TenantUser(id={self.id}, email='{self.email}', role='{self.role}')>"


class RefreshToken(PlatformBase):
    """
    RefreshToken Model - Stores JWT refresh tokens for session management.

    Allows tracking and revocation of refresh tokens.
    """

    __tablename__ = "refresh_tokens"

    # ==================== User Relationship ====================
    user_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ==================== Token Details ====================
    token_hash = Column(NVARCHAR(255), nullable=False, index=True)
    device_info = Column(NVARCHAR(500), nullable=True)
    ip_address = Column(NVARCHAR(50), nullable=True)

    # ==================== Validity ====================
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)

    # ==================== Relationships ====================
    user: "TenantUser" = relationship(
        "TenantUser",
        back_populates="refresh_tokens"
    )

    # ==================== Properties ====================
    @property
    def is_valid(self) -> bool:
        """Check if token is still valid"""
        return (
            not self.is_revoked and
            datetime.utcnow() < self.expires_at
        )

    # ==================== Methods ====================
    def revoke(self) -> None:
        """Revoke this refresh token"""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, is_valid={self.is_valid})>"
