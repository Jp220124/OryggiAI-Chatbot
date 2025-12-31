"""
LLM Schema Analyzer
Uses Google Gemini to understand what the database is about
Automatically detects organization type, modules, and relationships
"""

import json
import re
from typing import Dict, Any, List
import google.generativeai as genai
from loguru import logger

from app.config import settings


class LLMSchemaAnalyzer:
    """
    Uses LLM (Google Gemini) to understand database schema semantically

    Automatically detects:
    - Organization type (University, Hospital, Factory, Retail, etc.)
    - Functional modules (HR, Inventory, Students, Patients, etc.)
    - Table purposes and descriptions
    - Key entities and relationships
    """

    def __init__(self):
        """Initialize with Google Gemini"""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        logger.info(f"LLM Analyzer initialized with {settings.gemini_model}")

    async def analyze_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLM analyzes schema and returns semantic understanding

        Args:
            schema: Full schema from SchemaExtractor

        Returns:
            {
                "organization_type": "University/Hospital/Factory/etc",
                "organization_description": "Brief description",
                "detected_modules": ["HR Management", "Access Control", ...],
                "table_descriptions": {"TableName": "Description", ...},
                "view_descriptions": {"ViewName": "Description", ...},
                "key_entities": ["Employee", "Department", ...],
                "relationships_summary": "How entities relate",
                "suggested_contexts": ["employee queries", "attendance", ...],
                "domain_vocabulary": {"term": "meaning", ...}
            }
        """
        logger.info("Starting LLM schema analysis...")

        # Format schema for LLM
        schema_summary = self._format_schema_summary(schema)
        sample_data = self._format_sample_data(schema)
        relationships = self._format_relationships(schema)

        prompt = f"""You are an expert database analyst. Analyze this database schema and understand what type of organization uses it.

DATABASE SCHEMA:
{schema_summary}

SAMPLE DATA:
{sample_data}

RELATIONSHIPS:
{relationships}

Based on the table names, column names, and sample data, provide a comprehensive analysis.

Return your analysis as a valid JSON object with EXACTLY this structure:
{{
    "organization_type": "The type of organization (e.g., University, Hospital, Factory, Retail Store, Corporate Office, Access Control System)",
    "organization_description": "A 2-3 sentence description of what this organization does based on the data",
    "detected_modules": ["List of functional modules you detect - e.g., HR Management, Access Control, Visitor Management, Attendance Tracking"],
    "table_descriptions": {{
        "TableName1": "What this table stores and its purpose",
        "TableName2": "What this table stores and its purpose"
    }},
    "view_descriptions": {{
        "ViewName1": "What this view provides",
        "ViewName2": "What this view provides"
    }},
    "key_entities": ["Primary entities in this system - e.g., Employee, Department, Terminal, Visitor"],
    "relationships_summary": "How the key entities relate to each other in 2-3 sentences",
    "suggested_contexts": ["Types of queries users might ask - e.g., employee information, attendance reports, visitor logs"],
    "domain_vocabulary": {{
        "Ecode": "Employee Code - unique identifier for employees",
        "TerminalID": "Access control device identifier"
    }}
}}

Important:
- Be specific based on actual table/column names
- Include ALL tables in table_descriptions
- Include ALL views in view_descriptions
- Domain vocabulary should explain business-specific terms found in column names
- Return ONLY valid JSON, no markdown formatting"""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=4000
                )
            )

            # Parse JSON response
            response_text = response.text

            # Clean up response - remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            analysis = json.loads(response_text.strip())

            logger.info(f"Schema analysis complete. Detected: {analysis.get('organization_type', 'Unknown')}")
            logger.info(f"Modules found: {analysis.get('detected_modules', [])}")

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            # Return basic analysis
            return self._create_fallback_analysis(schema)

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._create_fallback_analysis(schema)

    def _format_schema_summary(self, schema: Dict[str, Any]) -> str:
        """Format schema for LLM prompt"""
        lines = []

        # Tables
        lines.append("=== TABLES ===")
        for table_name, table_info in schema.get("tables", {}).items():
            columns = table_info.get("columns", [])
            pk = table_info.get("primary_key", [])
            row_count = table_info.get("row_count", 0)

            col_strs = []
            for col in columns[:15]:  # Limit columns shown
                col_str = f"{col['name']} ({col['data_type']})"
                if col['name'] in pk:
                    col_str += " [PK]"
                col_strs.append(col_str)

            if len(columns) > 15:
                col_strs.append(f"... +{len(columns)-15} more columns")

            lines.append(f"\n{table_name} ({row_count:,} rows):")
            lines.append(f"  Columns: {', '.join(col_strs)}")

            # Show foreign keys
            fks = table_info.get("foreign_keys", [])
            if fks:
                fk_strs = [f"{fk['column']} -> {fk['referenced_table']}" for fk in fks[:5]]
                lines.append(f"  Foreign Keys: {', '.join(fk_strs)}")

        # Views
        if schema.get("views"):
            lines.append("\n=== VIEWS ===")
            for view_name, view_info in schema.get("views", {}).items():
                columns = view_info.get("columns", [])
                base_tables = view_info.get("base_tables", [])

                col_names = [col['name'] for col in columns[:10]]
                if len(columns) > 10:
                    col_names.append(f"+{len(columns)-10} more")

                lines.append(f"\n{view_name}:")
                lines.append(f"  Columns: {', '.join(col_names)}")
                if base_tables:
                    lines.append(f"  Based on: {', '.join(base_tables[:5])}")

        return "\n".join(lines)

    def _format_sample_data(self, schema: Dict[str, Any]) -> str:
        """Format sample data for LLM"""
        lines = []

        # Show sample data from key tables (limited)
        tables_shown = 0
        for table_name, table_info in schema.get("tables", {}).items():
            if tables_shown >= 10:  # Limit samples
                break

            samples = table_info.get("sample_data", [])
            if samples:
                lines.append(f"\n{table_name} samples:")
                for sample in samples[:2]:  # 2 samples per table
                    # Show key columns only
                    sample_str = ", ".join([
                        f"{k}={v}" for k, v in list(sample.items())[:6]
                    ])
                    lines.append(f"  {sample_str}")
                tables_shown += 1

        return "\n".join(lines) if lines else "No sample data available"

    def _format_relationships(self, schema: Dict[str, Any]) -> str:
        """Format relationships for LLM"""
        relationships = schema.get("relationships", [])

        if not relationships:
            return "No explicit foreign key relationships found"

        lines = []
        for rel in relationships[:30]:  # Limit relationships shown
            lines.append(
                f"- {rel['from_table']}.{rel['from_column']} -> "
                f"{rel['to_table']}.{rel['to_column']}"
            )

        if len(relationships) > 30:
            lines.append(f"... +{len(relationships)-30} more relationships")

        return "\n".join(lines)

    def _create_fallback_analysis(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create basic analysis when LLM fails"""
        logger.warning("Using fallback analysis")

        table_names = list(schema.get("tables", {}).keys())
        view_names = list(schema.get("views", {}).keys())

        # Simple heuristics
        org_type = "Generic Database"
        modules = []

        # Detect based on table names
        name_lower = " ".join(table_names).lower()

        if "employee" in name_lower or "emp" in name_lower:
            modules.append("Employee Management")
            org_type = "Corporate/HR System"
        if "terminal" in name_lower or "punch" in name_lower:
            modules.append("Access Control")
        if "visitor" in name_lower:
            modules.append("Visitor Management")
        if "student" in name_lower:
            org_type = "University/School"
            modules.append("Student Management")
        if "patient" in name_lower:
            org_type = "Hospital/Healthcare"
            modules.append("Patient Management")

        return {
            "organization_type": org_type,
            "organization_description": f"Database with {len(table_names)} tables and {len(view_names)} views",
            "detected_modules": modules or ["Data Management"],
            "table_descriptions": {t: f"Table storing {t} data" for t in table_names[:20]},
            "view_descriptions": {v: f"View combining data from multiple tables" for v in view_names[:10]},
            "key_entities": table_names[:10],
            "relationships_summary": f"Database contains {len(schema.get('relationships', []))} foreign key relationships",
            "suggested_contexts": ["data queries", "reports"],
            "domain_vocabulary": {}
        }

    async def generate_table_description(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        sample_data: List[Dict[str, Any]],
        context: str = ""
    ) -> str:
        """
        Generate natural language description for a specific table

        Args:
            table_name: Name of the table
            columns: Column definitions
            sample_data: Sample rows
            context: Optional context about the database

        Returns:
            Human-readable description of what the table stores
        """
        col_strs = [f"{c['name']} ({c['data_type']})" for c in columns[:15]]

        sample_str = ""
        if sample_data:
            sample_str = f"\nSample row: {sample_data[0]}"

        prompt = f"""Describe what this database table stores in 1-2 sentences.

Table: {table_name}
Columns: {', '.join(col_strs)}
{sample_str}
{f'Context: {context}' if context else ''}

Provide a clear, concise description."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0,
                    max_output_tokens=200
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"Failed to generate description for {table_name}: {e}")
            return f"Table storing {table_name} data"
