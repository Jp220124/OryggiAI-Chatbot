"""
View Schema Enricher
Creates rich documentation for database views with usage guidelines and examples
"""

from typing import Dict, Any, List
from loguru import logger

from app.database import db_manager
from app.rag.view_definitions import VIEW_DEFINITIONS, DEPRECATED_TABLES


class ViewSchemaEnricher:
    """
    Creates enriched schema documentation for database views
    Includes purpose, columns, use cases, and sample queries
    """

    def create_enriched_view_document(self, view_name: str) -> str:
        """
        Create rich documentation for a view

        Args:
            view_name: Name of the view

        Returns:
            Enriched text document describing the view
        """
        if view_name not in VIEW_DEFINITIONS:
            logger.warning(f"View {view_name} not found in VIEW_DEFINITIONS")
            return self._create_basic_view_document(view_name)

        view_def = VIEW_DEFINITIONS[view_name]

        doc = f"VIEW: dbo.{view_name} {view_def['rating']}\n"
        doc += f"TIER: {view_def['tier']} (Priority: {view_def['priority']})\n\n"

        # Purpose
        doc += f"PURPOSE:\n{view_def['purpose']}\n\n"

        # Pre-joined tables (if available)
        if "pre_joins" in view_def:
            doc += f"PRE-JOINS ({len(view_def['pre_joins'])} tables):\n"
            doc += f"{', '.join(view_def['pre_joins'])}\n\n"

        # Key columns
        if "key_columns" in view_def:
            doc += "KEY COLUMNS:\n"
            for category, columns in view_def["key_columns"].items():
                doc += f"  {category}: {', '.join(columns)}\n"
            doc += "\n"

        # Always use for
        doc += "ALWAYS USE FOR:\n"
        for use_case in view_def["always_use_for"]:
            doc += f"  [OK] {use_case}\n"
        doc += "\n"

        # Critical filters (if available)
        if "critical_filters" in view_def:
            doc += "CRITICAL FILTERS:\n"
            for filter_example in view_def["critical_filters"]:
                doc += f"  {filter_example}\n"
            doc += "\n"

        # Sample queries
        if "sample_queries" in view_def:
            doc += "COMMON QUERY PATTERNS:\n"
            for i, query_example in enumerate(view_def["sample_queries"], 1):
                doc += f"\n  Example {i}:\n"
                doc += f"  Question: \"{query_example['question']}\"\n"
                doc += f"  SQL: {query_example['sql']}\n"
            doc += "\n"

        # Do not use warnings
        if "do_not_use" in view_def:
            doc += "[WARNING] IMPORTANT WARNINGS:\n"
            for warning in view_def["do_not_use"]:
                doc += f"  {warning}\n"
            doc += "\n"

        return doc

    def _create_basic_view_document(self, view_name: str) -> str:
        """
        Create basic documentation for views not in VIEW_DEFINITIONS

        Args:
            view_name: Name of the view

        Returns:
            Basic text document describing the view
        """
        try:
            # Get view columns
            columns_query = f"""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{view_name}'
                ORDER BY ORDINAL_POSITION
            """
            columns = db_manager.execute_query(columns_query)

            doc = f"VIEW: dbo.{view_name}\n\n"
            doc += f"COLUMNS ({len(columns)} total):\n"
            for col in columns[:20]:  # Limit to first 20 columns
                doc += f"  • {col['COLUMN_NAME']} ({col['DATA_TYPE']})\n"

            if len(columns) > 20:
                doc += f"  ... and {len(columns) - 20} more columns\n"

            return doc

        except Exception as e:
            logger.error(f"Failed to create basic view document for {view_name}: {e}")
            return f"VIEW: dbo.{view_name}\n\nNo additional information available.\n"

    def create_deprecated_table_document(self, table_name: str) -> str:
        """
        Create documentation for deprecated tables (with warnings)

        Args:
            table_name: Name of the deprecated table

        Returns:
            Warning document for deprecated table
        """
        if table_name not in DEPRECATED_TABLES:
            return ""

        deprecated_info = DEPRECATED_TABLES[table_name]

        doc = f"TABLE: dbo.{table_name}\n\n"
        doc += "[WARNING][WARNING][WARNING] DEPRECATED / DO NOT USE [WARNING][WARNING][WARNING]\n\n"
        doc += f"REASON: {deprecated_info['reason']}\n\n"
        doc += f"REPLACEMENT: {deprecated_info['replacement']}\n\n"
        doc += "DO NOT generate queries using this table!\n"

        return doc

    def get_view_metadata(self, view_name: str) -> Dict[str, Any]:
        """
        Get metadata for a view (for ChromaDB storage)

        Args:
            view_name: Name of the view

        Returns:
            Metadata dictionary
        """
        if view_name not in VIEW_DEFINITIONS:
            return {
                "table_name": view_name,
                "type": "view",
                "priority": 1,
                "tier": 3
            }

        view_def = VIEW_DEFINITIONS[view_name]

        return {
            "table_name": view_name,
            "type": "view",
            "priority": view_def["priority"],
            "tier": view_def["tier"],
            "rating": view_def["rating"],
            "is_tier1": view_def["tier"] == 1
        }

    def get_all_tier1_views(self) -> List[str]:
        """Get list of Tier 1 view names"""
        return [
            name for name, details in VIEW_DEFINITIONS.items()
            if details["tier"] == 1
        ]

    def should_always_include_view(self, question: str, view_name: str) -> bool:
        """
        Determine if a view should always be included based on question keywords

        Args:
            question: User's question
            view_name: Name of the view to check

        Returns:
            True if view should be force-included in context
        """
        if view_name not in VIEW_DEFINITIONS:
            return False

        view_def = VIEW_DEFINITIONS[view_name]
        question_lower = question.lower()

        # Check use case keywords
        for use_case in view_def["always_use_for"]:
            use_case_keywords = use_case.lower().split()
            if any(keyword in question_lower for keyword in use_case_keywords):
                return True

        # Specific keyword matching
        keyword_map = {
            "vw_EmployeeMaster_Vms": ["employee", "department", "section", "branch", "organizational"],
            "vw_RawPunchDetail": ["attendance", "punch", "time", "in time", "out time", "work hour"],
            "AllEmployeeUnion": ["total employee", "all employee", "employee count"],
            "View_Visitor_EnrollmentDetail": ["visitor"],
            "View_Contractor_Detail": ["contractor"],
            "View_Employee_Terminal_Authentication_Relation": ["access", "terminal permission", "authorization"],
            "Vw_TerminalDetail_VMS": ["device", "terminal", "online", "offline"],
        }

        if view_name in keyword_map:
            return any(keyword in question_lower for keyword in keyword_map[view_name])

        return False


# Global enricher instance
view_enricher = ViewSchemaEnricher()
