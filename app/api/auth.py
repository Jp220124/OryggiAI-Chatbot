"""
Authentication API Routes
Endpoints for user registration, login, logout, and token management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from app.database.platform_connection import get_platform_db
from app.schemas.auth import (
    TenantRegistrationRequest,
    UserRegistrationRequest,
    RegistrationResponse,
    LoginRequest,
    LoginResponse,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    UserUpdateRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm
)
from app.services.auth_service import (
    register_tenant,
    register_user,
    authenticate_user,
    refresh_access_token,
    logout_user,
    change_password,
    AuthenticationError,
    RegistrationError
)
from app.api.deps import (
    CurrentUserDep,
    AdminDep
)
from app.config import settings


router = APIRouter()


# =============================================================================
# Registration Endpoints
# =============================================================================

@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tenant",
    description="Register a new tenant (company/organization) with an owner account"
)
async def register_new_tenant(
    request: TenantRegistrationRequest,
    db: Session = Depends(get_platform_db)
):
    """
    Register a new tenant and owner account.

    Creates:
    - New tenant organization
    - Owner user account
    - Access and refresh tokens

    Returns tokens for immediate authentication.
    """
    try:
        tenant, user, access_token, refresh_token = register_tenant(
            db=db,
            tenant_name=request.tenant_name,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            tenant_slug=request.tenant_slug
        )

        logger.info(f"New tenant registered: {tenant.name} ({tenant.id})")

        return RegistrationResponse(
            message="Registration successful",
            tenant_id=tenant.id,
            user_id=user.id,
            email=user.email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    except RegistrationError as e:
        logger.warning(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user within the current tenant (admin only)"
)
async def create_user(
    request: UserRegistrationRequest,
    current_user: AdminDep,
    db: Session = Depends(get_platform_db)
):
    """
    Create a new user within the current tenant.

    Requires owner or admin role.
    """
    try:
        user = register_user(
            db=db,
            tenant_id=current_user.tenant_id,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role
        )

        logger.info(
            f"User created: {user.email} by {current_user.email} "
            f"in tenant {current_user.tenant_id}"
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            tenant_id=user.tenant_id,
            is_active=user.is_active,
            created_at=user.created_at
        )

    except RegistrationError as e:
        logger.warning(f"User creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Login Endpoints
# =============================================================================

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
    description="Authenticate user and return access/refresh tokens"
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_platform_db)
):
    """
    Authenticate user with email and password.

    Returns access token (short-lived) and refresh token (long-lived).
    """
    try:
        user, tenant, access_token, refresh_token = authenticate_user(
            db=db,
            email=request.email,
            password=request.password
        )

        logger.info(f"User logged in: {user.email}")

        return LoginResponse(
            message="Login successful",
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                tenant_id=user.tenant_id,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login_at
            ),
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.jwt_access_token_expire_minutes * 60
            )
        )

    except AuthenticationError as e:
        logger.warning(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token"
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_platform_db)
):
    """
    Refresh access token using a valid refresh token.

    The old refresh token is revoked and a new one is issued.
    """
    try:
        new_access_token, new_refresh_token = refresh_access_token(
            db=db,
            refresh_token_str=request.refresh_token
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )

    except AuthenticationError as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description="Logout user and revoke refresh tokens"
)
async def logout(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Logout the current user by revoking all their refresh tokens.
    """
    success = logout_user(db=db, user_id=current_user.user_id)

    if success:
        logger.info(f"User logged out: {current_user.email}")
        return {"message": "Logout successful"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


# =============================================================================
# User Profile Endpoints
# =============================================================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the currently authenticated user's profile"
)
async def get_current_user_profile(current_user: CurrentUserDep):
    """
    Get the current user's profile information.
    """
    return UserResponse(
        id=current_user.user.id,
        email=current_user.user.email,
        full_name=current_user.user.full_name,
        role=current_user.user.role,
        tenant_id=current_user.user.tenant_id,
        is_active=current_user.user.is_active,
        created_at=current_user.user.created_at,
        last_login=current_user.user.last_login_at
    )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update the currently authenticated user's profile"
)
async def update_current_user_profile(
    request: UserUpdateRequest,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Update the current user's profile information.
    """
    user = current_user.user

    if request.full_name is not None:
        user.full_name = request.full_name

    if request.email is not None:
        # Check if email already exists
        from app.services.auth_service import get_user_by_email
        existing = get_user_by_email(db, request.email)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = request.email.lower()

    db.commit()
    db.refresh(user)

    logger.info(f"User profile updated: {user.email}")

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login_at
    )


# =============================================================================
# Password Management Endpoints
# =============================================================================

@router.post(
    "/password/change",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change the current user's password"
)
async def change_user_password(
    request: PasswordChangeRequest,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Change the current user's password.

    Requires the current password for verification.
    All refresh tokens are revoked after password change.
    """
    try:
        success = change_password(
            db=db,
            user_id=current_user.user_id,
            current_password=request.current_password,
            new_password=request.new_password
        )

        if success:
            logger.info(f"Password changed for user: {current_user.email}")
            return {
                "message": "Password changed successfully. Please log in again."
            }

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/password/reset-request",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Request a password reset email"
)
async def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_platform_db)
):
    """
    Request a password reset.

    An email with reset instructions will be sent if the email exists.
    Always returns success to prevent email enumeration.
    """
    # TODO: Implement email sending for password reset
    # For now, just log the request
    logger.info(f"Password reset requested for: {request.email}")

    # Always return success to prevent email enumeration
    return {
        "message": "If the email exists, a password reset link has been sent."
    }


@router.post(
    "/password/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Reset password using reset token"
)
async def reset_password(
    request: PasswordResetConfirm,
    db: Session = Depends(get_platform_db)
):
    """
    Reset password using a reset token.

    The token is sent via email from the reset request endpoint.
    """
    # TODO: Implement password reset token validation
    # For now, return not implemented
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset via token is not yet implemented"
    )


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get(
    "/health",
    summary="Auth service health",
    description="Check if the authentication service is healthy"
)
async def auth_health_check(db: Session = Depends(get_platform_db)):
    """
    Check if the authentication service and database connection are healthy.
    """
    try:
        # Try a simple query to verify database connection
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "service": "authentication",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Auth health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unhealthy"
        )
