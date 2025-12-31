"""
Platform Database Connection Management
Handles connection to OryggiAI_Platform database for multi-tenant SaaS operations
"""

from typing import Generator, Optional
from sqlalchemy import create_engine, text, pool
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from loguru import logger

from app.config import settings
from app.models.platform.base import PlatformBase


class PlatformDatabaseManager:
    """
    Platform Database Connection Manager
    Handles SQL Server connections to the OryggiAI_Platform database
    """

    def __init__(self):
        """Initialize platform database connection pool"""
        self.engine: Optional[any] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialized = False

    def initialize(self):
        """
        Initialize platform database connection pool

        Raises:
            Exception: If connection fails
        """
        if self._initialized:
            logger.warning("Platform database already initialized")
            return

        try:
            logger.info("Initializing platform database connection...")
            logger.info(f"Connecting to: {settings.platform_db_server}/{settings.platform_db_name}")

            # Create SQLAlchemy engine with connection pooling
            self.engine = create_engine(
                settings.platform_database_url,
                poolclass=pool.QueuePool,
                pool_size=settings.platform_db_pool_size,
                max_overflow=settings.platform_db_max_overflow,
                pool_timeout=settings.platform_db_pool_timeout,
                pool_pre_ping=True,  # Test connections before using
                echo=settings.debug,  # Log SQL queries in debug mode
            )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                result.fetchone()

            self._initialized = True
            logger.info("[OK] Platform database connection initialized successfully")

        except Exception as e:
            logger.error(f"[FAIL] Platform database connection failed: {str(e)}")
            raise

    def create_tables(self):
        """
        Create all platform tables if they don't exist.
        Note: Prefer using the SQL migration script for production.
        """
        if not self._initialized:
            raise RuntimeError("Platform database not initialized")

        try:
            # Import all models to ensure they're registered
            from app.models.platform import (
                Tenant, TenantUser, RefreshToken, TenantDatabase,
                SchemaCache, FewShotExample, UsageMetrics, AuditLog, ApiKey
            )

            # Create tables
            PlatformBase.metadata.create_all(bind=self.engine)
            logger.info("[OK] Platform database tables created/verified")

        except Exception as e:
            logger.error(f"[FAIL] Failed to create platform tables: {str(e)}")
            raise

    def get_session(self) -> Session:
        """
        Get platform database session

        Returns:
            SQLAlchemy Session

        Raises:
            RuntimeError: If database not initialized
        """
        if not self._initialized:
            raise RuntimeError("Platform database not initialized. Call initialize() first")

        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Context manager for platform database sessions
        Automatically commits or rolls back transactions

        Yields:
            SQLAlchemy Session

        Example:
            with platform_db.session_scope() as session:
                tenant = session.query(Tenant).first()
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def execute_query(self, query: str, params: Optional[dict] = None) -> list:
        """
        Execute raw SQL query and return results

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result rows as dictionaries
        """
        if not self._initialized:
            raise RuntimeError("Platform database not initialized")

        with self.engine.connect() as conn:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))

            # Convert to list of dictionaries
            columns = result.keys()
            rows = []
            for row in result:
                rows.append(dict(zip(columns, row)))

            return rows

    def test_connection(self) -> bool:
        """
        Test platform database connection

        Returns:
            True if connection successful
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                result.fetchone()
            logger.info("[OK] Platform database connection test passed")
            return True
        except Exception as e:
            logger.error(f"[FAIL] Platform database connection test failed: {str(e)}")
            return False

    def check_tables_exist(self) -> dict:
        """
        Check if platform tables exist

        Returns:
            Dict with table existence status
        """
        if not self._initialized:
            raise RuntimeError("Platform database not initialized")

        tables_to_check = [
            'tenants',
            'tenant_users',
            'tenant_databases',
            'schema_cache',
            'few_shot_examples',
            'usage_metrics',
            'audit_logs',
            'api_keys',
            'refresh_tokens'
        ]

        result = {}

        with self.engine.connect() as conn:
            for table in tables_to_check:
                check_query = text("""
                    SELECT COUNT(*) as cnt
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = :table_name
                """)
                res = conn.execute(check_query, {"table_name": table})
                count = res.fetchone()[0]
                result[table] = count > 0

        return result

    def close(self):
        """Close all platform database connections"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False
            logger.info("[OK] Platform database connections closed")


# Global platform database manager instance
platform_db = PlatformDatabaseManager()


def get_platform_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for platform database sessions

    Yields:
        SQLAlchemy Session

    Example:
        @app.get("/tenants")
        def get_tenants(db: Session = Depends(get_platform_db)):
            return db.query(Tenant).all()
    """
    session = platform_db.get_session()
    try:
        yield session
    finally:
        session.close()


def init_platform_database():
    """
    Initialize platform database connection
    Called during application startup
    """
    platform_db.initialize()


def close_platform_database():
    """
    Close platform database connections
    Called during application shutdown
    """
    platform_db.close()


def get_platform_session() -> Session:
    """
    Get a platform database session directly (for tests and scripts).
    Note: Caller is responsible for closing the session.

    Returns:
        SQLAlchemy Session

    Example:
        session = get_platform_session()
        try:
            # do work
            session.commit()
        finally:
            session.close()
    """
    if not platform_db._initialized:
        platform_db.initialize()
    return platform_db.get_session()
