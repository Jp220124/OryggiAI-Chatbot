"""
Tenant Management Service
Business logic for tenant database operations
"""

import uuid
import time
from datetime import datetime
from typing import Optional, List, Tuple
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from loguru import logger

from app.models.platform import Tenant, TenantUser, TenantDatabase
from app.security.encryption import encrypt_string as encrypt_data, decrypt_string as decrypt_data
from app.middleware.tenant_context import TenantContext, validate_tenant_access


class TenantServiceError(Exception):
    """Custom exception for tenant service errors"""
    pass


class DatabaseConnectionError(Exception):
    """Custom exception for database connection errors"""
    pass


# =============================================================================
# Tenant Database Management
# =============================================================================

def create_database_connection(
    db: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    description: Optional[str] = None,
    use_ssl: bool = False,
    connection_timeout: int = 30,
    query_timeout: int = 60
) -> TenantDatabase:
    """
    Create a new database connection for a tenant.

    Args:
        db: Database session
        tenant_id: Tenant ID
        user_id: User creating the connection
        name: Connection name
        db_type: Database type (mssql, postgresql, etc.)
        host: Database host
        port: Database port
        database_name: Database name
        username: Database username
        password: Database password (plain text)
        description: Optional description
        use_ssl: Whether to use SSL
        connection_timeout: Connection timeout in seconds
        query_timeout: Query timeout in seconds

    Returns:
        Created TenantDatabase

    Raises:
        TenantServiceError: If creation fails
    """
    # Check tenant exists and is active
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise TenantServiceError("Tenant not found")

    if tenant.status != 'active':
        raise TenantServiceError("Tenant is not active")

    # Check database limit
    db_count = db.query(TenantDatabase).filter(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.is_active == True
    ).count()

    if db_count >= tenant.max_databases:
        raise TenantServiceError(
            f"Tenant has reached maximum database limit ({tenant.max_databases})"
        )

    # Check for duplicate name
    existing = db.query(TenantDatabase).filter(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.name == name
    ).first()

    if existing:
        raise TenantServiceError(f"Database connection '{name}' already exists")

    try:
        # Encrypt password
        encrypted_password = encrypt_data(password)

        # Create database connection
        tenant_db = TenantDatabase(
            tenant_id=tenant_id,
            name=name,
            description=description,
            db_type=db_type,
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password_encrypted=encrypted_password,
            use_ssl=use_ssl,
            connection_timeout=connection_timeout,
            query_timeout=query_timeout,
            created_by=user_id
        )

        db.add(tenant_db)
        db.commit()
        db.refresh(tenant_db)

        logger.info(
            f"Created database connection: {name} for tenant {tenant_id}"
        )

        return tenant_db

    except TenantServiceError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create database connection: {str(e)}")
        raise TenantServiceError(f"Failed to create database connection: {str(e)}")


def update_database_connection(
    db: Session,
    database_id: uuid.UUID,
    tenant_id: uuid.UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_ssl: Optional[bool] = None,
    connection_timeout: Optional[int] = None,
    query_timeout: Optional[int] = None
) -> TenantDatabase:
    """
    Update a database connection.

    Args:
        db: Database session
        database_id: Database connection ID
        tenant_id: Tenant ID (for access validation)
        Other args: Fields to update

    Returns:
        Updated TenantDatabase

    Raises:
        TenantServiceError: If update fails
    """
    # Get and validate database
    tenant_db = db.query(TenantDatabase).filter(
        TenantDatabase.id == database_id
    ).first()

    if not tenant_db:
        raise TenantServiceError("Database connection not found")

    # Validate tenant access
    if tenant_db.tenant_id != tenant_id:
        logger.warning(
            f"Tenant {tenant_id} tried to access database belonging to {tenant_db.tenant_id}"
        )
        raise TenantServiceError("Access denied to this database")

    try:
        # Update fields if provided
        if name is not None:
            # Check for duplicate name
            existing = db.query(TenantDatabase).filter(
                TenantDatabase.tenant_id == tenant_id,
                TenantDatabase.name == name,
                TenantDatabase.id != database_id
            ).first()
            if existing:
                raise TenantServiceError(f"Database connection '{name}' already exists")
            tenant_db.name = name

        if description is not None:
            tenant_db.description = description
        if host is not None:
            tenant_db.host = host
        if port is not None:
            tenant_db.port = port
        if database_name is not None:
            tenant_db.database_name = database_name
        if username is not None:
            tenant_db.username = username
        if password is not None:
            tenant_db.password_encrypted = encrypt_data(password)
        if use_ssl is not None:
            tenant_db.use_ssl = use_ssl
        if connection_timeout is not None:
            tenant_db.connection_timeout = connection_timeout
        if query_timeout is not None:
            tenant_db.query_timeout = query_timeout

        # Reset analysis if connection details changed
        if any([host, port, database_name, username, password]):
            tenant_db.schema_analyzed = False
            tenant_db.analysis_status = 'pending'
            tenant_db.analysis_error = None

        db.commit()
        db.refresh(tenant_db)

        logger.info(f"Updated database connection: {tenant_db.name}")

        return tenant_db

    except TenantServiceError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update database connection: {str(e)}")
        raise TenantServiceError(f"Failed to update database connection: {str(e)}")


def delete_database_connection(
    db: Session,
    database_id: uuid.UUID,
    tenant_id: uuid.UUID,
    hard_delete: bool = False
) -> bool:
    """
    Delete (deactivate) a database connection.

    Args:
        db: Database session
        database_id: Database connection ID
        tenant_id: Tenant ID (for access validation)
        hard_delete: If True, permanently delete. Otherwise, soft delete.

    Returns:
        True if deleted successfully

    Raises:
        TenantServiceError: If deletion fails
    """
    tenant_db = db.query(TenantDatabase).filter(
        TenantDatabase.id == database_id
    ).first()

    if not tenant_db:
        raise TenantServiceError("Database connection not found")

    if tenant_db.tenant_id != tenant_id:
        raise TenantServiceError("Access denied to this database")

    try:
        if hard_delete:
            db.delete(tenant_db)
            logger.info(f"Hard deleted database connection: {tenant_db.name}")
        else:
            tenant_db.is_active = False
            logger.info(f"Soft deleted database connection: {tenant_db.name}")

        db.commit()
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete database connection: {str(e)}")
        raise TenantServiceError(f"Failed to delete database connection: {str(e)}")


def get_database_connection(
    db: Session,
    database_id: uuid.UUID,
    tenant_id: uuid.UUID
) -> Optional[TenantDatabase]:
    """
    Get a database connection by ID.

    Args:
        db: Database session
        database_id: Database connection ID
        tenant_id: Tenant ID (for access validation)

    Returns:
        TenantDatabase or None
    """
    tenant_db = db.query(TenantDatabase).filter(
        TenantDatabase.id == database_id,
        TenantDatabase.tenant_id == tenant_id
    ).first()

    return tenant_db


def list_database_connections(
    db: Session,
    tenant_id: uuid.UUID,
    include_inactive: bool = False
) -> List[TenantDatabase]:
    """
    List all database connections for a tenant.

    Args:
        db: Database session
        tenant_id: Tenant ID
        include_inactive: Include deactivated connections

    Returns:
        List of TenantDatabase objects
    """
    query = db.query(TenantDatabase).filter(
        TenantDatabase.tenant_id == tenant_id
    )

    if not include_inactive:
        query = query.filter(TenantDatabase.is_active == True)

    return query.order_by(TenantDatabase.created_at.desc()).all()


# =============================================================================
# Database Connection Testing
# =============================================================================

def test_database_connection(
    db: Session,
    database_id: uuid.UUID,
    tenant_id: uuid.UUID
) -> Tuple[bool, str, Optional[float], Optional[str]]:
    """
    Test a database connection.

    Args:
        db: Database session
        database_id: Database connection ID
        tenant_id: Tenant ID (for access validation)

    Returns:
        Tuple of (success, message, connection_time_ms, server_version)
    """
    tenant_db = get_database_connection(db, database_id, tenant_id)

    if not tenant_db:
        return False, "Database connection not found", None, None

    try:
        # Decrypt password
        password = decrypt_data(tenant_db.password_encrypted)

        # Build connection string
        connection_url = tenant_db.get_connection_string(password)

        # Test connection
        start_time = time.time()

        engine = create_engine(
            connection_url,
            connect_args={
                "timeout": tenant_db.connection_timeout
            } if tenant_db.db_type == 'sqlite' else {}
        )

        with engine.connect() as conn:
            # Get server version
            if tenant_db.db_type == 'mssql':
                result = conn.execute(text("SELECT @@VERSION"))
            elif tenant_db.db_type == 'postgresql':
                result = conn.execute(text("SELECT version()"))
            elif tenant_db.db_type == 'mysql':
                result = conn.execute(text("SELECT VERSION()"))
            else:
                result = conn.execute(text("SELECT 1"))

            row = result.fetchone()
            version = str(row[0]) if row else "Unknown"

        connection_time = (time.time() - start_time) * 1000  # Convert to ms

        engine.dispose()

        logger.info(f"Database connection test successful: {tenant_db.name}")

        return True, "Connection successful", connection_time, version[:200]

    except Exception as e:
        logger.warning(f"Database connection test failed: {str(e)}")
        return False, f"Connection failed: {str(e)}", None, None


def test_new_database_connection(
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    use_ssl: bool = False,
    connection_timeout: int = 30
) -> Tuple[bool, str, Optional[float], Optional[str]]:
    """
    Test a new database connection before saving.

    Args:
        Connection parameters

    Returns:
        Tuple of (success, message, connection_time_ms, server_version)
    """
    try:
        # Build connection URL based on db_type
        db_drivers = {
            "mssql": "mssql+pyodbc",
            "postgresql": "postgresql+psycopg2",
            "mysql": "mysql+pymysql",
            "sqlite": "sqlite",
            "oracle": "oracle+cx_oracle"
        }

        driver = db_drivers.get(db_type, "mssql+pyodbc")

        # URL-encode username and password to handle special characters like @, #, etc.
        encoded_username = quote_plus(username)
        encoded_password = quote_plus(password)

        if db_type == 'sqlite':
            connection_url = f"{driver}:///{database_name}"
        elif db_type == 'mssql':
            connection_url = (
                f"{driver}://{encoded_username}:{encoded_password}"
                f"@{host}:{port}/{database_name}"
                f"?driver=ODBC+Driver+17+for+SQL+Server"
            )
        else:
            connection_url = (
                f"{driver}://{encoded_username}:{encoded_password}"
                f"@{host}:{port}/{database_name}"
            )

        # Test connection
        start_time = time.time()

        engine = create_engine(
            connection_url,
            connect_args={
                "timeout": connection_timeout
            } if db_type == 'sqlite' else {}
        )

        with engine.connect() as conn:
            # Get server version
            if db_type == 'mssql':
                result = conn.execute(text("SELECT @@VERSION"))
            elif db_type == 'postgresql':
                result = conn.execute(text("SELECT version()"))
            elif db_type == 'mysql':
                result = conn.execute(text("SELECT VERSION()"))
            else:
                result = conn.execute(text("SELECT 1"))

            row = result.fetchone()
            version = str(row[0]) if row else "Unknown"

        connection_time = (time.time() - start_time) * 1000

        engine.dispose()

        return True, "Connection successful", connection_time, version[:200]

    except Exception as e:
        return False, f"Connection failed: {str(e)}", None, None


# =============================================================================
# Tenant Management
# =============================================================================

def get_tenant(
    db: Session,
    tenant_id: uuid.UUID
) -> Optional[Tenant]:
    """Get a tenant by ID"""
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def update_tenant(
    db: Session,
    tenant_id: uuid.UUID,
    name: Optional[str] = None,
    organization_type: Optional[str] = None,
    industry: Optional[str] = None,
    company_size: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    country: Optional[str] = None,
    timezone: Optional[str] = None,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None
) -> Tenant:
    """
    Update tenant information.

    Args:
        db: Database session
        tenant_id: Tenant ID
        Other args: Fields to update

    Returns:
        Updated Tenant

    Raises:
        TenantServiceError: If update fails
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise TenantServiceError("Tenant not found")

    try:
        if name is not None:
            tenant.name = name
        if organization_type is not None:
            tenant.organization_type = organization_type
        if industry is not None:
            tenant.industry = industry
        if company_size is not None:
            tenant.company_size = company_size
        if phone is not None:
            tenant.phone = phone
        if address is not None:
            tenant.address = address
        if country is not None:
            tenant.country = country
        if timezone is not None:
            tenant.timezone = timezone
        if logo_url is not None:
            tenant.logo_url = logo_url
        if primary_color is not None:
            tenant.primary_color = primary_color

        db.commit()
        db.refresh(tenant)

        logger.info(f"Updated tenant: {tenant.name}")

        return tenant

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update tenant: {str(e)}")
        raise TenantServiceError(f"Failed to update tenant: {str(e)}")


def get_tenant_usage_stats(
    db: Session,
    tenant_id: uuid.UUID
) -> dict:
    """
    Get usage statistics for a tenant.

    Args:
        db: Database session
        tenant_id: Tenant ID

    Returns:
        Dictionary with usage statistics
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        raise TenantServiceError("Tenant not found")

    # Count users
    user_count = db.query(TenantUser).filter(
        TenantUser.tenant_id == tenant_id
    ).count()

    active_user_count = db.query(TenantUser).filter(
        TenantUser.tenant_id == tenant_id,
        TenantUser.is_active == True
    ).count()

    # Count databases
    database_count = db.query(TenantDatabase).filter(
        TenantDatabase.tenant_id == tenant_id
    ).count()

    active_database_count = db.query(TenantDatabase).filter(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.is_active == True
    ).count()

    # Sum table and view counts
    from sqlalchemy import func

    table_stats = db.query(
        func.sum(TenantDatabase.table_count).label('tables'),
        func.sum(TenantDatabase.view_count).label('views')
    ).filter(
        TenantDatabase.tenant_id == tenant_id,
        TenantDatabase.is_active == True
    ).first()

    total_tables = table_stats.tables or 0
    total_views = table_stats.views or 0

    return {
        "tenant_id": tenant_id,
        "user_count": user_count,
        "active_user_count": active_user_count,
        "database_count": database_count,
        "active_database_count": active_database_count,
        "total_tables": total_tables,
        "total_views": total_views,
        "queries_today": 0,  # TODO: Implement query tracking
        "queries_this_month": 0,
        "storage_used_mb": 0.0
    }


# =============================================================================
# User Management within Tenant
# =============================================================================

def list_tenant_users(
    db: Session,
    tenant_id: uuid.UUID,
    include_inactive: bool = False
) -> List[TenantUser]:
    """
    List all users for a tenant.

    Args:
        db: Database session
        tenant_id: Tenant ID
        include_inactive: Include inactive users

    Returns:
        List of TenantUser objects
    """
    query = db.query(TenantUser).filter(
        TenantUser.tenant_id == tenant_id
    )

    if not include_inactive:
        query = query.filter(TenantUser.is_active == True)

    return query.order_by(TenantUser.created_at.desc()).all()


def get_tenant_user(
    db: Session,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID
) -> Optional[TenantUser]:
    """Get a user within tenant scope"""
    return db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == tenant_id
    ).first()


def update_tenant_user(
    db: Session,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    display_name: Optional[str] = None,
    phone: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
) -> TenantUser:
    """
    Update a user within tenant.

    Args:
        db: Database session
        user_id: User ID
        tenant_id: Tenant ID
        Other args: Fields to update

    Returns:
        Updated TenantUser

    Raises:
        TenantServiceError: If update fails
    """
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == tenant_id
    ).first()

    if not user:
        raise TenantServiceError("User not found")

    # Prevent deactivating the only owner
    if is_active == False and user.role == 'owner':
        owner_count = db.query(TenantUser).filter(
            TenantUser.tenant_id == tenant_id,
            TenantUser.role == 'owner',
            TenantUser.is_active == True
        ).count()

        if owner_count <= 1:
            raise TenantServiceError("Cannot deactivate the only owner")

    try:
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if display_name is not None:
            user.display_name = display_name
        if phone is not None:
            user.phone = phone
        if role is not None:
            # Cannot change owner role to something else if only owner
            if user.role == 'owner' and role != 'owner':
                owner_count = db.query(TenantUser).filter(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.role == 'owner',
                    TenantUser.is_active == True
                ).count()
                if owner_count <= 1:
                    raise TenantServiceError("Cannot demote the only owner")
            user.role = role
        if is_active is not None:
            user.is_active = is_active

        db.commit()
        db.refresh(user)

        logger.info(f"Updated user: {user.email}")

        return user

    except TenantServiceError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user: {str(e)}")
        raise TenantServiceError(f"Failed to update user: {str(e)}")


def delete_tenant_user(
    db: Session,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    hard_delete: bool = False
) -> bool:
    """
    Delete (deactivate) a user.

    Args:
        db: Database session
        user_id: User ID
        tenant_id: Tenant ID
        hard_delete: Permanently delete if True

    Returns:
        True if successful

    Raises:
        TenantServiceError: If deletion fails
    """
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == tenant_id
    ).first()

    if not user:
        raise TenantServiceError("User not found")

    # Prevent deleting the only owner
    if user.role == 'owner':
        owner_count = db.query(TenantUser).filter(
            TenantUser.tenant_id == tenant_id,
            TenantUser.role == 'owner',
            TenantUser.is_active == True
        ).count()

        if owner_count <= 1:
            raise TenantServiceError("Cannot delete the only owner")

    try:
        if hard_delete:
            # Delete refresh tokens first
            from app.models.platform import RefreshToken
            db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id
            ).delete()
            db.delete(user)
            logger.info(f"Hard deleted user: {user.email}")
        else:
            user.is_active = False
            user.deleted_at = datetime.utcnow()
            logger.info(f"Soft deleted user: {user.email}")

        db.commit()
        return True

    except TenantServiceError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user: {str(e)}")
        raise TenantServiceError(f"Failed to delete user: {str(e)}")
