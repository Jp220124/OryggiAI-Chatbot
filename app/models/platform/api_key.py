"""
ApiKey Model
API key management for programmatic access
"""

import uuid
import secrets
import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, BigInteger
)
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR
from sqlalchemy.orm import relationship

from app.models.platform.base import PlatformBase

if TYPE_CHECKING:
    from app.models.platform.tenant import Tenant
    from app.models.platform.user import TenantUser


class ApiKey(PlatformBase):
    """
    ApiKey Model - API key management for programmatic access.

    Allows tenants to create API keys for integrations and
    automated access to the platform.
    """

    __tablename__ = "api_keys"

    # ==================== Ownership ====================
    tenant_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id = Column(
        UNIQUEIDENTIFIER,
        ForeignKey("tenant_users.id"),
        nullable=False
    )

    # ==================== Key Details ====================
    name = Column(NVARCHAR(255), nullable=False)
    key_prefix = Column(NVARCHAR(10), nullable=False, index=True)
    key_hash = Column(NVARCHAR(255), nullable=False)

    # ==================== Permissions (JSON) ====================
    scopes = Column(Text, nullable=True)
    # Format: ["read", "write", "admin"]

    # ==================== Limits ====================
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_day = Column(Integer, default=10000)

    # ==================== Status ====================
    is_active = Column(Boolean, default=True, index=True)
    expires_at = Column(DateTime, nullable=True)

    # ==================== Usage Tracking ====================
    last_used_at = Column(DateTime, nullable=True)
    last_used_ip = Column(NVARCHAR(50), nullable=True)
    total_requests = Column(BigInteger, default=0)

    # ==================== Revocation ====================
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(NVARCHAR(500), nullable=True)

    # ==================== Relationships ====================
    tenant: "Tenant" = relationship("Tenant")

    user: "TenantUser" = relationship(
        "TenantUser",
        back_populates="api_keys"
    )

    # ==================== Properties ====================
    @property
    def is_valid(self) -> bool:
        """Check if API key is still valid"""
        if not self.is_active:
            return False
        if self.revoked_at is not None:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    @property
    def display_key(self) -> str:
        """Get display version of key (prefix only)"""
        return f"{self.key_prefix}..."

    # ==================== Methods ====================
    def get_scopes(self) -> list:
        """Parse and return scopes as list"""
        import json
        if self.scopes:
            try:
                return json.loads(self.scopes)
            except json.JSONDecodeError:
                pass
        return []

    def has_scope(self, scope: str) -> bool:
        """Check if key has specific scope"""
        scopes = self.get_scopes()

        # 'admin' scope grants all permissions
        if "admin" in scopes:
            return True

        return scope in scopes

    def record_usage(self, ip_address: str = None) -> None:
        """Record API key usage"""
        self.last_used_at = datetime.utcnow()
        self.last_used_ip = ip_address
        # Handle NULL total_requests gracefully
        if self.total_requests is None:
            self.total_requests = 1
        else:
            self.total_requests += 1

    def revoke(self, reason: str = None) -> None:
        """Revoke this API key"""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason

    def set_scopes(self, scopes: list) -> None:
        """Set scopes from list"""
        import json
        self.scopes = json.dumps(scopes) if scopes else None

    @classmethod
    def generate_key(cls) -> tuple:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, key_prefix, key_hash)
            - full_key: The complete key to give to the user (only shown once)
            - key_prefix: First 8 characters for identification
            - key_hash: SHA-256 hash for storage and verification
        """
        # Generate a secure random key
        # Format: oai_<32 random chars>
        random_part = secrets.token_urlsafe(24)
        full_key = f"oai_{random_part}"

        # Extract prefix (first 8 chars after oai_)
        key_prefix = full_key[:12]  # oai_XXXXXXXX

        # Hash the full key for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        return full_key, key_prefix, key_hash

    @classmethod
    def verify_key(cls, full_key: str, stored_hash: str) -> bool:
        """
        Verify an API key against stored hash.

        Args:
            full_key: The full API key from request
            stored_hash: The stored hash to verify against

        Returns:
            True if key matches
        """
        computed_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return secrets.compare_digest(computed_hash, stored_hash)

    @classmethod
    def create_for_user(
        cls,
        session,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        scopes: list = None,
        expires_at: datetime = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_day: int = 10000
    ) -> tuple:
        """
        Create a new API key for a user.

        Args:
            session: SQLAlchemy session
            tenant_id: Tenant UUID
            user_id: User UUID
            name: Human-readable name for the key
            scopes: List of permission scopes
            expires_at: Optional expiration datetime
            rate_limit_per_minute: Rate limit per minute
            rate_limit_per_day: Rate limit per day

        Returns:
            Tuple of (ApiKey instance, full_key)
            Note: full_key is only available at creation time
        """
        import json

        # Generate key
        full_key, key_prefix, key_hash = cls.generate_key()

        # Create API key record
        api_key = cls(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=json.dumps(scopes) if scopes else None,
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_day=rate_limit_per_day
        )

        session.add(api_key)

        return api_key, full_key

    def __repr__(self) -> str:
        return (
            f"<ApiKey(id={self.id}, name='{self.name}', "
            f"prefix='{self.key_prefix}', active={self.is_active})>"
        )
