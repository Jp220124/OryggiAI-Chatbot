"""
Authentication Schemas
Pydantic models for authentication requests and responses
"""

import re
import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, EmailStr


# =============================================================================
# Registration Schemas
# =============================================================================

class TenantRegistrationRequest(BaseModel):
    """Request schema for registering a new tenant (company/organization)"""

    # Tenant info
    tenant_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Company or organization name"
    )
    tenant_slug: Optional[str] = Field(
        None,
        max_length=100,
        description="URL-friendly identifier (auto-generated if not provided)"
    )

    # Owner info
    email: EmailStr = Field(..., description="Owner's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters)"
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Owner's full name"
    )

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

    @field_validator('tenant_slug')
    @classmethod
    def validate_slug(cls, v):
        """Ensure slug is URL-friendly"""
        if v is not None:
            if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', v):
                raise ValueError(
                    'Slug must contain only lowercase letters, numbers, and hyphens'
                )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_name": "Acme Corporation",
                "tenant_slug": "acme-corp",
                "email": "admin@acme.com",
                "password": "SecurePass123!",
                "full_name": "John Smith"
            }
        }


class UserRegistrationRequest(BaseModel):
    """Request schema for registering a new user within a tenant"""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters)"
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="User's full name"
    )
    role: str = Field(
        default="user",
        description="User role (admin, manager, user, viewer)"
    )

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        """Ensure role is valid"""
        valid_roles = ['admin', 'manager', 'user', 'viewer']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@acme.com",
                "password": "SecurePass123!",
                "full_name": "Jane Doe",
                "role": "user"
            }
        }


class RegistrationResponse(BaseModel):
    """Response schema for successful registration"""

    message: str
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Registration successful",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "admin@acme.com",
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer"
            }
        }


# =============================================================================
# Login Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Request schema for user login"""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@acme.com",
                "password": "SecurePass123!"
            }
        }


class TokenResponse(BaseModel):
    """Response schema for token-based authentication"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class LoginResponse(BaseModel):
    """Response schema for successful login"""

    message: str
    user: "UserResponse"
    tokens: TokenResponse

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Login successful",
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "admin@acme.com",
                    "full_name": "John Smith",
                    "role": "owner",
                    "tenant_id": "123e4567-e89b-12d3-a456-426614174000"
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIs...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                    "token_type": "bearer",
                    "expires_in": 1800
                }
            }
        }


# =============================================================================
# Token Refresh Schemas
# =============================================================================

class RefreshTokenRequest(BaseModel):
    """Request schema for refreshing access token"""

    refresh_token: str = Field(..., description="JWT refresh token")

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
            }
        }


# =============================================================================
# User Schemas
# =============================================================================

class UserResponse(BaseModel):
    """Response schema for user information"""

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    tenant_id: uuid.UUID
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "admin@acme.com",
                "full_name": "John Smith",
                "role": "owner",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "last_login": "2024-01-20T14:45:00Z"
            }
        }


class UserUpdateRequest(BaseModel):
    """Request schema for updating user profile"""

    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "John Smith Updated",
                "email": "newemail@acme.com"
            }
        }


# =============================================================================
# Password Schemas
# =============================================================================

class PasswordChangeRequest(BaseModel):
    """Request schema for changing password (when logged in)"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "OldSecurePass123!",
                "new_password": "NewSecurePass456!"
            }
        }


class PasswordResetRequest(BaseModel):
    """Request schema for initiating password reset"""

    email: EmailStr = Field(..., description="Email address for password reset")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@acme.com"
            }
        }


class PasswordResetConfirm(BaseModel):
    """Request schema for confirming password reset"""

    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        """Ensure password meets minimum requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIs...",
                "new_password": "NewSecurePass789!"
            }
        }


# Update forward references
LoginResponse.model_rebuild()
