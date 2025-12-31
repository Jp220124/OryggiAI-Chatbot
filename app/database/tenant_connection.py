"""
Tenant Database Connection Manager
Handles dynamic connections to tenant databases for multi-tenant queries
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, text, pool
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from loguru import logger
import threading
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from app.models.platform import TenantDatabase
from app.security.encryption import decrypt_string


class TenantConnectionPool:
    """
    Connection pool manager for tenant databases

    Maintains a cache of database engines for each tenant database,
    with automatic cleanup of stale connections.
    """

    def __init__(self, max_pool_size: int = 5, pool_timeout: int = 30):
        """
        Initialize tenant connection pool

        Args:
            max_pool_size: Maximum connections per tenant database
            pool_timeout: Connection pool timeout in seconds
        """
        self._engines: Dict[str, Any] = {}  # tenant_db_id -> engine
        self._last_used: Dict[str, datetime] = {}  # tenant_db_id -> last_used_time
        self._lock = threading.Lock()
        self._max_pool_size = max_pool_size
        self._pool_timeout = pool_timeout
        self._stale_threshold = timedelta(minutes=30)  # Clean up after 30 minutes of inactivity

        logger.info("TenantConnectionPool initialized")

    def get_engine(self, tenant_database: TenantDatabase):
        """
        Get or create SQLAlchemy engine for a tenant database

        Args:
            tenant_database: TenantDatabase model instance

        Returns:
            SQLAlchemy engine
        """
        db_id = str(tenant_database.id)

        with self._lock:
            # Check if engine exists and is healthy
            if db_id in self._engines:
                try:
                    # Test connection
                    engine = self._engines[db_id]
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    self._last_used[db_id] = datetime.utcnow()
                    return engine
                except Exception as e:
                    logger.warning(f"Stale connection for {db_id}, recreating: {str(e)}")
                    self._dispose_engine(db_id)

            # Create new engine
            connection_string = self._build_connection_string(tenant_database)

            try:
                engine = create_engine(
                    connection_string,
                    poolclass=pool.QueuePool,
                    pool_size=self._max_pool_size,
                    max_overflow=2,
                    pool_timeout=self._pool_timeout,
                    pool_pre_ping=True,
                    echo=False
                )

                # Test connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

                self._engines[db_id] = engine
                self._last_used[db_id] = datetime.utcnow()

                logger.info(f"Created connection pool for tenant database: {tenant_database.name}")
                return engine

            except Exception as e:
                logger.error(f"Failed to create connection for {tenant_database.name}: {str(e)}")
                raise

    def _build_connection_string(self, tenant_database: TenantDatabase) -> str:
        """Build SQLAlchemy connection string from TenantDatabase"""
        # Decrypt the password
        password = decrypt_string(tenant_database.password_encrypted)

        # URL-encode password to handle special characters like @, !, #, etc.
        encoded_password = quote_plus(password)

        db_type = tenant_database.db_type.lower()

        if db_type == "mssql":
            return (
                f"mssql+pyodbc://{tenant_database.username}:{encoded_password}@"
                f"{tenant_database.host}:{tenant_database.port}/{tenant_database.database_name}"
                f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
            )
        elif db_type == "postgresql":
            return (
                f"postgresql://{tenant_database.username}:{encoded_password}@"
                f"{tenant_database.host}:{tenant_database.port}/{tenant_database.database_name}"
            )
        elif db_type == "mysql":
            return (
                f"mysql+pymysql://{tenant_database.username}:{encoded_password}@"
                f"{tenant_database.host}:{tenant_database.port}/{tenant_database.database_name}"
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def _dispose_engine(self, db_id: str):
        """Dispose of an engine and remove from cache"""
        if db_id in self._engines:
            try:
                self._engines[db_id].dispose()
            except Exception as e:
                logger.warning(f"Error disposing engine for {db_id}: {str(e)}")
            del self._engines[db_id]

        if db_id in self._last_used:
            del self._last_used[db_id]

    def cleanup_stale_connections(self):
        """Clean up connections that haven't been used recently"""
        with self._lock:
            now = datetime.utcnow()
            stale_ids = [
                db_id for db_id, last_used in self._last_used.items()
                if now - last_used > self._stale_threshold
            ]

            for db_id in stale_ids:
                logger.info(f"Cleaning up stale connection for database: {db_id}")
                self._dispose_engine(db_id)

    def close_all(self):
        """Close all connection pools"""
        with self._lock:
            for db_id in list(self._engines.keys()):
                self._dispose_engine(db_id)
        logger.info("All tenant connection pools closed")


class TenantDatabaseManager:
    """
    Manager for executing queries on tenant databases

    Uses the TenantConnectionPool to manage connections and provides
    methods for executing queries with proper resource management.
    """

    def __init__(self):
        """Initialize tenant database manager"""
        self._pool = TenantConnectionPool()

    def execute_query(
        self,
        tenant_database: TenantDatabase,
        query: str,
        params: Optional[dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query on a tenant's database

        Args:
            tenant_database: TenantDatabase model instance
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of result rows as dictionaries
        """
        engine = self._pool.get_engine(tenant_database)

        try:
            with engine.connect() as conn:
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))

                # Convert to list of dictionaries
                columns = result.keys()
                rows = []
                for row in result:
                    rows.append(dict(zip(columns, row)))

                logger.debug(f"Tenant query returned {len(rows)} rows")
                return rows

        except Exception as e:
            logger.error(f"Tenant query execution failed: {str(e)}")
            raise

    def execute_query_single(
        self,
        tenant_database: TenantDatabase,
        query: str,
        params: Optional[dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute query and return first result

        Args:
            tenant_database: TenantDatabase model instance
            query: SQL query string
            params: Query parameters

        Returns:
            First result row as dictionary or None
        """
        results = self.execute_query(tenant_database, query, params)
        return results[0] if results else None

    @contextmanager
    def get_session(self, tenant_database: TenantDatabase):
        """
        Context manager for tenant database sessions

        Args:
            tenant_database: TenantDatabase model instance

        Yields:
            SQLAlchemy Session
        """
        engine = self._pool.get_engine(tenant_database)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def test_connection(self, tenant_database: TenantDatabase) -> Dict[str, Any]:
        """
        Test connection to a tenant database

        Args:
            tenant_database: TenantDatabase model instance

        Returns:
            Dict with success status and details
        """
        try:
            engine = self._pool.get_engine(tenant_database)
            with engine.connect() as conn:
                # Test basic connectivity
                conn.execute(text("SELECT 1"))

                # Get database info
                if tenant_database.db_type.lower() == "mssql":
                    info = conn.execute(text(
                        "SELECT DB_NAME() as db_name, @@VERSION as version"
                    )).fetchone()
                    db_info = {"db_name": info[0], "version": info[1][:50]}
                else:
                    db_info = {"db_name": tenant_database.database_name}

            return {
                "success": True,
                "message": "Connection successful",
                "database_info": db_info
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "error": str(e)
            }

    def cleanup(self):
        """Clean up stale connections"""
        self._pool.cleanup_stale_connections()

    def close(self):
        """Close all connections"""
        self._pool.close_all()


# Global tenant database manager instance
tenant_db_manager = TenantDatabaseManager()
