"""
Database Schema Indexer (VIEW-FIRST Architecture)
Prioritizes database views over base tables for better query accuracy
"""

from typing import List, Dict, Any
from loguru import logger
import json

from app.database import db_manager
from app.rag.faiss_manager import faiss_manager
from app.rag.chroma_manager import chroma_manager
from app.rag.view_definitions import VIEW_DEFINITIONS, get_all_view_names, DEPRECATED_TABLES
from app.rag.view_schema_enricher import view_enricher
from app.rag.table_definitions import (
    TABLE_DEFINITIONS, get_table_definition, create_table_document, get_table_priority
)


class SchemaIndexer:
    """
    Indexes database schema into vector store (VIEW-FIRST approach)
    Prioritizes views with rich documentation, base tables as fallback
    """

    def __init__(self):
        """Initialize schema indexer"""
        self.tables_info: List[Dict[str, Any]] = []
        self.views_info: List[Dict[str, Any]] = []

    def extract_schema(self, views_only: bool = False) -> List[Dict[str, Any]]:
        """
        Extract database schema with VIEW-FIRST priority

        Args:
            views_only: If True, only extract views (ignore base tables)

        Returns:
            List of table/view information dictionaries
        """
        logger.info("=" * 80)
        logger.info("EXTRACTING DATABASE SCHEMA (VIEW-FIRST ARCHITECTURE)")
        logger.info("=" * 80)

        try:
            # STEP 1: Extract critical views FIRST
            self._extract_critical_views()

            # STEP 2: Extract additional views (not in VIEW_DEFINITIONS)
            if not views_only:
                self._extract_other_views()

            # STEP 3: Extract base tables (as fallback) - only if not views_only
            if not views_only:
                self._extract_base_tables()

            total_extracted = len(self.views_info) + len(self.tables_info)
            logger.info(f"[OK] Extracted schema: {len(self.views_info)} views + {len(self.tables_info)} tables = {total_extracted} total")

            return self.views_info + self.tables_info

        except Exception as e:
            logger.error(f"[ERROR] Schema extraction failed: {str(e)}")
            raise

    def _extract_critical_views(self):
        """Extract the 9 critical views from VIEW_DEFINITIONS"""
        logger.info("Extracting CRITICAL VIEWS (Tier 1-3)...")

        view_names = get_all_view_names()
        self.views_info = []

        for view_name in view_names:
            try:
                view_info = self._extract_view_info(view_name)
                self.views_info.append(view_info)
                tier = VIEW_DEFINITIONS[view_name]["tier"]
                rating = VIEW_DEFINITIONS[view_name]["rating"]
                logger.info(f"  [OK] {view_name} {rating} (Tier {tier})")
            except Exception as e:
                logger.warning(f"  [ERROR] Failed to extract {view_name}: {e}")

        logger.info(f"[OK] Extracted {len(self.views_info)} critical views")

    def _extract_other_views(self):
        """Extract other database views not in VIEW_DEFINITIONS"""
        logger.info("Extracting additional views...")

        try:
            critical_view_names = get_all_view_names()

            views_query = """
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_CATALOG = DB_NAME()
                ORDER BY TABLE_NAME
            """

            all_views = db_manager.execute_query(views_query)
            other_views = [
                v["TABLE_NAME"] for v in all_views
                if v["TABLE_NAME"] not in critical_view_names
            ]

            logger.info(f"Found {len(other_views)} additional views")

            for view_name in other_views[:20]:  # Limit to 20 additional views
                try:
                    view_info = self._extract_view_info(view_name, is_critical=False)
                    self.views_info.append(view_info)
                except Exception as e:
                    logger.debug(f"  Skipped {view_name}: {e}")

            logger.info(f"[OK] Extracted {len(other_views[:20])} additional views")

        except Exception as e:
            logger.warning(f"Failed to extract additional views: {e}")

    def _extract_base_tables(self):
        """Extract base tables (as fallback for queries not covered by views)"""
        logger.info("Extracting base tables (fallback)...")

        try:
            tables_query = """
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                    AND TABLE_CATALOG = DB_NAME()
                ORDER BY TABLE_NAME
            """

            tables = db_manager.execute_query(tables_query)
            logger.info(f"Found {len(tables)} base tables")

            self.tables_info = []

            for table in tables[:50]:  # Limit to 50 tables
                table_name = table["TABLE_NAME"]

                # Skip deprecated tables
                if table_name in DEPRECATED_TABLES:
                    logger.warning(f"  [WARNING] SKIPPED {table_name} (DEPRECATED)")
                    continue

                try:
                    table_info = self._extract_table_info(table_name)
                    self.tables_info.append(table_info)
                except Exception as e:
                    logger.debug(f"  Skipped {table_name}: {e}")

            logger.info(f"[OK] Extracted {len(self.tables_info)} base tables")

        except Exception as e:
            logger.error(f"Failed to extract base tables: {e}")
            raise

    def _extract_view_info(self, view_name: str, is_critical: bool = True) -> Dict[str, Any]:
        """
        Extract information for a database view

        Args:
            view_name: Name of the view
            is_critical: Whether this is a critical view from VIEW_DEFINITIONS

        Returns:
            Dictionary with view information
        """
        # Get view columns
        columns_query = f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{view_name}'
            ORDER BY ORDINAL_POSITION
        """

        columns = db_manager.execute_query(columns_query)
        column_names = [col["COLUMN_NAME"] for col in columns]
        column_types = {col["COLUMN_NAME"]: col["DATA_TYPE"] for col in columns}

        return {
            "table_name": view_name,
            "columns": column_names,
            "column_types": column_types,
            "type": "view",
            "is_critical": is_critical,
            "priority": VIEW_DEFINITIONS.get(view_name, {}).get("priority", 1)
        }

    def _extract_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Extract detailed information for a single table

        Args:
            table_name: Name of the table

        Returns:
            Dictionary with table metadata
        """
        # Get column information
        columns_query = f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM
                INFORMATION_SCHEMA.COLUMNS
            WHERE
                TABLE_NAME = '{table_name}'
            ORDER BY
                ORDINAL_POSITION
        """

        columns = db_manager.execute_query(columns_query)

        column_names = [col["COLUMN_NAME"] for col in columns]
        column_types = {
            col["COLUMN_NAME"]: col["DATA_TYPE"]
            for col in columns
        }

        # Get primary key
        pk_query = f"""
            SELECT
                COLUMN_NAME
            FROM
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE
                TABLE_NAME = '{table_name}'
                AND CONSTRAINT_NAME LIKE 'PK_%'
        """

        pk_result = db_manager.execute_query(pk_query)
        primary_key = pk_result[0]["COLUMN_NAME"] if pk_result else None

        # Get foreign keys
        fk_query = f"""
            SELECT
                kcu.COLUMN_NAME,
                kcu2.TABLE_NAME AS REFERENCED_TABLE,
                kcu2.COLUMN_NAME AS REFERENCED_COLUMN
            FROM
                INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            INNER JOIN
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            INNER JOIN
                INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2
                ON rc.UNIQUE_CONSTRAINT_NAME = kcu2.CONSTRAINT_NAME
            WHERE
                kcu.TABLE_NAME = '{table_name}'
        """

        foreign_keys = db_manager.execute_query(fk_query)

        # Get sample data (first 3 rows)
        try:
            sample_query = f"SELECT TOP 3 * FROM {table_name}"
            sample_data = db_manager.execute_query(sample_query)
        except:
            sample_data = []

        return {
            "table_name": table_name,
            "columns": column_names,
            "column_types": column_types,
            "primary_key": primary_key,
            "foreign_keys": foreign_keys,
            "sample_data": sample_data,
            "row_count": len(sample_data)
        }

    def create_embeddings(self) -> int:
        """
        Create and store embeddings for views and tables (VIEW-FIRST)

        Returns:
            Number of embeddings created
        """
        logger.info("=" * 80)
        logger.info("CREATING EMBEDDINGS (VIEW-FIRST ARCHITECTURE)")
        logger.info("=" * 80)

        documents = []
        metadatas = []
        ids = []

        # STEP 1: Create enriched embeddings for VIEWS
        logger.info(f"Creating enriched embeddings for {len(self.views_info)} views...")

        for view_info in self.views_info:
            view_name = view_info["table_name"]
            is_critical = view_info.get("is_critical", False)

            # Use enriched documentation for critical views
            if is_critical:
                doc_text = view_enricher.create_enriched_view_document(view_name)
                logger.info(f"  [OK] {view_name} (ENRICHED)")
            else:
                doc_text = view_enricher._create_basic_view_document(view_name)

            documents.append(doc_text)

            # Create metadata with priority
            metadata = view_enricher.get_view_metadata(view_name)
            metadatas.append(metadata)

            # Create unique ID
            ids.append(f"view_{view_name}")

        # STEP 2: Create embeddings for BASE TABLES (with enriched definitions when available)
        logger.info(f"Creating embeddings for {len(self.tables_info)} base tables...")

        enriched_count = 0
        for table_info in self.tables_info:
            table_name = table_info["table_name"]

            # Create text description (enriched if available)
            doc_text = self._create_table_document(table_info)
            documents.append(doc_text)

            # Check if this table has enriched definition
            is_enriched = table_name in TABLE_DEFINITIONS
            if is_enriched:
                enriched_count += 1
                table_def = TABLE_DEFINITIONS[table_name]
                priority = table_def.get("priority", 2)
                category = table_def.get("category", "general")
                logger.info(f"  [OK] {table_name} (ENRICHED - {category})")
            else:
                priority = 1
                category = "general"

            # Create metadata with appropriate priority
            metadata = {
                "table_name": table_name,
                "column_count": len(table_info["columns"]),
                "type": "table",
                "priority": priority,
                "category": category,
                "is_enriched": is_enriched,
                "has_foreign_keys": len(table_info.get("foreign_keys", [])) > 0
            }
            metadatas.append(metadata)

            # Create unique ID
            ids.append(f"table_{table_name}")

        logger.info(f"  {enriched_count} tables with enriched documentation")

        # STEP 3: Add to ChromaDB
        logger.info(f"Adding {len(documents)} embeddings to ChromaDB...")
        chroma_manager.add_schema_embeddings(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        logger.info("=" * 80)
        logger.info(f"[YES] EMBEDDINGS CREATED: {len(documents)} total")
        logger.info(f"   - {len(self.views_info)} views (enriched documentation)")
        logger.info(f"   - {len(self.tables_info)} tables (basic documentation)")
        logger.info("=" * 80)

        return len(documents)

    def _create_table_document(self, table_info: Dict[str, Any]) -> str:
        """
        Create rich text document for table schema
        Uses enriched definitions from table_definitions.py when available

        Args:
            table_info: Table information dictionary

        Returns:
            Text document describing the table
        """
        table_name = table_info["table_name"]
        columns = table_info["columns"]
        column_types = table_info["column_types"]
        primary_key = table_info["primary_key"]
        foreign_keys = table_info["foreign_keys"]

        # Check if we have a rich definition for this table
        if table_name in TABLE_DEFINITIONS:
            # Use enriched documentation
            doc = create_table_document(table_name)

            # Append actual column list from database
            doc += f"\nACTUAL COLUMNS ({len(columns)}):\n"
            for col in columns[:30]:  # Limit to 30 columns
                col_type = column_types.get(col, "unknown")
                doc += f"  - {col} ({col_type})\n"

            if len(columns) > 30:
                doc += f"  ... and {len(columns) - 30} more columns\n"

            # Add primary key
            if primary_key:
                doc += f"\nPRIMARY KEY: {primary_key}\n"

            # Add foreign keys from database
            if foreign_keys:
                doc += "\nFOREIGN KEYS (from database):\n"
                for fk in foreign_keys:
                    doc += f"  {fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE']}.{fk['REFERENCED_COLUMN']}\n"

            return doc

        # Fallback: Build basic descriptive text for tables without rich definitions
        doc = f"TABLE: dbo.{table_name}\n\n"
        doc += f"Primary Key: {primary_key}\n" if primary_key else ""
        doc += f"Columns ({len(columns)}): {', '.join(columns[:20])}\n"

        if len(columns) > 20:
            doc += f"  ... and {len(columns) - 20} more columns\n"

        # Add column types
        col_type_str = ", ".join([f"{col}:{column_types.get(col, 'unknown')}" for col in columns[:10]])
        doc += f"Column Types: {col_type_str}\n"

        # Add foreign keys
        if foreign_keys:
            fk_str = ", ".join([
                f"{fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE']}.{fk['REFERENCED_COLUMN']}"
                for fk in foreign_keys
            ])
            doc += f"Foreign Keys: {fk_str}\n"

        # Add sample data context (first row if available)
        if table_info.get("sample_data"):
            sample = table_info["sample_data"][0]
            sample_str = ", ".join([f"{k}={v}" for k, v in list(sample.items())[:5]])
            doc += f"Sample Data: {sample_str}\n"

        return doc

    def _create_column_document(
        self,
        table_name: str,
        column_name: str,
        column_type: str
    ) -> str:
        """
        Create document for individual column

        Args:
            table_name: Name of table
            column_name: Name of column
            column_type: Data type of column

        Returns:
            Text document describing the column
        """
        return (
            f"Column: {column_name} in table {table_name}. "
            f"Type: {column_type}. "
            f"Use this for queries about {column_name.lower()} data."
        )

    def reindex(self, views_only: bool = False):
        """
        Delete existing embeddings and re-index database schema
        Use this when schema changes

        Args:
            views_only: If True, only index views (ignore base tables)
        """
        logger.info("=" * 80)
        logger.info("RE-INDEXING DATABASE SCHEMA (VIEW-FIRST)")
        logger.info("=" * 80)

        # Delete all existing embeddings
        chroma_manager.delete_all()

        # Extract and index with VIEW-FIRST strategy
        self.extract_schema(views_only=views_only)
        count = self.create_embeddings()

        logger.info("=" * 80)
        logger.info(f"[YES] RE-INDEXING COMPLETE: {count} embeddings created")
        logger.info("=" * 80)
        return count


# Global schema indexer instance
schema_indexer = SchemaIndexer()


def index_database_schema(views_only: bool = False):
    """
    Convenience function to index database schema (VIEW-FIRST)
    Called during application startup or manually

    Args:
        views_only: If True, only index critical views (ignore base tables)
    """
    logger.info("=" * 80)
    logger.info("INDEXING DATABASE SCHEMA (VIEW-FIRST ARCHITECTURE)")
    logger.info("=" * 80)

    try:
        # Initialize managers
        if not db_manager._initialized:
            from app.database import init_database
            init_database()

        if not chroma_manager._initialized:
            chroma_manager.initialize()

        # Extract and index with VIEW-FIRST strategy
        schema_indexer.extract_schema(views_only=views_only)
        count = schema_indexer.create_embeddings()

        # Show stats
        stats = chroma_manager.get_collection_stats()

        logger.info("=" * 80)
        logger.info(f"[YES] SCHEMA INDEXING COMPLETE!")
        logger.info(f"  Total embeddings: {stats['count']}")
        logger.info(f"  Critical views: {len([v for v in schema_indexer.views_info if v.get('is_critical')])}")
        logger.info(f"  Other views: {len([v for v in schema_indexer.views_info if not v.get('is_critical')])}")
        logger.info(f"  Base tables: {len(schema_indexer.tables_info)}")
        logger.info("=" * 80)

        return count

    except Exception as e:
        logger.error(f"[ERROR] Schema indexing failed: {str(e)}")
        raise


if __name__ == "__main__":
    # Allow running as standalone script
    index_database_schema()
