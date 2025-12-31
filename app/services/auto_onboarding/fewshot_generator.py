"""
Auto Few-Shot Generator
Automatically generates relevant Q&A pairs for any database
Uses LLM to create natural language questions and corresponding SQL queries

ENHANCED: Now uses organization context (name, type, vocabulary) from DataContextDetector
to generate domain-appropriate questions like "How many students at MUJ?" instead of
generic "How many employees in the system?"
"""

import json
import re
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from loguru import logger

from app.config import settings


class AutoFewShotGenerator:
    """
    Automatically generates few-shot Q&A examples for Text-to-SQL

    Features:
    - Generates natural language questions based on schema
    - Creates corresponding SQL queries
    - Uses ORGANIZATION CONTEXT for domain-specific questions
    - Covers all detected modules
    - Validates SQL syntax
    - Categorizes by complexity (simple/medium/complex)
    """

    def __init__(self):
        """Initialize with Google Gemini"""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        logger.info("FewShot Generator initialized")

    async def generate_fewshots(
        self,
        schema: Dict[str, Any],
        analysis: Dict[str, Any],
        count: int = 50,
        batch_size: int = 10,
        org_context: Optional[Dict[str, Any]] = None  # NEW: Organization context
    ) -> List[Dict[str, str]]:
        """
        Generate few-shot Q&A pairs automatically

        Args:
            schema: Full schema from SchemaExtractor
            analysis: Schema analysis from LLMAnalyzer
            count: Total number of examples to generate (default: 50)
            batch_size: Generate in batches to manage token limits
            org_context: Organization context from DataContextDetector
                         Contains: organization_name, organization_type, domain_vocabulary,
                                   key_entities, typical_queries

        Returns:
            List of {
                "question": "Natural language question",
                "sql": "SELECT ... FROM ...",
                "module": "HR Management",
                "complexity": "simple|medium|complex",
                "tables_used": ["Table1", "Table2"]
            }
        """
        logger.info(f"Generating {count} few-shot examples...")

        # Store org context for use in batch generation
        self.org_context = org_context or {}

        all_fewshots = []
        modules = analysis.get("detected_modules", ["General"])

        # Use organization-specific type if available
        org_type = self.org_context.get("organization_type_display") or \
                   analysis.get("organization_type", "Organization")
        org_name = self.org_context.get("organization_name", "the organization")

        # Generate examples per module for better coverage
        examples_per_module = max(count // len(modules), 5)

        for module in modules:
            logger.info(f"Generating examples for module: {module}")

            # Get relevant tables for this module
            relevant_tables = self._get_tables_for_module(schema, module, analysis)

            if not relevant_tables:
                continue

            # Generate batch with organization context
            batch = await self._generate_batch(
                schema=schema,
                analysis=analysis,
                module=module,
                org_type=org_type,
                org_name=org_name,
                relevant_tables=relevant_tables,
                count=examples_per_module
            )

            all_fewshots.extend(batch)

        # Validate and deduplicate
        validated = self._validate_and_dedupe(all_fewshots, schema)

        logger.info(f"Generated {len(validated)} validated few-shot examples")
        return validated[:count]

    async def _generate_batch(
        self,
        schema: Dict[str, Any],
        analysis: Dict[str, Any],
        module: str,
        org_type: str,
        org_name: str,  # NEW: Organization name
        relevant_tables: List[str],
        count: int
    ) -> List[Dict[str, str]]:
        """Generate a batch of examples for a specific module"""

        # Build schema context for relevant tables only
        schema_context = self._build_schema_context(schema, relevant_tables)

        # Get domain vocabulary and typical queries if available
        domain_vocab = self.org_context.get("domain_vocabulary", {})
        key_entities = self.org_context.get("key_entities", [])
        typical_queries = self.org_context.get("typical_queries", [])

        # Build vocabulary context
        vocab_context = ""
        if domain_vocab:
            vocab_items = [f"- {term}: {meaning}" for term, meaning in list(domain_vocab.items())[:10]]
            vocab_context = f"\n\nDOMAIN VOCABULARY:\n" + "\n".join(vocab_items)

        # Build typical queries hint
        queries_hint = ""
        if typical_queries:
            queries_hint = f"\n\nTYPICAL QUESTIONS USERS ASK:\n" + "\n".join([f"- {q}" for q in typical_queries[:5]])

        # Build entity hint
        entity_hint = ""
        if key_entities:
            entity_hint = f"\n\nKEY ENTITIES TO ASK ABOUT: {', '.join(key_entities)}"

        prompt = f"""You are a SQL expert generating training examples for a Text-to-SQL AI system.

ORGANIZATION: {org_name}
ORGANIZATION TYPE: {org_type}
MODULE: {module}{vocab_context}{entity_hint}{queries_hint}

DATABASE SCHEMA:
{schema_context}

Generate {count} diverse Q&A examples. Questions should be natural language queries that someone at {org_name} ({org_type}) would ask about {module}.

CRITICAL RULES:
1. Questions must be natural language (like a real user would type)
2. Questions should be SPECIFIC to {org_name} - use the organization name when appropriate
3. Use domain-appropriate terminology (e.g., "faculty" for university, "workers" for factory)
4. SQL must be valid for SQL Server (use TOP instead of LIMIT, use square brackets for table names)
5. Cover simple (COUNT, basic SELECT), medium (JOINs, GROUP BY), and complex (subqueries, multiple JOINs) queries
6. Include various query types: counts, lists, filters, aggregations, comparisons
7. Questions should reference real column names from the schema
8. Use appropriate WHERE clauses with realistic conditions

Return ONLY a JSON array with this exact format:
[
    {{
        "question": "How many employees work at {org_name}?",
        "sql": "SELECT COUNT(*) AS TotalEmployees FROM [dbo].[EmployeeMaster] WHERE IsActive = 1",
        "module": "{module}",
        "complexity": "simple",
        "tables_used": ["EmployeeMaster"]
    }},
    {{
        "question": "Show all staff in the IT department at {org_name}",
        "sql": "SELECT e.* FROM [dbo].[EmployeeMaster] e INNER JOIN [dbo].[DepartmentMaster] d ON e.DeptID = d.DeptID WHERE d.DeptName = 'IT' AND e.IsActive = 1",
        "module": "{module}",
        "complexity": "medium",
        "tables_used": ["EmployeeMaster", "DepartmentMaster"]
    }}
]

Generate {count} unique, realistic examples covering different complexity levels.
Return ONLY valid JSON, no markdown or explanations."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Some creativity for diverse questions
                    max_output_tokens=4000
                )
            )

            response_text = response.text

            # Clean up response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            examples = json.loads(response_text.strip())

            # Ensure it's a list
            if isinstance(examples, dict):
                examples = [examples]

            return examples

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse few-shot JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to generate few-shots for {module}: {e}")
            return []

    def _get_tables_for_module(
        self,
        schema: Dict[str, Any],
        module: str,
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Identify tables relevant to a specific module"""

        all_tables = list(schema.get("tables", {}).keys())
        all_views = list(schema.get("views", {}).keys())

        # Get table descriptions from analysis
        table_descs = analysis.get("table_descriptions", {})

        # Module keywords mapping
        module_keywords = {
            "Employee Management": ["employee", "emp", "staff", "person", "worker"],
            "HR Management": ["employee", "emp", "department", "salary", "leave", "hr"],
            "Access Control": ["terminal", "punch", "access", "door", "authentication", "biometric"],
            "Visitor Management": ["visitor", "guest", "visit", "badge"],
            "Attendance": ["attendance", "punch", "time", "shift", "schedule"],
            "Department Management": ["department", "dept", "division", "branch"],
            "Device Management": ["terminal", "device", "reader", "controller"]
        }

        # Get keywords for this module (or use module name itself)
        keywords = module_keywords.get(module, [module.lower().split()[0]])

        # Find matching tables
        relevant = []
        for table in all_tables + all_views:
            table_lower = table.lower()

            # Check if table name matches keywords
            if any(kw in table_lower for kw in keywords):
                relevant.append(table)
                continue

            # Check table description
            desc = table_descs.get(table, "").lower()
            if any(kw in desc for kw in keywords):
                relevant.append(table)

        # If no matches, return some tables anyway
        if not relevant:
            relevant = all_tables[:5]

        return relevant[:10]  # Limit to 10 tables per module

    def _build_schema_context(
        self,
        schema: Dict[str, Any],
        table_names: List[str]
    ) -> str:
        """Build schema context string for selected tables"""

        lines = []

        for table_name in table_names:
            # Check tables first, then views
            table_info = schema.get("tables", {}).get(table_name) or \
                        schema.get("views", {}).get(table_name)

            if not table_info:
                continue

            columns = table_info.get("columns", [])
            pk = table_info.get("primary_key", [])
            fks = table_info.get("foreign_keys", [])

            # Format columns
            col_strs = []
            for col in columns[:20]:  # Limit columns
                col_str = f"{col['name']} {col['data_type']}"
                if col['name'] in pk:
                    col_str += " PRIMARY KEY"
                if not col.get('nullable', True):
                    col_str += " NOT NULL"
                col_strs.append(col_str)

            lines.append(f"\nTable: {table_name}")
            lines.append(f"Columns: {', '.join(col_strs)}")

            # Foreign keys
            if fks:
                fk_info = [f"{fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                          for fk in fks[:5]]
                lines.append(f"Foreign Keys: {', '.join(fk_info)}")

            # Sample values
            samples = table_info.get("sample_data", [])
            if samples and samples[0]:
                sample_cols = list(samples[0].keys())[:5]
                sample_vals = {k: samples[0][k] for k in sample_cols}
                lines.append(f"Sample values: {sample_vals}")

        return "\n".join(lines)

    def _validate_and_dedupe(
        self,
        fewshots: List[Dict[str, str]],
        schema: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Validate SQL and remove duplicates"""

        table_names = set(schema.get("tables", {}).keys()) | \
                     set(schema.get("views", {}).keys())

        validated = []
        seen_questions = set()
        seen_sql = set()

        for fs in fewshots:
            question = fs.get("question", "")
            sql = fs.get("sql", "")

            # Skip duplicates
            q_lower = question.lower().strip()
            sql_normalized = re.sub(r'\s+', ' ', sql.lower().strip())

            if q_lower in seen_questions or sql_normalized in seen_sql:
                continue

            # Basic SQL validation
            if not self._validate_sql(sql, table_names):
                continue

            seen_questions.add(q_lower)
            seen_sql.add(sql_normalized)

            validated.append(fs)

        return validated

    def _validate_sql(self, sql: str, table_names: set) -> bool:
        """Basic SQL validation"""

        if not sql or len(sql) < 10:
            return False

        sql_lower = sql.lower()

        # Must start with SELECT
        if not sql_lower.strip().startswith("select"):
            return False

        # Check for dangerous operations
        dangerous = ["drop", "delete", "update", "insert", "alter", "truncate", "exec"]
        if any(d in sql_lower for d in dangerous):
            return False

        # Check if at least one table is referenced
        table_names_lower = {t.lower() for t in table_names}
        sql_clean = sql_lower.replace("[", "").replace("]", "").replace("dbo.", "")

        found_table = False
        for table in table_names_lower:
            if table in sql_clean:
                found_table = True
                break

        return found_table

    async def generate_additional_examples(
        self,
        schema: Dict[str, Any],
        analysis: Dict[str, Any],
        existing_questions: List[str],
        count: int = 10
    ) -> List[Dict[str, str]]:
        """
        Generate additional examples avoiding duplicates

        Useful for expanding the few-shot collection over time
        """
        schema_context = self._build_schema_context(
            schema,
            list(schema.get("tables", {}).keys())[:10]
        )

        existing_list = "\n".join([f"- {q}" for q in existing_questions[:20]])

        prompt = f"""Generate {count} NEW few-shot examples for a Text-to-SQL system.

DATABASE SCHEMA:
{schema_context}

EXISTING QUESTIONS (DO NOT DUPLICATE):
{existing_list}

Generate {count} completely NEW and DIFFERENT questions covering areas not already covered.

Return as JSON array:
[{{"question": "...", "sql": "...", "module": "...", "complexity": "simple|medium|complex", "tables_used": [...]}}]

Return ONLY valid JSON."""

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=2000
                )
            )

            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())

        except Exception as e:
            logger.warning(f"Failed to generate additional examples: {e}")
            return []
