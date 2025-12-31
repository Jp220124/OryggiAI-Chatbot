"""
Gateway Schema Extractor
Extracts database schema through the Gateway Agent connection
for firewalled databases that cannot be accessed directly.
"""

from typing import Dict, List, Any, Optional
from loguru import logger

from app.gateway.connection_manager import gateway_manager
from app.gateway.schemas import QueryStatus


class GatewaySchemaExtractor:
    """
    Extracts database schema through Gateway Agent WebSocket connection.

    This is used for databases that are behind a firewall and cannot be
    accessed directly by the SaaS platform. The Gateway Agent executes
    queries locally and returns results via WebSocket.
    """

    def __init__(self, database_id: str, db_type: str = "mssql"):
        """
        Initialize gateway schema extractor

        Args:
            database_id: UUID of the tenant database
            db_type: Type of database (mssql, postgresql, mysql)
        """
        self.database_id = database_id
        self.db_type = db_type.lower()

    def is_connected(self) -> bool:
        """Check if gateway agent is connected for this database"""
        return gateway_manager.is_connected(self.database_id)

    async def execute_query(self, sql: str, max_rows: int = 1000) -> Dict[str, Any]:
        """
        Execute a SQL query through the gateway agent

        Args:
            sql: SQL query to execute
            max_rows: Maximum rows to return

        Returns:
            Query results with columns and rows
        """
        if not self.is_connected():
            raise Exception(f"Gateway not connected for database {self.database_id}")

        response = await gateway_manager.execute_query(
            database_id=self.database_id,
            sql_query=sql,
            timeout=120,
            max_rows=max_rows,
        )

        if response.status == QueryStatus.ERROR:
            raise Exception(f"Query failed: {response.error_message}")

        return {
            "columns": response.columns or [],
            "rows": response.rows or [],
            "row_count": response.row_count or 0,
        }

    async def extract_full_schema(
        self,
        schema: str = "dbo",
        include_views: bool = True,
        sample_rows: int = 5,
        max_tables: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract complete schema from database through gateway

        Args:
            schema: Database schema name (default: dbo for SQL Server)
            include_views: Whether to include views (default: True)
            sample_rows: Number of sample rows to fetch per table (default: 5)
            max_tables: Optional limit on tables (for testing)

        Returns:
            Complete schema dictionary
        """
        logger.info(f"Extracting schema through gateway for database {self.database_id}")

        result = {
            "tables": {},
            "views": {},
            "relationships": [],
            "statistics": {
                "total_tables": 0,
                "total_views": 0,
                "total_columns": 0,
            }
        }

        try:
            # Get list of tables
            tables = await self._get_tables(schema)

            if max_tables:
                tables = tables[:max_tables]

            logger.info(f"Found {len(tables)} tables")

            for table_name in tables:
                try:
                    table_info = await self._extract_table_info(schema, table_name, sample_rows)
                    result["tables"][table_name] = table_info
                    result["statistics"]["total_columns"] += len(table_info.get("columns", []))
                except Exception as e:
                    logger.warning(f"Failed to extract table {table_name}: {e}")

            result["statistics"]["total_tables"] = len(result["tables"])

            # Get views if requested
            if include_views:
                views = await self._get_views(schema)
                logger.info(f"Found {len(views)} views")

                for view_name in views:
                    try:
                        view_info = await self._extract_view_info(schema, view_name, sample_rows)
                        result["views"][view_name] = view_info
                    except Exception as e:
                        logger.warning(f"Failed to extract view {view_name}: {e}")

                result["statistics"]["total_views"] = len(result["views"])

            # Get relationships
            relationships = await self._get_relationships(schema)
            result["relationships"] = relationships

            logger.info(f"Schema extraction complete: {result['statistics']}")
            return result

        except Exception as e:
            logger.error(f"Schema extraction failed: {e}")
            raise

    async def _get_tables(self, schema: str) -> List[str]:
        """Get list of tables in schema"""
        if self.db_type == "mssql":
            sql = f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{schema}'
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """
        elif self.db_type == "postgresql":
            sql = f"""
                SELECT tablename as TABLE_NAME
                FROM pg_catalog.pg_tables
                WHERE schemaname = '{schema}'
                ORDER BY tablename
            """
        else:
            sql = f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{schema}'
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """

        result = await self.execute_query(sql)
        # Rows are dicts with column names as keys
        return [row.get("TABLE_NAME") for row in result["rows"] if row.get("TABLE_NAME")]

    async def _get_views(self, schema: str) -> List[str]:
        """Get list of views in schema"""
        if self.db_type == "mssql":
            sql = f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_SCHEMA = '{schema}'
                ORDER BY TABLE_NAME
            """
        elif self.db_type == "postgresql":
            sql = f"""
                SELECT viewname as TABLE_NAME
                FROM pg_catalog.pg_views
                WHERE schemaname = '{schema}'
                ORDER BY viewname
            """
        else:
            sql = f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_SCHEMA = '{schema}'
                ORDER BY TABLE_NAME
            """

        result = await self.execute_query(sql)
        # Rows are dicts with column names as keys
        return [row.get("TABLE_NAME") for row in result["rows"] if row.get("TABLE_NAME")]

    async def _extract_table_info(
        self,
        schema: str,
        table_name: str,
        sample_rows: int
    ) -> Dict[str, Any]:
        """Extract detailed information about a table"""
        info = {
            "columns": [],
            "primary_key": [],
            "foreign_keys": [],
            "sample_data": [],
            "row_count": 0,
        }

        # Get columns
        info["columns"] = await self._get_columns(schema, table_name)

        # Get primary key
        info["primary_key"] = await self._get_primary_key(schema, table_name)

        # Get foreign keys
        info["foreign_keys"] = await self._get_foreign_keys(schema, table_name)

        # Get row count
        info["row_count"] = await self._get_row_count(schema, table_name)

        # Get sample data
        if sample_rows > 0:
            info["sample_data"] = await self._get_sample_data(schema, table_name, sample_rows)

        return info

    async def _extract_view_info(
        self,
        schema: str,
        view_name: str,
        sample_rows: int
    ) -> Dict[str, Any]:
        """Extract detailed information about a view"""
        info = {
            "columns": [],
            "sample_data": [],
            "row_count": 0,
        }

        # Get columns
        info["columns"] = await self._get_columns(schema, view_name)

        # Get sample data
        if sample_rows > 0:
            info["sample_data"] = await self._get_sample_data(schema, view_name, sample_rows)

        return info

    async def _get_columns(self, schema: str, table_name: str) -> List[Dict[str, Any]]:
        """Get column information for a table/view"""
        if self.db_type == "mssql":
            sql = f"""
                SELECT
                    c.COLUMN_NAME,
                    c.DATA_TYPE,
                    c.IS_NULLABLE,
                    c.COLUMN_DEFAULT,
                    c.CHARACTER_MAXIMUM_LENGTH,
                    c.NUMERIC_PRECISION,
                    c.NUMERIC_SCALE
                FROM INFORMATION_SCHEMA.COLUMNS c
                WHERE c.TABLE_SCHEMA = '{schema}'
                AND c.TABLE_NAME = '{table_name}'
                ORDER BY c.ORDINAL_POSITION
            """
        else:
            sql = f"""
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_DEFAULT,
                    CHARACTER_MAXIMUM_LENGTH,
                    NUMERIC_PRECISION,
                    NUMERIC_SCALE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{schema}'
                AND TABLE_NAME = '{table_name}'
                ORDER BY ORDINAL_POSITION
            """

        result = await self.execute_query(sql)

        columns = []
        for row in result["rows"]:
            # Rows are dicts with column names as keys
            columns.append({
                "name": row.get("COLUMN_NAME"),
                "data_type": row.get("DATA_TYPE"),
                "nullable": row.get("IS_NULLABLE") == "YES",
                "default": row.get("COLUMN_DEFAULT"),
                "max_length": row.get("CHARACTER_MAXIMUM_LENGTH"),
                "precision": row.get("NUMERIC_PRECISION"),
                "scale": row.get("NUMERIC_SCALE"),
            })

        return columns

    async def _get_primary_key(self, schema: str, table_name: str) -> List[str]:
        """Get primary key columns for a table"""
        if self.db_type == "mssql":
            sql = f"""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = '{schema}'
                AND TABLE_NAME = '{table_name}'
                AND CONSTRAINT_NAME LIKE 'PK_%'
                ORDER BY ORDINAL_POSITION
            """
        else:
            sql = f"""
                SELECT kcu.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                WHERE tc.TABLE_SCHEMA = '{schema}'
                AND tc.TABLE_NAME = '{table_name}'
                AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                ORDER BY kcu.ORDINAL_POSITION
            """

        result = await self.execute_query(sql)
        # Rows are dicts with column names as keys
        return [row.get("COLUMN_NAME") for row in result["rows"] if row.get("COLUMN_NAME")]

    async def _get_foreign_keys(self, schema: str, table_name: str) -> List[Dict[str, Any]]:
        """Get foreign key constraints for a table"""
        if self.db_type == "mssql":
            sql = f"""
                SELECT
                    fk.name AS constraint_name,
                    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
                    OBJECT_NAME(fkc.referenced_object_id) AS referenced_table,
                    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
                FROM sys.foreign_keys fk
                INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                WHERE OBJECT_NAME(fk.parent_object_id) = '{table_name}'
                AND OBJECT_SCHEMA_NAME(fk.parent_object_id) = '{schema}'
            """
        else:
            sql = f"""
                SELECT
                    tc.CONSTRAINT_NAME,
                    kcu.COLUMN_NAME,
                    ccu.TABLE_NAME AS referenced_table,
                    ccu.COLUMN_NAME AS referenced_column
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                    ON ccu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                AND tc.TABLE_SCHEMA = '{schema}'
                AND tc.TABLE_NAME = '{table_name}'
            """

        result = await self.execute_query(sql)

        fks = []
        for row in result["rows"]:
            # Rows are dicts with column names as keys
            fks.append({
                "constraint_name": row.get("constraint_name"),
                "column": row.get("column_name"),
                "referenced_table": row.get("referenced_table"),
                "referenced_column": row.get("referenced_column"),
            })

        return fks

    async def _get_relationships(self, schema: str) -> List[Dict[str, Any]]:
        """Get all foreign key relationships in schema"""
        if self.db_type == "mssql":
            sql = f"""
                SELECT
                    OBJECT_NAME(fk.parent_object_id) AS from_table,
                    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS from_column,
                    OBJECT_NAME(fkc.referenced_object_id) AS to_table,
                    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS to_column
                FROM sys.foreign_keys fk
                INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = '{schema}'
            """
        else:
            sql = f"""
                SELECT
                    tc.TABLE_NAME AS from_table,
                    kcu.COLUMN_NAME AS from_column,
                    ccu.TABLE_NAME AS to_table,
                    ccu.COLUMN_NAME AS to_column
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                    ON ccu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                AND tc.TABLE_SCHEMA = '{schema}'
            """

        result = await self.execute_query(sql)

        relationships = []
        for row in result["rows"]:
            # Rows are dicts with column names as keys
            relationships.append({
                "from_table": row.get("from_table"),
                "from_column": row.get("from_column"),
                "to_table": row.get("to_table"),
                "to_column": row.get("to_column"),
            })

        return relationships

    async def _get_row_count(self, schema: str, table_name: str) -> int:
        """Get approximate row count for a table"""
        if self.db_type == "mssql":
            # Use sys.partitions for fast approximate count
            sql = f"""
                SELECT SUM(p.rows) AS row_count
                FROM sys.tables t
                INNER JOIN sys.partitions p ON t.object_id = p.object_id
                WHERE t.name = '{table_name}'
                AND t.schema_id = SCHEMA_ID('{schema}')
                AND p.index_id IN (0, 1)
            """
        else:
            sql = f"SELECT COUNT(*) FROM [{schema}].[{table_name}]"

        try:
            result = await self.execute_query(sql)
            if result["rows"] and result["rows"][0]:
                # Rows are dicts - get the first value
                first_row = result["rows"][0]
                row_count = list(first_row.values())[0] if first_row else 0
                return int(row_count or 0)
        except Exception as e:
            logger.warning(f"Could not get row count for {table_name}: {e}")

        return 0

    async def _get_sample_data(
        self,
        schema: str,
        table_name: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get sample rows from a table"""
        if self.db_type == "mssql":
            sql = f"SELECT TOP {limit} * FROM [{schema}].[{table_name}]"
        elif self.db_type == "postgresql":
            sql = f'SELECT * FROM "{schema}"."{table_name}" LIMIT {limit}'
        else:
            sql = f"SELECT * FROM `{schema}`.`{table_name}` LIMIT {limit}"

        try:
            result = await self.execute_query(sql)

            # Gateway returns rows as list of dicts already
            rows = result.get("rows", [])

            sample_data = []
            for row in rows:
                # Row is already a dict - just sanitize values
                row_dict = {}
                for col, val in row.items():
                    if val is not None:
                        # Convert to string for serialization if needed
                        row_dict[col] = str(val) if not isinstance(val, (str, int, float, bool, type(None))) else val
                    else:
                        row_dict[col] = None
                sample_data.append(row_dict)

            return sample_data

        except Exception as e:
            logger.warning(f"Could not get sample data for {table_name}: {e}")
            return []
