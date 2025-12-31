"""
Pydantic Schemas Module
Request and response models for API endpoints
"""

from app.schemas.auth import (
    # Registration
    TenantRegistrationRequest,
    UserRegistrationRequest,
    RegistrationResponse,

    # Login
    LoginRequest,
    LoginResponse,
    TokenResponse,

    # Token refresh
    RefreshTokenRequest,

    # User info
    UserResponse,
    UserUpdateRequest,

    # Password
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChangeRequest
)

from app.schemas.tenant import (
    # Tenant
    TenantResponse,
    TenantUpdate,
    TenantUsageStats,

    # Database connections
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseConnectionResponse,
    DatabaseConnectionSummary,
    DatabaseTestResult,

    # User management within tenant
    TenantUserCreate,
    TenantUserUpdate,
    TenantUserResponse,
    TenantUserSummary
)

__all__ = [
    # Auth - Registration
    "TenantRegistrationRequest",
    "UserRegistrationRequest",
    "RegistrationResponse",

    # Auth - Login
    "LoginRequest",
    "LoginResponse",
    "TokenResponse",

    # Auth - Token refresh
    "RefreshTokenRequest",

    # Auth - User info
    "UserResponse",
    "UserUpdateRequest",

    # Auth - Password
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "PasswordChangeRequest",

    # Tenant
    "TenantResponse",
    "TenantUpdate",
    "TenantUsageStats",

    # Database connections
    "DatabaseConnectionCreate",
    "DatabaseConnectionUpdate",
    "DatabaseConnectionResponse",
    "DatabaseConnectionSummary",
    "DatabaseTestResult",

    # User management within tenant
    "TenantUserCreate",
    "TenantUserUpdate",
    "TenantUserResponse",
    "TenantUserSummary"
]
