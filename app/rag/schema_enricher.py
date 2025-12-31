"""
Schema Enricher
Uses LLM to generate rich, semantic descriptions of database schemas
"""

from typing import Dict, Any, List
import google.generativeai as genai
from loguru import logger

from app.config import settings


# Domain-specific keyword hints to improve semantic retrieval
KEYWORD_HINTS = {
    "AttendanceRegister": ["punch", "punch in", "punch out", "in punch", "out punch", "swipe", "clock in", "clock out", "biometric entry", "attendance", "present", "absent"],
    "MachinePunch": ["raw punch", "machine punch", "punch data", "punch records", "biometric logs"],
    "MachineRawPunch": ["punch transaction", "terminal punch", "swipe data"],
    "Biometric": ["fingerprint", "biometric scan", "finger punch"],
    "EmployeeMaster": ["staff", "worker", "personnel", "employee details", "joining date", "department", "section", "designation", "category", "gender", "email"],
    "LeaveApplication": ["leave request", "time off", "vacation", "sick leave"],
}


class SchemaEnricher:
    """
    Enriches raw database schema metadata with semantic descriptions
    using Gemini LLM to make schema more understandable for text-to-SQL
    """

    def __init__(self):
        """Initialize schema enricher with Gemini"""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def enrich_table(self, table_metadata: Dict[str, Any]) -> str:
        """
        Generate rich semantic description for a table

        Args:
            table_metadata: Dict from SchemaExtractor with table info

        Returns:
            Rich text description suitable for FAISS vector store
        """
        table_name = table_metadata["table_name"]
        logger.info(f"Enriching schema for table: {table_name}")

        try:
            # Build prompt for Gemini
            prompt = self._build_enrichment_prompt(table_metadata)

            # Generate description
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Lower temperature for more factual descriptions
                    max_output_tokens=500
                )
            )

            enriched_description = response.text.strip()
            logger.info(f"[OK] Generated description for {table_name}")

            # Combine with structured metadata
            final_description = self._format_final_description(
                table_metadata,
                enriched_description
            )

            return final_description

        except Exception as e:
            logger.error(f"[ERROR] Failed to enrich {table_name}: {str(e)}")
            # Fallback to basic description
            return self._create_basic_description(table_metadata)

    def _build_enrichment_prompt(self, metadata: Dict[str, Any]) -> str:
        """
        Build prompt for Gemini to generate semantic description

        Args:
            metadata: Table metadata dict

        Returns:
            Prompt string
        """
        table_name = metadata["table_name"]
        columns = metadata["columns"]
        foreign_keys = metadata.get("foreign_keys", [])

        # Format columns for prompt
        column_list = []
        for col in columns:
            col_desc = f"- {col['name']} ({col['data_type']})"
            if not col['nullable']:
                col_desc += " NOT NULL"
            column_list.append(col_desc)

        columns_text = "\n".join(column_list)

        #Format foreign keys for prompt
        fk_text = ""
        if foreign_keys:
            fk_list = []
            for fk in foreign_keys:
                fk_list.append(
                    f"- {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                )
            fk_text = "\n\nForeign Keys:\n" + "\n".join(fk_list)

        prompt = f"""You are a database documentation expert. Analyze this SQL Server table and provide a concise, semantic description.

Table Name: {table_name}

Columns:
{columns_text}{fk_text}

Generate a brief description that:
1. Explains the table's business purpose (what data it stores)
2. Highlights key columns and their meanings IN BUSINESS TERMS
3. **CRITICAL**: For abbreviated columns (e.g., SecCode, DesCode, Catcode, Gcode), explicitly state what they represent
   - Example: "SecCode represents the Section/Department Code"
   - Example: "DesCode is the Designation Code"
4. Mentions common use cases or queries
5. Infers meaning from column names (e.g., InTime = check-in time, OutTime = check-out time)

Keep the description under 150 words and focus on practical query usage with explicit column meaning explanations.

Description:"""

        return prompt

    def _format_final_description(
        self,
        metadata: Dict[str, Any],
        llm_description: str
    ) -> str:
        """
        Format the final enriched description for FAISS storage

        Args:
            metadata: Original table metadata
            llm_description: LLM-generated semantic description

        Returns:
            Formatted description string
        """
        table_name = metadata["full_name"]  # e.g., dbo.EmployeeMaster
        columns = metadata["columns"]
        pk = metadata.get("primary_key")
        fks = metadata.get("foreign_keys", [])

        # Start with enriched description
        description = f"""TABLE: {table_name}

PURPOSE:
{llm_description}

COLUMNS ({len(columns)} total):
"""

        # Add column details
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            description += f"  • {col['name']} ({col['data_type']}, {nullable})\n"

        # Add primary key
        if pk:
            description += f"\nPRIMARY KEY: {', '.join(pk)}\n"

        # Add foreign key relationships
        if fks:
            description += "\nRELATIONSHIPS:\n"
            for fk in fks:
                description += f"  • {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}\n"

        # Add common query patterns hint
        description += f"\nCOMMON QUERIES:\n"
        description += f"  SELECT * FROM {table_name}\n"
        if fks:
            ref_table = fks[0]['referenced_table']
            fk_col = fks[0]['column']
            description += f"  JOIN with {ref_table} ON {table_name}.{fk_col}\n"

        # Add keyword hints for semantic search improvement
        # This helps bridge the gap between user terms (e.g., "punch") and schema terms (e.g., "InTime")
        simple_table_name = metadata["table_name"]
        if simple_table_name in KEYWORD_HINTS:
            keywords = ", ".join(KEYWORD_HINTS[simple_table_name])
            description += f"\nKEYWORDS: {keywords}\n"

        return description

    def _create_basic_description(self, metadata: Dict[str, Any]) -> str:
        """
        Create basic description without LLM (fallback)

        Args:
            metadata: Table metadata

        Returns:
            Basic formatted description
        """
        table_name = metadata["full_name"]
        columns = metadata["columns"]

        description = f"TABLE: {table_name}\n\nCOLUMNS:\n"
        for col in columns:
            description += f"  • {col['name']} ({col['data_type']})\n"

        return description

    def enrich_all_tables(
        self,
        tables_metadata: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[Dict[str, str]]:
        """
        Enrich multiple tables with semantic descriptions

        Args:
            tables_metadata: List of table metadata dicts from SchemaExtractor
            batch_size: Process tables in batches

        Returns:
            List of dicts with 'table_name' and 'enriched_description'
        """
        logger.info(f"Enriching {len(tables_metadata)} tables...")

        enriched_tables = []

        for i, table_meta in enumerate(tables_metadata, 1):
            logger.info(f"Processing {i}/{len(tables_metadata)}: {table_meta['table_name']}")

            enriched_desc = self.enrich_table(table_meta)

            enriched_tables.append({
                "table_name": table_meta["table_name"],
                "full_name": table_meta["full_name"],
                "enriched_description": enriched_desc,
                "metadata": table_meta  # Keep original metadata
            })

        logger.info(f"[OK] Enriched {len(enriched_tables)} tables")
        return enriched_tables


# Singleton instance
schema_enricher = SchemaEnricher()
