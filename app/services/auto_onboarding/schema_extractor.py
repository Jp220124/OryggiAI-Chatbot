"""
Auto Schema Extractor
Automatically extracts complete database schema with sample data
Supports multiple database types: MS SQL Server, PostgreSQL, MySQL
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from loguru import logger


class AutoSchemaExtractor:
    """
    Automatically extracts complete database schema including:
    - All tables and views
    - Column definitions (name, type, nullable, defaults)
    - Primary keys and foreign keys
    - Sample data (for LLM context)
    - Row counts
    - Relationships between tables
    """

    def __init__(self, connection_string: str):
        """
        Initialize schema extractor with database connection

        Args:
            connection_string: SQLAlchemy-compatible connection string
                Examples:
                - mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server
                - postgresql://user:pass@server/db
                - mysql://user:pass@server/db
        """
        self.connection_string = connection_string
        self.engine: Optional[Engine] = None
        self.db_type: str = self._detect_db_type(connection_string)

    def _detect_db_type(self, connection_string: str) -> str:
        """Detect database type from connection string"""
        conn_lower = connection_string.lower()
        if 'mssql' in conn_lower or 'pyodbc' in conn_lower:
            return 'mssql'
        elif 'postgresql' in conn_lower or 'postgres' in conn_lower:
            return 'postgresql'
        elif 'mysql' in conn_lower:
            return 'mysql'
        else:
            return 'unknown'

    def connect(self) -> bool:
        """
        Establish database connection

        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to {self.db_type} database...")
            self.engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )

            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("Database connection established")
            return True

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    async def extract_full_schema(
        self,
        schema: str = "dbo",
        include_views: bool = True,
        sample_rows: int = 5,
        max_tables: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract complete schema from database - FULLY AUTOMATIC

        Args:
            schema: Database schema name (default: dbo for SQL Server)
            include_views: Whether to include views (default: True)
            sample_rows: Number of sample rows to fetch per table (default: 5)
            max_tables: Optional limit on tables (for testing)

        Returns:
            Complete schema dictionary with:
            {
                "tables": {...},
                "views": {...},
                "relationships": [...],
                "statistics": {...}
            }
        """
        if not self.engine:
            self.connect()

        result = {
            "tables": {},
            "views": {},
            "relationships": [],
            "statistics": {
                "total_tables": 0,
                "total_views": 0,
                "total_columns": 0,
                "total_relationships": 0,
                "total_rows_sampled": 0
            }
        }

        try:
            # Get all tables
            tables = self._get_tables(schema)
            if max_tables:
                tables = tables[:max_tables]

            logger.info(f"Found {len(tables)} tables to extract")

            # Extract each table
            for table_name in tables:
                try:
                    table_meta = await self._extract_table_metadata(
                        table_name, schema, sample_rows
                    )
                    result["tables"][table_name] = table_meta
                    result["statistics"]["total_columns"] += len(table_meta["columns"])

                    # Track relationships
                    for fk in table_meta.get("foreign_keys", []):
                        result["relationships"].append({
                            "from_table": table_name,
                            "from_column": fk["column"],
                            "to_table": fk["referenced_table"],
                            "to_column": fk["referenced_column"]
                        })

                except Exception as e:
                    logger.warning(f"Failed to extract {table_name}: {e}")
                    continue

            result["statistics"]["total_tables"] = len(result["tables"])
            result["statistics"]["total_relationships"] = len(result["relationships"])

            # Get views if requested
            if include_views:
                views = self._get_views(schema)
                logger.info(f"Found {len(views)} views to extract")

                for view_name in views:
                    try:
                        view_meta = await self._extract_view_metadata(
                            view_name, schema, sample_rows
                        )
                        result["views"][view_name] = view_meta
                    except Exception as e:
                        logger.warning(f"Failed to extract view {view_name}: {e}")
                        continue

                result["statistics"]["total_views"] = len(result["views"])

            logger.info(f"Schema extraction complete: {result['statistics']}")
            return result

        except Exception as e:
            logger.error(f"Schema extraction failed: {e}")
            raise

    def _get_tables(self, schema: str) -> List[str]:
        """Get list of all tables"""
        if self.db_type == 'mssql':
            query = text("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = :schema
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
        elif self.db_type == 'postgresql':
            query = text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
        else:
            # MySQL
            query = text("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = :schema
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"schema": schema})
            return [row[0] for row in result]

    def _get_views(self, schema: str) -> List[str]:
        """Get list of all views"""
        if self.db_type == 'mssql':
            query = text("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_SCHEMA = :schema
                ORDER BY TABLE_NAME
            """)
        else:
            query = text("""
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = :schema
                ORDER BY table_name
            """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"schema": schema})
            return [row[0] for row in result]

    async def _extract_table_metadata(
        self,
        table_name: str,
        schema: str,
        sample_rows: int
    ) -> Dict[str, Any]:
        """Extract complete metadata for a single table"""

        metadata = {
            "name": table_name,
            "schema": schema,
            "full_name": f"{schema}.{table_name}",
            "type": "TABLE",
            "columns": [],
            "primary_key": [],
            "foreign_keys": [],
            "indexes": [],
            "sample_data": [],
            "row_count": 0
        }

        # Get columns
        metadata["columns"] = self._get_columns(table_name, schema)

        # Get primary key
        metadata["primary_key"] = self._get_primary_key(table_name, schema)

        # Get foreign keys
        metadata["foreign_keys"] = self._get_foreign_keys(table_name, schema)

        # Get indexes
        metadata["indexes"] = self._get_indexes(table_name, schema)

        # Get row count
        metadata["row_count"] = self._get_row_count(table_name, schema)

        # Get sample data (for LLM context)
        metadata["sample_data"] = self._get_sample_data(
            table_name, schema, sample_rows
        )

        return metadata

    async def _extract_view_metadata(
        self,
        view_name: str,
        schema: str,
        sample_rows: int
    ) -> Dict[str, Any]:
        """Extract metadata for a view"""

        metadata = {
            "name": view_name,
            "schema": schema,
            "full_name": f"{schema}.{view_name}",
            "type": "VIEW",
            "columns": [],
            "base_tables": [],
            "sample_data": [],
            "definition_preview": ""
        }

        # Get columns
        metadata["columns"] = self._get_columns(view_name, schema)

        # Get view definition and extract base tables
        view_def = self._get_view_definition(view_name, schema)
        metadata["definition_preview"] = view_def[:500] if view_def else ""
        metadata["base_tables"] = self._extract_base_tables(view_def)

        # Get sample data
        metadata["sample_data"] = self._get_sample_data(
            view_name, schema, sample_rows
        )

        return metadata

    def _get_columns(self, table_name: str, schema: str) -> List[Dict[str, Any]]:
        """Get all columns for a table/view"""
        query = text("""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :schema
            AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"schema": schema, "table_name": table_name})
            return [
                {
                    "name": row[0],
                    "data_type": row[1],
                    "max_length": row[2],
                    "nullable": row[3] == "YES",
                    "default": str(row[4]) if row[4] else None,
                    "position": row[5]
                }
                for row in result
            ]

    def _get_primary_key(self, table_name: str, schema: str) -> List[str]:
        """Get primary key columns"""
        if self.db_type == 'mssql':
            query = text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE OBJECTPROPERTY(
                    OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME),
                    'IsPrimaryKey'
                ) = 1
                AND TABLE_SCHEMA = :schema
                AND TABLE_NAME = :table_name
                ORDER BY ORDINAL_POSITION
            """)
        else:
            query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = :schema
                AND tc.table_name = :table_name
                ORDER BY kcu.ordinal_position
            """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"schema": schema, "table_name": table_name})
            return [row[0] for row in result]

    def _get_foreign_keys(self, table_name: str, schema: str) -> List[Dict[str, str]]:
        """Get foreign key relationships"""
        if self.db_type == 'mssql':
            query = text("""
                SELECT
                    fk.name AS FK_NAME,
                    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS FK_COLUMN,
                    OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS REFERENCED_SCHEMA,
                    OBJECT_NAME(fk.referenced_object_id) AS REFERENCED_TABLE,
                    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS REFERENCED_COLUMN
                FROM sys.foreign_keys AS fk
                INNER JOIN sys.foreign_key_columns AS fkc
                    ON fk.object_id = fkc.constraint_object_id
                WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = :schema
                AND OBJECT_NAME(fk.parent_object_id) = :table_name
            """)
        else:
            query = text("""
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_schema,
                    ccu.table_name,
                    ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = :schema
                AND tc.table_name = :table_name
            """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"schema": schema, "table_name": table_name})
            return [
                {
                    "name": row[0],
                    "column": row[1],
                    "referenced_schema": row[2],
                    "referenced_table": row[3],
                    "referenced_column": row[4]
                }
                for row in result
            ]

    def _get_indexes(self, table_name: str, schema: str) -> List[Dict[str, Any]]:
        """Get indexes for a table"""
        if self.db_type == 'mssql':
            query = text("""
                SELECT
                    i.name AS INDEX_NAME,
                    i.is_unique,
                    i.is_primary_key,
                    COL_NAME(ic.object_id, ic.column_id) AS COLUMN_NAME
                FROM sys.indexes AS i
                INNER JOIN sys.index_columns AS ic
                    ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                WHERE i.object_id = OBJECT_ID(:full_name)
                AND i.index_id > 0
                ORDER BY i.name, ic.key_ordinal
            """)

            full_name = f"{schema}.{table_name}"

            with self.engine.connect() as conn:
                result = conn.execute(query, {"full_name": full_name})

                # Group columns by index
                indexes_dict = {}
                for row in result:
                    index_name = row[0]
                    if index_name not in indexes_dict:
                        indexes_dict[index_name] = {
                            "name": index_name,
                            "unique": bool(row[1]),
                            "primary": bool(row[2]),
                            "columns": []
                        }
                    indexes_dict[index_name]["columns"].append(row[3])

                return list(indexes_dict.values())

        return []  # Simplified for other DBs

    def _get_row_count(self, table_name: str, schema: str) -> int:
        """Get approximate row count"""
        try:
            # Use APPROX for large tables (SQL Server)
            if self.db_type == 'mssql':
                query = text("""
                    SELECT SUM(p.rows) AS row_count
                    FROM sys.partitions p
                    JOIN sys.tables t ON p.object_id = t.object_id
                    WHERE t.name = :table_name
                    AND SCHEMA_NAME(t.schema_id) = :schema
                    AND p.index_id IN (0, 1)
                """)
            else:
                query = text(f"SELECT COUNT(*) FROM {schema}.{table_name}")

            with self.engine.connect() as conn:
                result = conn.execute(query, {"table_name": table_name, "schema": schema})
                count = result.scalar()
                return int(count) if count else 0

        except Exception:
            return 0

    def _get_sample_data(
        self,
        table_name: str,
        schema: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get sample rows from table"""
        try:
            if self.db_type == 'mssql':
                query = text(f"SELECT TOP {limit} * FROM [{schema}].[{table_name}]")
            else:
                query = text(f"SELECT * FROM {schema}.{table_name} LIMIT {limit}")

            with self.engine.connect() as conn:
                result = conn.execute(query)
                columns = result.keys()

                samples = []
                for row in result:
                    sample = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # Convert to JSON-serializable format
                        if value is not None:
                            if hasattr(value, 'isoformat'):
                                value = value.isoformat()
                            else:
                                value = str(value)
                        sample[col] = value
                    samples.append(sample)

                return samples

        except Exception as e:
            logger.warning(f"Failed to get sample data for {table_name}: {e}")
            return []

    def _get_view_definition(self, view_name: str, schema: str) -> str:
        """Get SQL definition of a view"""
        try:
            if self.db_type == 'mssql':
                query = text("""
                    SELECT VIEW_DEFINITION
                    FROM INFORMATION_SCHEMA.VIEWS
                    WHERE TABLE_SCHEMA = :schema
                    AND TABLE_NAME = :view_name
                """)
            else:
                query = text("""
                    SELECT view_definition
                    FROM information_schema.views
                    WHERE table_schema = :schema
                    AND table_name = :view_name
                """)

            with self.engine.connect() as conn:
                result = conn.execute(query, {"schema": schema, "view_name": view_name})
                return result.scalar() or ""

        except Exception:
            return ""

    def _extract_base_tables(self, view_definition: str) -> List[str]:
        """Extract base table names from view definition"""
        import re

        if not view_definition:
            return []

        # Match FROM table or JOIN table patterns
        pattern = r'(?:FROM|JOIN)\s+(?:\[?dbo\]?\.)?(?:\[)?(\w+)(?:\])?'
        tables = re.findall(pattern, view_definition, re.IGNORECASE)

        # Remove duplicates and SQL keywords
        excluded = {'SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'VALUES'}
        unique_tables = list(set([t for t in tables if t.upper() not in excluded]))

        return unique_tables

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
