"""
Tenant Management Schemas
Pydantic models for tenant and database management
"""

import re
import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, field_validator, EmailStr


# =============================================================================
# Enums
# =============================================================================

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


class TenantStatus(str, Enum):
    """Tenant status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"


# =============================================================================
# Tenant Schemas
# =============================================================================

class TenantBase(BaseModel):
    """Base tenant fields"""
    name: str = Field(..., min_length=2, max_length=255)
    organization_type: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=100)
    timezone: str = Field(default="Asia/Kolkata", max_length=100)


class TenantUpdate(BaseModel):
    """Schema for updating tenant information"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    organization_type: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, max_length=20)


class TenantResponse(BaseModel):
    """Response schema for tenant details"""
    id: uuid.UUID
    name: str
    slug: str
    organization_type: Optional[str]
    industry: Optional[str]
    company_size: Optional[str]
    admin_email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    country: Optional[str]
    timezone: str
    status: str
    plan: str
    trial_ends_at: Optional[datetime]
    max_users: int
    max_databases: int
    max_queries_per_day: int
    max_storage_mb: int
    logo_url: Optional[str]
    primary_color: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantSummary(BaseModel):
    """Brief tenant summary"""
    id: uuid.UUID
    name: str
    slug: str
    status: str
    plan: str
    user_count: int = 0
    database_count: int = 0

    model_config = {"from_attributes": True}


# =============================================================================
# Tenant Database Schemas
# =============================================================================

class DatabaseConnectionBase(BaseModel):
    """Base database connection fields"""
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    db_type: DatabaseType
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., gt=0, lt=65536)
    database_name: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)

    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host format"""
        # Allow localhost, IP addresses, and domain names
        if not v or len(v.strip()) == 0:
            raise ValueError('Host cannot be empty')
        return v.strip()


class DatabaseConnectionCreate(DatabaseConnectionBase):
    """Schema for creating a new database connection"""
    password: str = Field(..., min_length=1, max_length=500)
    use_ssl: bool = Field(default=False)
    connection_timeout: int = Field(default=30, ge=5, le=300)
    query_timeout: int = Field(default=60, ge=5, le=600)


class DatabaseConnectionUpdate(BaseModel):
    """Schema for updating database connection"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, gt=0, lt=65536)
    database_name: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=1, max_length=500)
    use_ssl: Optional[bool] = None
    connection_timeout: Optional[int] = Field(None, ge=5, le=300)
    query_timeout: Optional[int] = Field(None, ge=5, le=600)


class DatabaseConnectionResponse(BaseModel):
    """Response schema for database connection"""
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    use_ssl: bool
    connection_timeout: int
    query_timeout: int
    is_active: bool
    schema_analyzed: bool
    analysis_status: str
    analysis_error: Optional[str]
    last_analysis_at: Optional[datetime]
    detected_organization_type: Optional[str]
    table_count: int
    view_count: int
    auto_sync_enabled: bool
    sync_interval_hours: int
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatabaseConnectionSummary(BaseModel):
    """Brief database connection summary"""
    id: uuid.UUID
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    is_active: bool
    schema_analyzed: bool
    analysis_status: str
    table_count: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DatabaseTestResult(BaseModel):
    """Result of database connection test"""
    success: bool
    message: str
    connection_time_ms: Optional[float] = None
    server_version: Optional[str] = None


class SchemaAnalysisResponse(BaseModel):
    """Response for schema analysis"""
    database_id: uuid.UUID
    status: str
    message: str
    table_count: Optional[int] = None
    view_count: Optional[int] = None
    detected_organization_type: Optional[str] = None
    detected_modules: Optional[List[str]] = None


# =============================================================================
# User Management within Tenant
# =============================================================================

class TenantUserCreate(BaseModel):
    """Schema for creating a user within tenant"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(default="user")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role"""
        valid_roles = ['admin', 'manager', 'user', 'viewer']
        if v.lower() not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v.lower()


class TenantUserUpdate(BaseModel):
    """Schema for updating a user within tenant"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate role if provided"""
        if v is None:
            return v
        valid_roles = ['admin', 'manager', 'user', 'viewer']
        if v.lower() not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v.lower()


class TenantUserResponse(BaseModel):
    """Response schema for tenant user"""
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    phone: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantUserSummary(BaseModel):
    """Brief user summary"""
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# =============================================================================
# Usage and Statistics
# =============================================================================

class TenantUsageStats(BaseModel):
    """Tenant usage statistics"""
    tenant_id: uuid.UUID
    user_count: int
    active_user_count: int
    database_count: int
    active_database_count: int
    total_tables: int
    total_views: int
    queries_today: int
    queries_this_month: int
    storage_used_mb: float


class DatabaseUsageStats(BaseModel):
    """Database usage statistics"""
    database_id: uuid.UUID
    table_count: int
    view_count: int
    queries_today: int
    queries_this_month: int
    avg_query_time_ms: float
    last_query_at: Optional[datetime]
