"""
Local Database Connection Manager

Handles connections to the local SQL Server database.
"""

import pyodbc
from typing import Dict, List, Any, Optional
from datetime import datetime, date, time
from decimal import Decimal
import logging

try:
    from .config import DatabaseConfig
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.config import DatabaseConfig
    except ImportError:
        # Standalone script
        from config import DatabaseConfig

logger = logging.getLogger(__name__)


class LocalDatabaseManager:
    """Manages connection to local SQL Server database"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection: Optional[pyodbc.Connection] = None

    def _build_connection_string(self) -> str:
        """Build ODBC connection string"""
        # TrustServerCertificate required for ODBC Driver 18 with self-signed certs
        trust_cert = getattr(self.config, 'trust_server_certificate', True)
        encrypt = getattr(self.config, 'encrypt', False)

        # Build server string - only include port if non-default (1433)
        server = self.config.host
        if self.config.port and self.config.port != 1433:
            server = f"{self.config.host},{self.config.port}"

        base_conn = (
            f"DRIVER={{{self.config.driver}}};"
            f"SERVER={server};"
            f"DATABASE={self.config.database};"
            f"Connection Timeout={self.config.connection_timeout};"
        )

        # Add encryption settings for ODBC Driver 18
        if "18" in self.config.driver:
            base_conn += f"Encrypt={'yes' if encrypt else 'no'};"
            if trust_cert:
                base_conn += "TrustServerCertificate=yes;"

        if self.config.use_windows_auth:
            return base_conn + "Trusted_Connection=yes;"
        else:
            return (
                base_conn +
                f"UID={self.config.username};"
                f"PWD={self.config.password};"
            )

    def connect(self) -> bool:
        """
        Establish connection to the database

        Returns:
            True if connection successful
        """
        try:
            conn_str = self._build_connection_string()
            self._connection = pyodbc.connect(conn_str)
            logger.info(f"Connected to database: {self.config.database}")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def disconnect(self):
        """Close the database connection"""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self._connection = None

    def is_connected(self) -> bool:
        """Check if connection is active"""
        if not self._connection:
            return False
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False

    def execute_query(
        self,
        query: str,
        timeout: Optional[int] = None,
        max_rows: int = 1000,
    ) -> Dict[str, Any]:
        """
        Execute a SQL query and return results

        Args:
            query: SQL query string
            timeout: Query timeout in seconds
            max_rows: Maximum rows to return

        Returns:
            Dict with columns, rows, row_count, and execution_time_ms
        """
        if not self._connection:
            if not self.connect():
                return {
                    "success": False,
                    "error": "Not connected to database",
                    "error_code": "CONNECTION_ERROR",
                }

        start_time = datetime.utcnow()

        try:
            cursor = self._connection.cursor()

            # Set query timeout on connection (not cursor - pyodbc)
            query_timeout = timeout or self.config.query_timeout
            self._connection.timeout = query_timeout

            # Execute query
            cursor.execute(query)

            # Check if query returns results
            if cursor.description:
                columns = [column[0] for column in cursor.description]
                rows = []

                # Fetch rows up to max_rows
                row_count = 0
                for row in cursor:
                    if row_count >= max_rows:
                        break
                    # Convert row to dict
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Handle special types for JSON serialization
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        elif isinstance(value, date):
                            value = value.isoformat()
                        elif isinstance(value, time):
                            value = value.isoformat()
                        elif isinstance(value, Decimal):
                            value = float(value)
                        elif isinstance(value, bytes):
                            value = value.hex()
                        row_dict[col] = value
                    rows.append(row_dict)
                    row_count += 1

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "execution_time_ms": int(execution_time),
                }
            else:
                # Non-SELECT query (INSERT, UPDATE, DELETE)
                affected = cursor.rowcount
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                return {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "affected_rows": affected,
                    "execution_time_ms": int(execution_time),
                }

        except pyodbc.Error as e:
            logger.error(f"Query execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.args[0] if e.args else "QUERY_ERROR",
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "UNEXPECTED_ERROR",
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the database connection

        Returns:
            Dict with success status and database info
        """
        try:
            if not self._connection:
                if not self.connect():
                    return {
                        "success": False,
                        "error": "Failed to connect to database",
                    }

            cursor = self._connection.cursor()
            cursor.execute("SELECT @@VERSION as version, DB_NAME() as db_name")
            row = cursor.fetchone()
            cursor.close()

            return {
                "success": True,
                "database": self.config.database,
                "version": row.version[:100] if row else "Unknown",
                "db_name": row.db_name if row else self.config.database,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_status(self) -> str:
        """Get connection status string"""
        if self.is_connected():
            return "connected"
        else:
            return "disconnected"
