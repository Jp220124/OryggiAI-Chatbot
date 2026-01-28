"""
Enrollment Token Model

Database model for tracking self-service biometric enrollment tokens.
Used for QR-based employee biometric enrollment flow.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Index
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER, NVARCHAR

from app.models.platform.base import PlatformBase


class EnrollmentToken(PlatformBase):
    """
    Tracks enrollment tokens for self-service biometric enrollment.

    Flow:
    1. HR creates new employee via chatbot
    2. System generates unique token and QR code
    3. Employee scans QR at any biometric device
    4. Device validates token via API
    5. Device captures biometric and completes enrollment
    6. Token is marked as used (one-time use)
    """

    __tablename__ = "enrollment_tokens"

    # Performance indexes
    __table_args__ = (
        Index('ix_enrollment_tokens_tenant_created',
              'tenant_id', 'created_at'),
        Index('ix_enrollment_tokens_ecode_tenant',
              'employee_ecode', 'tenant_id'),
    )

    # ==================== Token Identity ====================
    token = Column(
        NVARCHAR(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique 64-char hex token (UUID4 without dashes)"
    )

    # ==================== Employee Information ====================
    employee_ecode = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Employee ECode from EmployeeMaster"
    )

    employee_name = Column(
        NVARCHAR(200),
        nullable=False,
        comment="Employee full name for display"
    )

    employee_email = Column(
        NVARCHAR(200),
        nullable=False,
        comment="Email where QR was sent"
    )

    # ==================== Biometric Configuration ====================
    biometric_type = Column(
        NVARCHAR(20),
        default="face",
        nullable=False,
        comment="Type of biometric to capture: face, finger, palm"
    )

    # ==================== Token Status ====================
    is_used = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether token has been used"
    )

    used_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp when token was used"
    )

    device_ip = Column(
        NVARCHAR(50),
        nullable=True,
        comment="IP of device that completed enrollment"
    )

    device_info = Column(
        NVARCHAR(200),
        nullable=True,
        comment="Additional device information"
    )

    # ==================== Expiry ====================
    expires_at = Column(
        DateTime,
        nullable=False,
        comment="Token expiration timestamp"
    )

    # ==================== Audit Fields ====================
    created_by_user_id = Column(
        UNIQUEIDENTIFIER,
        nullable=True,
        comment="User who initiated the enrollment"
    )

    tenant_id = Column(
        UNIQUEIDENTIFIER,
        nullable=True,
        index=True,
        comment="Tenant ID for multi-tenant support"
    )

    database_id = Column(
        UNIQUEIDENTIFIER,
        nullable=True,
        comment="Database ID for tenant database reference"
    )

    # ==================== Properties ====================
    @property
    def is_expired(self) -> bool:
        """Check if token has expired"""
        return datetime.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (not used and not expired)"""
        return not self.is_used and not self.is_expired

    @property
    def time_remaining(self) -> Optional[timedelta]:
        """Get remaining time before expiry"""
        if self.is_expired:
            return None
        return self.expires_at - datetime.now()

    # ==================== Class Methods ====================
    @classmethod
    def generate_token(cls) -> str:
        """Generate a unique 64-character hex token"""
        return uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars

    @classmethod
    def create_enrollment_token(
        cls,
        employee_ecode: int,
        employee_name: str,
        employee_email: str,
        biometric_type: str = "face",
        expires_hours: int = 24,
        created_by_user_id: uuid.UUID = None,
        tenant_id: uuid.UUID = None,
        database_id: uuid.UUID = None,
    ) -> "EnrollmentToken":
        """
        Create a new enrollment token.

        Args:
            employee_ecode: Employee code from EmployeeMaster
            employee_name: Employee full name
            employee_email: Email to send QR
            biometric_type: Type of biometric (face, finger, palm)
            expires_hours: Hours until token expires (default 24)
            created_by_user_id: User who initiated enrollment
            tenant_id: Tenant ID
            database_id: Database ID

        Returns:
            New EnrollmentToken instance
        """
        return cls(
            token=cls.generate_token(),
            employee_ecode=employee_ecode,
            employee_name=employee_name,
            employee_email=employee_email,
            biometric_type=biometric_type,
            expires_at=datetime.now() + timedelta(hours=expires_hours),
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            database_id=database_id,
        )

    # ==================== Instance Methods ====================
    def mark_as_used(self, device_ip: str = None, device_info: str = None) -> None:
        """Mark token as used after successful enrollment"""
        self.is_used = True
        self.used_at = datetime.now()
        self.device_ip = device_ip
        self.device_info = device_info

    def to_device_response(self) -> dict:
        """Return minimal data for device API response"""
        return {
            "ecode": self.employee_ecode,
            "name": self.employee_name,
            "biometric_type": self.biometric_type,
        }

    def __repr__(self) -> str:
        status = "USED" if self.is_used else ("EXPIRED" if self.is_expired else "VALID")
        return (
            f"<EnrollmentToken(ecode={self.employee_ecode}, "
            f"name='{self.employee_name}', status={status})>"
        )
