"""
Tenant Management API Routes
Endpoints for managing tenant settings, databases, and users
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from app.database.platform_connection import get_platform_db
from app.api.deps import (
    CurrentUserDep,
    OwnerDep,
    AdminDep
)
from app.schemas.tenant import (
    TenantResponse,
    TenantUpdate,
    TenantUsageStats,
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseConnectionResponse,
    DatabaseConnectionSummary,
    DatabaseTestResult,
    TenantUserCreate,
    TenantUserUpdate,
    TenantUserResponse,
    TenantUserSummary
)
from app.services.tenant_service import (
    get_tenant,
    update_tenant,
    get_tenant_usage_stats,
    create_database_connection,
    update_database_connection,
    delete_database_connection,
    get_database_connection,
    list_database_connections,
    test_database_connection,
    test_new_database_connection,
    list_tenant_users,
    get_tenant_user,
    update_tenant_user,
    delete_tenant_user,
    TenantServiceError
)
from app.services.auth_service import register_user, RegistrationError


router = APIRouter()


# =============================================================================
# Tenant Management Endpoints
# =============================================================================

@router.get(
    "/",
    response_model=TenantResponse,
    summary="Get current tenant",
    description="Get details of the current tenant"
)
async def get_current_tenant(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """Get the current tenant's information."""
    tenant = get_tenant(db, current_user.tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    return TenantResponse.model_validate(tenant)


@router.put(
    "/",
    response_model=TenantResponse,
    summary="Update tenant",
    description="Update the current tenant's settings (owner only)"
)
async def update_current_tenant(
    request: TenantUpdate,
    current_user: OwnerDep,
    db: Session = Depends(get_platform_db)
):
    """Update tenant settings. Requires owner role."""
    try:
        tenant = update_tenant(
            db=db,
            tenant_id=current_user.tenant_id,
            name=request.name,
            organization_type=request.organization_type,
            industry=request.industry,
            company_size=request.company_size,
            phone=request.phone,
            address=request.address,
            country=request.country,
            timezone=request.timezone,
            logo_url=request.logo_url,
            primary_color=request.primary_color
        )

        logger.info(f"Tenant updated: {tenant.name} by {current_user.email}")

        return TenantResponse.model_validate(tenant)

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/usage",
    response_model=TenantUsageStats,
    summary="Get usage statistics",
    description="Get usage statistics for the current tenant"
)
async def get_usage_statistics(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """Get tenant usage statistics."""
    try:
        stats = get_tenant_usage_stats(db, current_user.tenant_id)
        return TenantUsageStats(**stats)

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Database Connection Endpoints
# =============================================================================

@router.get(
    "/databases",
    response_model=List[DatabaseConnectionSummary],
    summary="List database connections",
    description="Get all database connections for the current tenant"
)
async def list_databases(
    current_user: CurrentUserDep,
    include_inactive: bool = False,
    db: Session = Depends(get_platform_db)
):
    """List all database connections for the tenant."""
    databases = list_database_connections(
        db=db,
        tenant_id=current_user.tenant_id,
        include_inactive=include_inactive
    )

    return [
        DatabaseConnectionSummary(
            id=d.id,
            name=d.name,
            db_type=d.db_type,
            host=d.host,
            port=d.port,
            database_name=d.database_name,
            is_active=d.is_active,
            schema_analyzed=d.schema_analyzed,
            analysis_status=d.analysis_status,
            table_count=d.table_count,
            created_at=d.created_at
        )
        for d in databases
    ]


@router.post(
    "/databases",
    response_model=DatabaseConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create database connection",
    description="Add a new database connection (admin only)"
)
async def create_database(
    request: DatabaseConnectionCreate,
    current_user: AdminDep,
    db: Session = Depends(get_platform_db)
):
    """Create a new database connection. Requires admin role."""
    try:
        tenant_db = create_database_connection(
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            name=request.name,
            db_type=request.db_type.value,
            host=request.host,
            port=request.port,
            database_name=request.database_name,
            username=request.username,
            password=request.password,
            description=request.description,
            use_ssl=request.use_ssl,
            connection_timeout=request.connection_timeout,
            query_timeout=request.query_timeout
        )

        logger.info(
            f"Database connection created: {tenant_db.name} "
            f"by {current_user.email}"
        )

        return DatabaseConnectionResponse.model_validate(tenant_db)

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/databases/{database_id}",
    response_model=DatabaseConnectionResponse,
    summary="Get database connection",
    description="Get details of a specific database connection"
)
async def get_database(
    database_id: str,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """Get a specific database connection."""
    try:
        import uuid
        db_id = uuid.UUID(database_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid database ID format"
        )

    tenant_db = get_database_connection(
        db=db,
        database_id=db_id,
        tenant_id=current_user.tenant_id
    )

    if not tenant_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found"
        )

    return DatabaseConnectionResponse.model_validate(tenant_db)


@router.put(
    "/databases/{database_id}",
    response_model=DatabaseConnectionResponse,
    summary="Update database connection",
    description="Update a database connection (admin only)"
)
async def update_database(
    database_id: str,
    request: DatabaseConnectionUpdate,
    current_user: AdminDep,
    db: Session = Depends(get_platform_db)
):
    """Update a database connection. Requires admin role."""
    try:
        import uuid
        db_id = uuid.UUID(database_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid database ID format"
        )

    try:
        tenant_db = update_database_connection(
            db=db,
            database_id=db_id,
            tenant_id=current_user.tenant_id,
            name=request.name,
            description=request.description,
            host=request.host,
            port=request.port,
            database_name=request.database_name,
            username=request.username,
            password=request.password,
            use_ssl=request.use_ssl,
            connection_timeout=request.connection_timeout,
            query_timeout=request.query_timeout
        )

        logger.info(
            f"Database connection updated: {tenant_db.name} "
            f"by {current_user.email}"
        )

        return DatabaseConnectionResponse.model_validate(tenant_db)

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/databases/{database_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete database connection",
    description="Delete a database connection (admin only)"
)
async def delete_database(
    database_id: str,
    current_user: AdminDep,
    hard_delete: bool = False,
    db: Session = Depends(get_platform_db)
):
    """Delete a database connection. Requires admin role."""
    try:
        import uuid
        db_id = uuid.UUID(database_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid database ID format"
        )

    try:
        delete_database_connection(
            db=db,
            database_id=db_id,
            tenant_id=current_user.tenant_id,
            hard_delete=hard_delete
        )

        logger.info(
            f"Database connection deleted: {database_id} "
            f"by {current_user.email}"
        )

        return {"message": "Database connection deleted successfully"}

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/databases/{database_id}/test",
    response_model=DatabaseTestResult,
    summary="Test database connection",
    description="Test connectivity to a database"
)
async def test_database(
    database_id: str,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """Test a database connection."""
    try:
        import uuid
        db_id = uuid.UUID(database_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid database ID format"
        )

    success, message, time_ms, version = test_database_connection(
        db=db,
        database_id=db_id,
        tenant_id=current_user.tenant_id
    )

    return DatabaseTestResult(
        success=success,
        message=message,
        connection_time_ms=time_ms,
        server_version=version
    )


@router.post(
    "/databases/test",
    response_model=DatabaseTestResult,
    summary="Test new database connection",
    description="Test connectivity to a new database before saving"
)
async def test_new_database(
    request: DatabaseConnectionCreate,
    current_user: AdminDep
):
    """Test a new database connection before saving."""
    success, message, time_ms, version = test_new_database_connection(
        db_type=request.db_type.value,
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        password=request.password,
        use_ssl=request.use_ssl,
        connection_timeout=request.connection_timeout
    )

    return DatabaseTestResult(
        success=success,
        message=message,
        connection_time_ms=time_ms,
        server_version=version
    )


@router.post(
    "/databases/{database_id}/onboard",
    summary="Onboard database",
    description="Start automatic onboarding for a database (admin only)"
)
async def onboard_database(
    database_id: str,
    current_user: AdminDep,
    fewshot_count: int = 50,
    db: Session = Depends(get_platform_db)
):
    """
    Start automatic onboarding for a database.

    This will:
    1. Extract the database schema
    2. Analyze the organization type
    3. Generate Q&A examples for RAG
    4. Create embeddings for chat

    Requires admin role.
    """
    try:
        import uuid
        db_id = uuid.UUID(database_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid database ID format"
        )

    # Get the database connection
    tenant_db = get_database_connection(
        db=db,
        database_id=db_id,
        tenant_id=current_user.tenant_id
    )

    if not tenant_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found"
        )

    try:
        from app.services.tenant_onboarding import tenant_onboarding_service

        result = await tenant_onboarding_service.onboard_tenant_database(
            db=db,
            tenant_database=tenant_db,
            fewshot_count=fewshot_count,
            include_views=True
        )

        if result["success"]:
            logger.info(
                f"Database onboarded: {tenant_db.name} "
                f"by {current_user.email}"
            )
            return {
                "success": True,
                "message": f"Onboarding complete for {tenant_db.name}",
                "organization_name": result.get("organization_name"),
                "organization_type": result.get("organization_type_display"),
                "detected_modules": result.get("detected_modules", []),
                "tables_analyzed": result.get("tables_analyzed", 0),
                "schema_records": result.get("schema_records", 0),
                "fewshot_records": result.get("fewshot_records", 0),
                "onboarding_time_seconds": result.get("onboarding_time_seconds", 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Onboarding failed: {', '.join(result.get('errors', ['Unknown error']))}"
            )

    except Exception as e:
        logger.error(f"Onboarding failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/databases/{database_id}/onboard/status",
    summary="Get onboarding status",
    description="Get the onboarding status for a database"
)
async def get_onboard_status(
    database_id: str,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """Get onboarding status for a database."""
    try:
        import uuid
        db_id = uuid.UUID(database_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid database ID format"
        )

    # Verify database belongs to tenant
    tenant_db = get_database_connection(
        db=db,
        database_id=db_id,
        tenant_id=current_user.tenant_id
    )

    if not tenant_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found"
        )

    from app.services.tenant_onboarding import tenant_onboarding_service

    status_info = tenant_onboarding_service.get_onboarding_status(
        db=db,
        tenant_db_id=db_id
    )

    return {
        "database_id": str(db_id),
        "database_name": tenant_db.name,
        "is_onboarded": status_info["is_onboarded"],
        "schema_count": status_info["schema_count"],
        "fewshot_count": status_info["fewshot_count"],
        "ready_to_chat": status_info["ready_to_chat"]
    }


# =============================================================================
# User Management Endpoints
# =============================================================================

@router.get(
    "/users",
    response_model=List[TenantUserSummary],
    summary="List tenant users",
    description="Get all users in the current tenant"
)
async def list_users(
    current_user: AdminDep,
    include_inactive: bool = False,
    db: Session = Depends(get_platform_db)
):
    """List all users in the tenant. Requires admin role."""
    users = list_tenant_users(
        db=db,
        tenant_id=current_user.tenant_id,
        include_inactive=include_inactive
    )

    return [
        TenantUserSummary(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active
        )
        for u in users
    ]


@router.post(
    "/users",
    response_model=TenantUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user in the tenant (admin only)"
)
async def create_user(
    request: TenantUserCreate,
    current_user: AdminDep,
    db: Session = Depends(get_platform_db)
):
    """Create a new user. Requires admin role."""
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
            f"User created: {user.email} by {current_user.email}"
        )

        return TenantUserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            phone=user.phone,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at
        )

    except RegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/users/{user_id}",
    response_model=TenantUserResponse,
    summary="Get user",
    description="Get details of a specific user"
)
async def get_user(
    user_id: str,
    current_user: AdminDep,
    db: Session = Depends(get_platform_db)
):
    """Get a specific user. Requires admin role."""
    try:
        import uuid
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    user = get_tenant_user(
        db=db,
        user_id=uid,
        tenant_id=current_user.tenant_id
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return TenantUserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


@router.put(
    "/users/{user_id}",
    response_model=TenantUserResponse,
    summary="Update user",
    description="Update a user in the tenant (admin only)"
)
async def update_user(
    user_id: str,
    request: TenantUserUpdate,
    current_user: AdminDep,
    db: Session = Depends(get_platform_db)
):
    """Update a user. Requires admin role."""
    try:
        import uuid
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    try:
        user = update_tenant_user(
            db=db,
            user_id=uid,
            tenant_id=current_user.tenant_id,
            first_name=request.first_name,
            last_name=request.last_name,
            display_name=request.display_name,
            phone=request.phone,
            role=request.role,
            is_active=request.is_active
        )

        logger.info(
            f"User updated: {user.email} by {current_user.email}"
        )

        return TenantUserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            phone=user.phone,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at
        )

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete user",
    description="Delete a user from the tenant (admin only)"
)
async def delete_user(
    user_id: str,
    current_user: AdminDep,
    hard_delete: bool = False,
    db: Session = Depends(get_platform_db)
):
    """Delete a user. Requires admin role."""
    try:
        import uuid
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Cannot delete self
    if uid == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    try:
        delete_tenant_user(
            db=db,
            user_id=uid,
            tenant_id=current_user.tenant_id,
            hard_delete=hard_delete
        )

        logger.info(
            f"User deleted: {user_id} by {current_user.email}"
        )

        return {"message": "User deleted successfully"}

    except TenantServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
