"""
Database Connection Management for SQL Server
Handles connection pooling and session management
"""

from typing import Generator, Optional
from sqlalchemy import create_engine, text, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from loguru import logger

from app.config import settings


# SQLAlchemy Base for ORM models
Base = declarative_base()


class DatabaseManager:
    """
    Database Connection Manager
    Handles SQL Server connections with pooling
    """

    def __init__(self):
        """Initialize database connection pool"""
        self.engine: Optional[any] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialized = False

    def initialize(self):
        """
        Initialize database connection pool

        Raises:
            Exception: If connection fails
        """
        if self._initialized:
            logger.warning("Database already initialized")
            return

        try:
            logger.info("Initializing database connection...")
            logger.info(f"Connecting to: {settings.db_server}/{settings.db_name}")

            # Create SQLAlchemy engine with connection pooling
            self.engine = create_engine(
                settings.database_url,
                poolclass=pool.QueuePool,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_timeout=settings.db_pool_timeout,
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
                result = conn.execute(text("SELECT 1"))
                result.fetchone()

            self._initialized = True
            logger.info("[OK] Database connection initialized successfully")

        except Exception as e:
            logger.error(f"[ERROR] Database connection failed: {str(e)}")
            raise

    def get_session(self) -> Session:
        """
        Get database session

        Returns:
            SQLAlchemy Session

        Raises:
            RuntimeError: If database not initialized
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first")

        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions
        Automatically commits or rolls back transactions

        Yields:
            SQLAlchemy Session

        Example:
            with db_manager.session_scope() as session:
                session.query(User).all()
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

        Example:
            results = db_manager.execute_query(
                "SELECT * FROM EmployeeMaster WHERE Ecode = :ecode",
                {"ecode": 123}
            )
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first")

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

    def execute_query_single(self, query: str, params: Optional[dict] = None) -> Optional[dict]:
        """
        Execute query and return first result

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            First result row as dictionary or None
        """
        results = self.execute_query(query, params)
        return results[0] if results else None

    def test_connection(self) -> bool:
        """
        Test database connection

        Returns:
            True if connection successful
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("[OK] Database connection test passed")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Database connection test failed: {str(e)}")
            return False

    def close(self):
        """Close all database connections"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False
            logger.info("[OK] Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions

    Yields:
        SQLAlchemy Session

    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def init_database():
    """
    Initialize database connection
    Called during application startup
    """
    db_manager.initialize()


def close_database():
    """
    Close database connections
    Called during application shutdown
    """
    db_manager.close()
