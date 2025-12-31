"""
Schema Extractor
Automatically extracts database schema metadata from SQL Server
"""

from typing import List, Dict, Any, Optional
from sqlalchemy import text
from loguru import logger

from app.database.connection import get_db, init_database


class SchemaExtractor:
    """
    Extracts comprehensive schema information from SQL Server
    including tables, views, columns, data types, primary keys, and foreign keys
    """

    def __init__(self):
        """Initialize schema extractor"""
        init_database()
        self.db = next(get_db())

    def get_all_tables(self, schema: str = "dbo") -> List[str]:
        """
        Get list of all tables in the database

        Args:
            schema: Database schema name (default: dbo)

        Returns:
            List of table names
        """
        logger.info(f"Extracting tables from schema: {schema}")

        query = text("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = :schema
            AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)

        result = self.db.execute(query, {"schema": schema})
        tables = [row[0] for row in result]

        logger.info(f"[OK] Found {len(tables)} tables")
        return tables

    def get_all_views(self, schema: str = "dbo") -> List[str]:
        """
        Get list of all views in the database

        Args:
            schema: Database schema name (default: dbo)

        Returns:
            List of view names
        """
        logger.info(f"Extracting views from schema: {schema}")

        query = text("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = :schema
            AND TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_NAME
        """)

        result = self.db.execute(query, {"schema": schema})
        views = [row[0] for row in result]

        logger.info(f"[OK] Found {len(views)} views")
        return views

    def get_priority_views(self, schema: str = "dbo") -> List[str]:
        """
        Get list of priority views that should be indexed for SQL generation

        Args:
            schema: Database schema name (default: dbo)

        Returns:
            List of priority view names
        """
        # Priority views - 9 critical views identified by user
        # Tier 1: ALWAYS USE (Critical)
        priority_names = [
            'AllEmployeeUnion',                                    # Combines EmployeeMaster + EmployeeMaster_Deleted
            'vw_RawPunchDetail',                                   # Pre-joined punch records (9 tables)
            'vw_EmployeeMaster_Vms',                               # Complete employee details (18 JOINs)
            
            # Tier 2: HIGH PRIORITY
            'View_Visitor_EnrollmentDetail',                       # Visitor management (9 tables)
            'View_Contractor_Detail',                              # Contractor management
            'View_Employee_Terminal_Authentication_Relation',      # Access control
            'View_EmployeeByUserGroupPolicy',                      # User groups + biometrics
            
            # Tier 3: SPECIALIZED
            'Vw_TerminalDetail_VMS',                              # Terminal configuration
            'vw_VisitorBasicDetail'                               # Basic visitor lookups
        ]

        all_views = self.get_all_views(schema)

        # Filter to only views that exist
        priority_views = [v for v in all_views if v in priority_names]

        logger.info(f"[OK] Found {len(priority_views)} priority views out of {len(all_views)} total")
        return priority_views

    def extract_view_metadata(self, view_name: str, schema: str = "dbo") -> Dict[str, Any]:
        """
        Extract metadata for a database view

        Args:
            view_name: Name of the view
            schema: Database schema name (default: dbo)

        Returns:
            Dict containing view metadata including columns and base tables
        """
        logger.info(f"Extracting metadata for view {schema}.{view_name}")

        # Get view definition
        view_def_query = text("""
            SELECT VIEW_DEFINITION
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = :schema
            AND TABLE_NAME = :view_name
        """)

        result = self.db.execute(view_def_query, {"schema": schema, "view_name": view_name})
        view_definition = result.scalar() or ""

        # Extract base tables from view definition
        base_tables = self._extract_tables_from_view(view_definition)

        metadata = {
            "view_name": view_name,
            "schema": schema,
            "full_name": f"{schema}.{view_name}",
            "type": "VIEW",
            "columns": self._get_columns(view_name, schema),
            "base_tables": base_tables,
            "view_definition": view_definition[:500] if view_definition else None  # Truncate long definitions
        }

        return metadata

    def _extract_tables_from_view(self, view_definition: str) -> List[str]:
        """
        Extract base table names from view definition

        Args:
            view_definition: SQL definition of the view

        Returns:
            List of table names referenced in the view
        """
        import re

        # Simple pattern to match table references
        # Matches: FROM table, JOIN table, dbo.table, etc.
        pattern = r'(?:FROM|JOIN)\s+(?:dbo\.)?(\w+)'

        tables = re.findall(pattern, view_definition, re.IGNORECASE)

        # Remove duplicates and common SQL keywords that might match
        excluded = {'SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'VALUES'}
        unique_tables = list(set([t for t in tables if t.upper() not in excluded]))

        return unique_tables

    def extract_table_metadata(self, table_name: str, schema: str = "dbo") -> Dict[str, Any]:
        """
        Extract comprehensive metadata for a single table

        Args:
            table_name: Name of the table
            schema: Database schema name (default: dbo)

        Returns:
            Dict containing table metadata including columns, keys, and relationships
        """
        logger.info(f"Extracting metadata for {schema}.{table_name}")

        metadata = {
            "table_name": table_name,
            "schema": schema,
            "full_name": f"{schema}.{table_name}",
            "type": "TABLE",
            "columns": self._get_columns(table_name, schema),
            "primary_key": self._get_primary_key(table_name, schema),
            "foreign_keys": self._get_foreign_keys(table_name, schema),
            "indexes": self._get_indexes(table_name, schema)
        }

        return metadata

    def _get_columns(self, table_name: str, schema: str) -> List[Dict[str, Any]]:
        """
        Get all columns for a table with their data types and constraints

        Returns:
            List of column metadata dicts
        """
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

        result = self.db.execute(query, {"schema": schema, "table_name": table_name})

        columns = []
        for row in result:
            column = {
                "name": row[0],
                "data_type": row[1],
                "max_length": row[2],
                "nullable": row[3] == "YES",
                "default": row[4],
                "position": row[5]
            }
            columns.append(column)

        return columns

    def _get_primary_key(self, table_name: str, schema: str) -> Optional[List[str]]:
        """
        Get primary key columns for a table

        Returns:
            List of primary key column names, or None if no PK
        """
        query = text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsPrimaryKey') = 1
            AND TABLE_SCHEMA = :schema
            AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """)

        result = self.db.execute(query, {"schema": schema, "table_name": table_name})
        pk_columns = [row[0] for row in result]

        return pk_columns if pk_columns else None

    def _get_foreign_keys(self, table_name: str, schema: str) -> List[Dict[str, str]]:
        """
        Get foreign key relationships for a table

        Returns:
            List of foreign key relationship dicts
        """
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

        result = self.db.execute(query, {"schema": schema, "table_name": table_name})

        foreign_keys = []
        for row in result:
            fk = {
                "name": row[0],
                "column": row[1],
                "referenced_schema": row[2],
                "referenced_table": row[3],
                "referenced_column": row[4]
            }
            foreign_keys.append(fk)

        return foreign_keys

    def _get_indexes(self, table_name: str, schema: str) -> List[Dict[str, Any]]:
        """
        Get indexes for a table

        Returns:
            List of index metadata dicts
        """
        query = text("""
            SELECT 
                i.name AS INDEX_NAME,
                i.is_unique,
                COL_NAME(ic.object_id, ic.column_id) AS COLUMN_NAME
            FROM sys.indexes AS i
            INNER JOIN sys.index_columns AS ic 
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            WHERE i.object_id = OBJECT_ID(:full_table_name)
            AND i.index_id > 0
            ORDER BY i.name, ic.key_ordinal
        """)

        full_table_name = f"{schema}.{table_name}"
        result = self.db.execute(query, {"full_table_name": full_table_name})

        # Group columns by index name
        indexes_dict = {}
        for row in result:
            index_name = row[0]
            if index_name not in indexes_dict:
                indexes_dict[index_name] = {
                    "name": index_name,
                    "unique": bool(row[1]),
                    "columns": []
                }
            indexes_dict[index_name]["columns"].append(row[2])

        return list(indexes_dict.values())

    def extract_all_schemas(self, schema: str = "dbo", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extract metadata for all tables in the database

        Args:
            schema: Database schema name (default: dbo)
            limit: Optional limit on number of tables to extract (for testing)

        Returns:
            List of table metadata dicts
        """
        logger.info(f"Extracting all table schemas from {schema}")

        tables = self.get_all_tables(schema)

        if limit:
            tables = tables[:limit]
            logger.info(f"Limiting to first {limit} tables")

        all_metadata = []
        for table in tables:
            try:
                metadata = self.extract_table_metadata(table, schema)
                all_metadata.append(metadata)
            except Exception as e:
                logger.error(f"[ERROR] Failed to extract metadata for {table}: {str(e)}")

        logger.info(f"[OK] Successfully extracted metadata for {len(all_metadata)} tables")
        return all_metadata


# Singleton instance
schema_extractor = SchemaExtractor()
