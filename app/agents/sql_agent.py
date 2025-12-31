"""
SQL Agent with RAG Enhancement
Generates SQL queries using retrieved schema context
Supports both Gemini and OpenRouter LLM providers
"""

from typing import Dict, Any, Optional, List
import asyncio
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from loguru import logger
import requests

from app.config import settings
from app.database import db_manager
from app.rag.chroma_manager import chroma_manager
from app.rag.few_shot_manager import few_shot_manager


class RAGSQLAgent:
    """
    SQL Agent with Retrieval-Augmented Generation
    Uses ChromaDB (Google Embeddings) to retrieve relevant schema context before generating SQL
    Supports both Gemini and OpenRouter as LLM providers
    """

    def __init__(self):
        """Initialize SQL Agent with configured LLM provider (Gemini or OpenRouter)"""
        # Determine which LLM provider to use
        self.llm_provider = getattr(settings, 'llm_provider', 'gemini').lower()
        self.temperature = getattr(settings, 'gemini_temperature', 0.1)

        logger.info(f"[SQL_AGENT] Initializing with LLM provider: {self.llm_provider}")

        if self.llm_provider == 'openrouter':
            # OpenRouter configuration
            self.openrouter_api_key = getattr(settings, 'openrouter_api_key', '')
            self.openrouter_model = getattr(settings, 'openrouter_model', 'tngtech/deepseek-r1t2-chimera:free')
            self.openrouter_base_url = getattr(settings, 'openrouter_base_url', 'https://openrouter.ai/api/v1')

            if not self.openrouter_api_key:
                logger.warning("[SQL_AGENT] OpenRouter API key not configured, falling back to Gemini")
                self.llm_provider = 'gemini'
            else:
                logger.info(f"[SQL_AGENT] Using OpenRouter: {self.openrouter_model}")

        if self.llm_provider == 'gemini':
            # Gemini configuration
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
            logger.info(f"[SQL_AGENT] Using Gemini: {settings.gemini_model}")

    def _check_template_query(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Check if the question matches a known pattern and return a pre-built SQL template.

        This method bypasses the LLM entirely for queries that require specific SQL patterns
        that the LLM consistently fails to generate correctly.

        Args:
            question: User's question

        Returns:
            Dict with sql_query and other info if template matches, None otherwise
        """
        import re
        question_lower = question.lower()

        # FACE ACCESS query detection
        face_keywords = ['face access', 'face recognition access', 'face data push',
                         'who has face', 'facial access', 'face only access',
                         'face authentication']

        if any(kw in question_lower for kw in face_keywords):
            logger.info(f"[TEMPLATE] Detected face access query - using direct SQL template")

            # Extract device/domain filter if mentioned (e.g., "SUBWAY", "MAIN GATE")
            domain_filter = ""
            domain_patterns = [
                r'on\s+(\w+)\s+devices?',  # "on SUBWAY devices"
                r'(\w+)\s+device(?:s)?',    # "SUBWAY devices"
                r'at\s+(\w+)',              # "at SUBWAY"
            ]
            for pattern in domain_patterns:
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    domain = match.group(1)
                    if domain.lower() not in ['the', 'all', 'any', 'which', 'what']:
                        domain_filter = f"AND v.DomainName LIKE '%{domain}%'"
                        break

            # Extract role filter if mentioned (student, staff, employee)
            role_filter = ""
            if 'student' in question_lower:
                role_filter = "AND e.AccessType = 'Student'"
            elif 'staff' in question_lower or 'employee' in question_lower:
                role_filter = "AND e.AccessType IN ('Staff', 'Employee')"

            # Build WHERE clause conditions
            conditions = ["v.AuthenticationID = 7"]
            if domain_filter:
                conditions.append(domain_filter.replace("AND ", ""))
            if role_filter:
                conditions.append(role_filter.replace("AND ", ""))
            conditions.append("e.Active = 1")

            # Build the correct SQL query
            where_clause = "\n    AND ".join(conditions)
            sql_query = f"""SELECT DISTINCT v.CorpEmpCode, v.EmpName, v.DomainName
FROM dbo.View_Employee_Terminal_Authentication_Relation v
JOIN dbo.vw_EmployeeMaster_Vms e ON v.Ecode = e.Ecode
WHERE {where_clause}
ORDER BY v.EmpName"""

            return {
                "sql_query": sql_query.strip(),
                "explanation": "Generated using face access template (AuthenticationID = 7)",
                "context_used": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "tables_referenced": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "template_used": "face_access"
            }

        # FINGERPRINT ACCESS query detection
        fingerprint_keywords = ['fingerprint access', 'finger access', 'fingerprint data push']
        if any(kw in question_lower for kw in fingerprint_keywords):
            logger.info(f"[TEMPLATE] Detected fingerprint access query - using direct SQL template")

            domain_filter = ""
            for pattern in [r'on\s+(\w+)\s+devices?', r'(\w+)\s+device(?:s)?']:
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    domain = match.group(1)
                    if domain.lower() not in ['the', 'all', 'any', 'which', 'what']:
                        domain_filter = f"AND v.DomainName LIKE '%{domain}%'"
                        break

            # Build WHERE clause conditions
            conditions = ["v.AuthenticationID = 2"]
            if domain_filter:
                conditions.append(domain_filter.replace("AND ", ""))
            conditions.append("e.Active = 1")

            where_clause = "\n    AND ".join(conditions)
            sql_query = f"""SELECT DISTINCT v.CorpEmpCode, v.EmpName, v.DomainName
FROM dbo.View_Employee_Terminal_Authentication_Relation v
JOIN dbo.vw_EmployeeMaster_Vms e ON v.Ecode = e.Ecode
WHERE {where_clause}
ORDER BY v.EmpName"""

            return {
                "sql_query": sql_query.strip(),
                "explanation": "Generated using fingerprint access template (AuthenticationID = 2)",
                "context_used": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "tables_referenced": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "template_used": "fingerprint_access"
            }

        # CARD ACCESS query detection
        card_keywords = ['card access', 'card/finger access', 'card and finger']
        if any(kw in question_lower for kw in card_keywords):
            logger.info(f"[TEMPLATE] Detected card access query - using direct SQL template")

            domain_filter = ""
            for pattern in [r'on\s+(\w+)\s+devices?', r'(\w+)\s+device(?:s)?']:
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    domain = match.group(1)
                    if domain.lower() not in ['the', 'all', 'any', 'which', 'what']:
                        domain_filter = f"AND v.DomainName LIKE '%{domain}%'"
                        break

            # Build WHERE clause conditions
            conditions = ["v.AuthenticationID = 3"]
            if domain_filter:
                conditions.append(domain_filter.replace("AND ", ""))
            conditions.append("e.Active = 1")

            where_clause = "\n    AND ".join(conditions)
            sql_query = f"""SELECT DISTINCT v.CorpEmpCode, v.EmpName, v.DomainName
FROM dbo.View_Employee_Terminal_Authentication_Relation v
JOIN dbo.vw_EmployeeMaster_Vms e ON v.Ecode = e.Ecode
WHERE {where_clause}
ORDER BY v.EmpName"""

            return {
                "sql_query": sql_query.strip(),
                "explanation": "Generated using card access template (AuthenticationID = 3)",
                "context_used": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "tables_referenced": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "template_used": "card_access"
            }

        # REMOVED FROM DEVICE query detection
        removed_keywords = ['removed from device', 'data removed', 'removed data push']
        if any(kw in question_lower for kw in removed_keywords):
            logger.info(f"[TEMPLATE] Detected removed from device query - using direct SQL template")

            domain_filter = ""
            for pattern in [r'on\s+(\w+)\s+devices?', r'(\w+)\s+device(?:s)?']:
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    domain = match.group(1)
                    if domain.lower() not in ['the', 'all', 'any', 'which', 'what']:
                        domain_filter = f"AND v.DomainName LIKE '%{domain}%'"
                        break

            # Build WHERE clause conditions
            conditions = ["v.AuthenticationID = 1001"]
            if domain_filter:
                conditions.append(domain_filter.replace("AND ", ""))

            where_clause = "\n    AND ".join(conditions)
            sql_query = f"""SELECT DISTINCT v.CorpEmpCode, v.EmpName, v.DomainName
FROM dbo.View_Employee_Terminal_Authentication_Relation v
JOIN dbo.vw_EmployeeMaster_Vms e ON v.Ecode = e.Ecode
WHERE {where_clause}
ORDER BY v.EmpName"""

            return {
                "sql_query": sql_query.strip(),
                "explanation": "Generated using removed from device template (AuthenticationID = 1001)",
                "context_used": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "tables_referenced": ["View_Employee_Terminal_Authentication_Relation", "vw_EmployeeMaster_Vms"],
                "template_used": "removed_from_device"
            }

        return None

    def _is_followup_query(self, question: str) -> bool:
        """
        Detect if the current question is a follow-up query referencing previous results.

        Args:
            question: User's current question

        Returns:
            True if this appears to be a follow-up query
        """
        question_lower = question.lower()

        # Pronouns and phrases that indicate follow-up
        followup_indicators = [
            # Pronouns
            'they', 'them', 'those', 'these', 'it', 'their',
            # Phrases
            'the same', 'those students', 'those employees', 'those people',
            'which of them', 'among them', 'from them',
            'are they', 'do they', 'can they', 'will they',
            'are those', 'are these',
            # Implicit references
            'hostler or dayscholar', 'hostel or dayscholar',  # Common follow-up pattern
        ]

        for indicator in followup_indicators:
            if indicator in question_lower:
                logger.info(f"[FOLLOWUP_DETECT] Detected follow-up indicator: '{indicator}'")
                return True

        return False

    def _extract_ecodes_from_previous_sql(self, previous_sql: str) -> Optional[List[str]]:
        """
        Transform a previous aggregation SQL query to extract the underlying ECodes.

        Strategy:
        1. If query has CTE (WITH clause), extract CTE and modify final SELECT to get ECodes
        2. If query is simple COUNT/aggregation, modify to SELECT DISTINCT Ecode

        Args:
            previous_sql: The previous SQL query (usually an aggregation)

        Returns:
            List of ECodes extracted by executing modified query, or None if failed
        """
        import re

        logger.info(f"[ECODE_EXTRACT] Attempting to extract ECodes from previous query...")

        try:
            # Normalize SQL for easier parsing
            sql_upper = previous_sql.upper()
            sql_normalized = ' '.join(previous_sql.split())  # Normalize whitespace

            # Check if this is an aggregation query
            is_aggregation = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'COUNT '])

            if not is_aggregation:
                logger.info("[ECODE_EXTRACT] Previous query is not an aggregation, skipping")
                return None

            # Strategy 1: Query has CTE (WITH ... AS ...)
            if 'WITH ' in sql_upper and ' AS ' in sql_upper:
                logger.info("[ECODE_EXTRACT] Detected CTE pattern, extracting...")

                # Extract CTE portion - everything from WITH to the final SELECT
                # Pattern: WITH CteName AS (...) SELECT COUNT(*) FROM CteName
                cte_match = re.search(
                    r'(WITH\s+\w+\s+AS\s*\([^)]+(?:\([^)]*\)[^)]*)*\))',
                    previous_sql,
                    re.IGNORECASE | re.DOTALL
                )

                if cte_match:
                    cte_part = cte_match.group(1)
                    cte_name_match = re.search(r'WITH\s+(\w+)\s+AS', cte_part, re.IGNORECASE)

                    if cte_name_match:
                        cte_name = cte_name_match.group(1)

                        # Build new query: same CTE, but SELECT ECodes instead of COUNT
                        # Try different column name variations
                        for ecode_col in ['ECode', 'Ecode', 'ecode', 'lp.ECode', 'e.Ecode']:
                            modified_sql = f"{cte_part} SELECT DISTINCT {ecode_col} FROM {cte_name}"

                            try:
                                logger.info(f"[ECODE_EXTRACT] Trying: SELECT DISTINCT {ecode_col} FROM {cte_name}")
                                results = db_manager.execute_query(modified_sql)

                                if results:
                                    # Extract ECodes from results
                                    ecodes = []
                                    for row in results:
                                        for key in ['ECode', 'Ecode', 'ecode']:
                                            if key in row and row[key]:
                                                ecodes.append(str(row[key]))
                                                break

                                    if ecodes:
                                        logger.info(f"[ECODE_EXTRACT] Successfully extracted {len(ecodes)} ECodes")
                                        return ecodes
                            except Exception as e:
                                logger.debug(f"[ECODE_EXTRACT] Failed with {ecode_col}: {e}")
                                continue

            # Strategy 2: Simple query without CTE - extract FROM/WHERE clause
            else:
                logger.info("[ECODE_EXTRACT] Trying simple query transformation...")

                # Find the FROM clause and everything after it
                from_match = re.search(r'(FROM\s+.+)', previous_sql, re.IGNORECASE | re.DOTALL)

                if from_match:
                    from_clause = from_match.group(1)

                    # Build new query to get ECodes
                    for ecode_expr in ['DISTINCT e.Ecode', 'DISTINCT lp.ECode', 'DISTINCT Ecode', 'DISTINCT ECode']:
                        modified_sql = f"SELECT {ecode_expr} {from_clause}"

                        # Remove any GROUP BY or ORDER BY from the end
                        modified_sql = re.sub(r'\s+GROUP\s+BY\s+.+$', '', modified_sql, flags=re.IGNORECASE)
                        modified_sql = re.sub(r'\s+ORDER\s+BY\s+.+$', '', modified_sql, flags=re.IGNORECASE)

                        try:
                            logger.info(f"[ECODE_EXTRACT] Trying simple transform with {ecode_expr}...")
                            results = db_manager.execute_query(modified_sql)

                            if results:
                                ecodes = []
                                for row in results:
                                    for key in ['ECode', 'Ecode', 'ecode']:
                                        if key in row and row[key]:
                                            ecodes.append(str(row[key]))
                                            break

                                if ecodes:
                                    logger.info(f"[ECODE_EXTRACT] Successfully extracted {len(ecodes)} ECodes")
                                    return ecodes
                        except Exception as e:
                            logger.debug(f"[ECODE_EXTRACT] Failed with {ecode_expr}: {e}")
                            continue

            logger.warning("[ECODE_EXTRACT] Could not extract ECodes from previous query")
            return None

        except Exception as e:
            logger.error(f"[ECODE_EXTRACT] Error extracting ECodes: {e}")
            return None

    def _get_previous_context(self, conversation_history: Optional[List[Dict]]) -> Dict[str, Any]:
        """
        Extract previous query context from conversation history.

        Returns:
            Dict with keys: 'result_ids', 'sql_query', 'has_context'
        """
        if not conversation_history:
            return {'result_ids': None, 'sql_query': None, 'has_context': False}

        last_result_ids = None
        last_sql_query = None

        # Search conversation history from newest to oldest
        for msg in reversed(conversation_history):
            if msg.get("message_type") != "assistant":
                continue

            content = msg.get("message_content", "")

            if "---CONTEXT_FOR_FOLLOWUP---" in content:
                parts = content.split("---CONTEXT_FOR_FOLLOWUP---")
                context_part = parts[1] if len(parts) > 1 else ""

                for line in context_part.split("\n"):
                    line = line.strip()
                    if line.startswith("[SQL_QUERY]:"):
                        last_sql_query = line.replace("[SQL_QUERY]:", "").strip()
                    elif line.startswith("[RESULT_IDS]:"):
                        last_result_ids = line.replace("[RESULT_IDS]:", "").strip()

                # Found context, stop searching
                break

        return {
            'result_ids': last_result_ids,
            'sql_query': last_sql_query,
            'has_context': bool(last_result_ids or last_sql_query)
        }

    def _preprocess_question(self, question: str) -> str:
        """
        Preprocess question to add hints for specific query patterns.
        This helps guide the LLM without fully bypassing it.

        Args:
            question: Original user question

        Returns:
            Enhanced question with hints, or original if no hints needed
        """
        # For now, just return the original question
        # This method can be extended to add hints for specific patterns
        return question

    def generate_sql(
        self,
        question: str,
        tenant_id: str = "default",
        user_id: str = "system",
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language question using RAG

        Args:
            question: User's natural language question
            tenant_id: Tenant identifier
            user_id: User identifier
            conversation_history: Optional list of previous conversation messages for context

        Returns:
            Dict with keys: 'sql_query', 'explanation', 'context_used'

        Example:
            result = agent.generate_sql("How many employees joined last month?")
            # Returns: {"sql_query": "SELECT COUNT(*) FROM...", ...}
        """
        logger.info(f"Generating SQL for: {question}")
        if conversation_history:
            logger.debug(f"Using {len(conversation_history)} messages from conversation history")

        # Pre-fetched ECodes for follow-up queries (deterministic approach)
        prefetched_ecodes = None

        try:
            # Step 0: Check for template-based queries (bypass LLM for known patterns)
            template_result = self._check_template_query(question)
            if template_result:
                logger.info(f"[SQL_AGENT] Using template query: {template_result.get('template_used')}")
                return template_result

            # Step 0b: Preprocess question to add hints for specific query patterns
            enhanced_question = self._preprocess_question(question)
            if enhanced_question != question:
                logger.info(f"[SQL_AGENT] Question enhanced with hints")

            # Step 0c: CRITICAL - Pre-fetch ECodes for follow-up queries
            # This is the deterministic solution for conversation context
            if conversation_history and self._is_followup_query(question):
                logger.info("[SQL_AGENT] Detected follow-up query, checking for pre-fetch opportunity...")

                prev_context = self._get_previous_context(conversation_history)

                if prev_context['has_context']:
                    if prev_context['result_ids']:
                        # Already have ECodes from previous query
                        prefetched_ecodes = prev_context['result_ids'].split(',')
                        logger.info(f"[SQL_AGENT] Using stored ECodes: {len(prefetched_ecodes)} IDs")
                    elif prev_context['sql_query']:
                        # Previous query was aggregation - need to pre-fetch ECodes
                        logger.info("[SQL_AGENT] Previous query was aggregation, pre-fetching ECodes...")
                        prefetched_ecodes = self._extract_ecodes_from_previous_sql(prev_context['sql_query'])
                        if prefetched_ecodes:
                            logger.info(f"[SQL_AGENT] Pre-fetched {len(prefetched_ecodes)} ECodes from previous query")
                        else:
                            logger.warning("[SQL_AGENT] Could not pre-fetch ECodes, LLM will handle context")

            # Step 1: Retrieve relevant few-shot examples
            logger.info("[SQL_AGENT] Step 1: Retrieving few-shot examples...")
            few_shot_examples = self._retrieve_few_shot_examples(enhanced_question)
            logger.info(f"[SQL_AGENT] Step 1 complete: {len(few_shot_examples)} examples")

            # Step 2: Retrieve relevant schema context using RAG
            logger.info("[SQL_AGENT] Step 2: Retrieving schema context...")
            schema_context = self._retrieve_schema_context(enhanced_question)
            logger.info(f"[SQL_AGENT] Step 2 complete: {len(schema_context['documents'])} schemas")

            # Step 3: Build prompt with examples, schema context, conversation history, and pre-fetched ECodes
            logger.info("[SQL_AGENT] Step 3: Building prompt...")
            prompt = self._build_prompt(enhanced_question, schema_context, few_shot_examples, conversation_history, prefetched_ecodes)
            logger.info(f"[SQL_AGENT] Step 3 complete: prompt length {len(prompt)}")

            # Step 4: Call LLM to generate SQL (Gemini or OpenRouter)
            logger.info(f"[SQL_AGENT] Step 4: Calling {self.llm_provider.upper()}...")
            sql_query = self._call_llm(prompt)
            logger.info("[SQL_AGENT] Step 4 complete")

            # Step 4: Clean and validate SQL
            sql_query = self._clean_sql(sql_query)

            logger.info(f"[OK] Generated SQL: {sql_query[:100]}...")

            return {
                "sql_query": sql_query,
                "explanation": f"Generated query based on {len(schema_context['documents'])} relevant tables",
                "context_used": schema_context["documents"],
                "tables_referenced": [
                    meta["table_name"]
                    for meta in schema_context["metadatas"]
                    if meta.get("type") == "schema"
                ]
            }

        except Exception as e:
            logger.error(f"[ERROR] SQL generation failed: {str(e)}")
            raise

    async def generate_sql_async(
        self,
        question: str,
        tenant_id: str = "default",
        user_id: str = "system",
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        PERFORMANCE OPTIMIZED: Async version of generate_sql.

        Uses asyncio.to_thread() for blocking LLM calls, allowing other
        async operations to proceed while waiting for the LLM response.

        Args:
            question: User's natural language question
            tenant_id: Tenant identifier
            user_id: User identifier
            conversation_history: Optional list of previous conversation messages

        Returns:
            Dict with keys: 'sql_query', 'explanation', 'context_used'
        """
        logger.info(f"[SQL_AGENT] Generating SQL (async) for: {question}")
        if conversation_history:
            logger.debug(f"[SQL_AGENT] Using {len(conversation_history)} messages from conversation history")

        prefetched_ecodes = None

        try:
            # Step 0: Check for template-based queries (bypass LLM for known patterns)
            template_result = self._check_template_query(question)
            if template_result:
                logger.info(f"[SQL_AGENT] Using template query: {template_result.get('template_used')}")
                return template_result

            # Step 0b: Preprocess question to add hints
            enhanced_question = self._preprocess_question(question)
            if enhanced_question != question:
                logger.info(f"[SQL_AGENT] Question enhanced with hints")

            # Step 0c: Pre-fetch ECodes for follow-up queries
            if conversation_history and self._is_followup_query(question):
                logger.info("[SQL_AGENT] Detected follow-up query, checking for pre-fetch opportunity...")
                prev_context = self._get_previous_context(conversation_history)
                if prev_context['has_context']:
                    if prev_context['result_ids']:
                        prefetched_ecodes = prev_context['result_ids'].split(',')
                        logger.info(f"[SQL_AGENT] Using stored ECodes: {len(prefetched_ecodes)} IDs")
                    elif prev_context['sql_query']:
                        logger.info("[SQL_AGENT] Previous query was aggregation, pre-fetching ECodes...")
                        prefetched_ecodes = self._extract_ecodes_from_previous_sql(prev_context['sql_query'])
                        if prefetched_ecodes:
                            logger.info(f"[SQL_AGENT] Pre-fetched {len(prefetched_ecodes)} ECodes")

            # Step 1: Retrieve few-shot examples (sync but fast - in-memory FAISS)
            logger.info("[SQL_AGENT] Step 1: Retrieving few-shot examples...")
            few_shot_examples = self._retrieve_few_shot_examples(enhanced_question)
            logger.info(f"[SQL_AGENT] Step 1 complete: {len(few_shot_examples)} examples")

            # Step 2: Retrieve schema context (sync but fast - local ChromaDB)
            logger.info("[SQL_AGENT] Step 2: Retrieving schema context...")
            schema_context = self._retrieve_schema_context(enhanced_question)
            logger.info(f"[SQL_AGENT] Step 2 complete: {len(schema_context['documents'])} schemas")

            # Step 3: Build prompt
            logger.info("[SQL_AGENT] Step 3: Building prompt...")
            prompt = self._build_prompt(enhanced_question, schema_context, few_shot_examples, conversation_history, prefetched_ecodes)
            logger.info(f"[SQL_AGENT] Step 3 complete: prompt length {len(prompt)}")

            # Step 4: Call LLM ASYNC (non-blocking)
            logger.info(f"[SQL_AGENT] Step 4: Calling {self.llm_provider.upper()} (async)...")
            sql_query = await self._call_llm_async(prompt)
            logger.info("[SQL_AGENT] Step 4 complete")

            # Step 5: Clean and validate SQL
            sql_query = self._clean_sql(sql_query)
            logger.info(f"[SQL_AGENT] Generated SQL: {sql_query[:100]}...")

            return {
                "sql_query": sql_query,
                "explanation": f"Generated query based on {len(schema_context['documents'])} relevant tables",
                "context_used": schema_context["documents"],
                "tables_referenced": [
                    meta["table_name"]
                    for meta in schema_context["metadatas"]
                    if meta.get("type") == "schema"
                ]
            }

        except Exception as e:
            logger.error(f"[SQL_AGENT] SQL generation (async) failed: {str(e)}")
            raise

    def _retrieve_schema_context(self, question: str, n_results: int = 10) -> Dict[str, Any]:
        """
        Retrieve relevant schema information from vector store

        Args:
            question: User's question
            n_results: Number of schema results to retrieve

        Returns:
            Dict with documents, metadatas, and distances
        """
        logger.info(f"Retrieving schema context (top {n_results})...")

        try:
            results = chroma_manager.query_schemas(
                query_text=question,
                n_results=n_results
            )

            logger.info(f"[OK] Retrieved {len(results['documents'])} schema contexts")
            return results

        except Exception as e:
            logger.error(f"[ERROR] Schema retrieval failed: {str(e)}")
            # Return empty context if retrieval fails
            return {
                "documents": [],
                "metadatas": [],
                "distances": []
            }

    def _retrieve_few_shot_examples(self, question: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant few-shot examples from vector store

        Args:
            question: User's question
            n_results: Number of examples to retrieve (default: 3)

        Returns:
            List of relevant example dictionaries
        """
        logger.info(f"Retrieving few-shot examples (top {n_results})...")

        try:
            examples = few_shot_manager.get_relevant_examples(
                question=question,
                n_results=n_results
            )

            logger.info(f"[OK] Retrieved {len(examples)} few-shot examples")
            return examples

        except Exception as e:
            logger.error(f"[ERROR] Few-shot retrieval failed: {str(e)}")
            # Return empty list if retrieval fails
            return []

    def _build_prompt(
        self,
        question: str,
        schema_context: Dict[str, Any],
        few_shot_examples: List[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict]] = None,
        prefetched_ecodes: Optional[List[str]] = None
    ) -> str:
        """
        Build comprehensive prompt with question, few-shot examples, retrieved schema, and conversation history

        Args:
            question: User's question
            schema_context: Retrieved schema information
            few_shot_examples: List of relevant example queries
            conversation_history: Optional list of previous conversation messages for context
            prefetched_ecodes: Optional list of ECodes pre-fetched from previous query for follow-up filtering

        Returns:
            Complete prompt for Gemini
        """
        prompt = f"""You are an expert SQL query generator for SQL Server databases.

Given the user's question, relevant SQL query examples, and database schema information, generate a precise SQL query.
"""

        # CRITICAL: If we have pre-fetched ECodes, inject MANDATORY filter instruction at the top
        if prefetched_ecodes and len(prefetched_ecodes) > 0:
            ecodes_str = ", ".join([f"'{e.strip()}'" for e in prefetched_ecodes[:100]])  # Limit to 100
            prompt += f"""
[!!!] MANDATORY FILTER - DO NOT IGNORE [!!!]

This is a FOLLOW-UP QUERY. The user is asking about specific records from a previous query.
You MUST add this filter to your WHERE clause:

    WHERE e.Ecode IN ({ecodes_str})

OR if using a different table alias:

    WHERE <table_alias>.Ecode IN ({ecodes_str})

This filter is NON-NEGOTIABLE. Without it, your query will return wrong results.
The user asked about {len(prefetched_ecodes)} specific record(s) from their previous query.

[!!!] END MANDATORY FILTER [!!!]

"""

        # Add few-shot examples if available
        if few_shot_examples:
            import sys
            print(f"DEBUG: Adding {len(few_shot_examples)} few-shot examples", file=sys.stderr)
            logger.info(f"Adding {len(few_shot_examples)} few-shot examples to prompt")
            prompt += "\n" + few_shot_manager.format_examples_for_prompt(few_shot_examples)

        # Add retrieved schema context
        prompt += "\nDATABASE SCHEMA CONTEXT:\n"
        import sys
        print(f"DEBUG: Adding {len(schema_context['documents'])} schema docs", file=sys.stderr)
        logger.info(f"Adding {len(schema_context['documents'])} schema documents to prompt")
        for i, doc in enumerate(schema_context["documents"], 1):
            prompt += f"\n{i}. {doc}\n"
            # Log the first few lines of each doc to verify it's a view
            print(f"DEBUG: Schema Doc {i}: {doc[:100]}...", file=sys.stderr)
            logger.debug(f"Schema Doc {i}: {doc[:100]}...")

        # Add conversation history if available
        if conversation_history and len(conversation_history) > 0:
            prompt += "\n\nCONVERSATION HISTORY:\n"
            prompt += "Below is the recent conversation history. When the user uses pronouns like 'them', 'those', 'it', or refers to previous queries, check this history for context.\n"
            prompt += "IMPORTANT: Pay attention to which tables/views were used in previous queries to maintain consistency.\n"
            prompt += "CRITICAL: If the user asks about 'them' or 'those', use the RESULT_IDS from the previous query to filter with WHERE Ecode IN (...).\n\n"

            # Track the most recent result IDs for follow-up queries
            last_result_ids = None
            last_sql_query = None

            for msg in conversation_history:
                msg_type = msg.get("message_type", "")
                content = msg.get("message_content", "")

                if msg_type == "user":
                    prompt += f"USER: {content}\n"
                elif msg_type == "assistant":
                    # Parse the enriched content format
                    # Format: answer_text\n\n---CONTEXT_FOR_FOLLOWUP---\n[SQL_QUERY]: ...\n[RESULT_IDS]: ...\n[RESULT_COUNT]: ...

                    answer_part = content
                    sql_query = None
                    result_ids = None

                    # Check for our context marker
                    if "---CONTEXT_FOR_FOLLOWUP---" in content:
                        parts = content.split("---CONTEXT_FOR_FOLLOWUP---")
                        answer_part = parts[0].strip()
                        context_part = parts[1] if len(parts) > 1 else ""

                        # Parse context lines
                        for line in context_part.split("\n"):
                            line = line.strip()
                            if line.startswith("[SQL_QUERY]:"):
                                sql_query = line.replace("[SQL_QUERY]:", "").strip()
                                last_sql_query = sql_query
                            elif line.startswith("[RESULT_IDS]:"):
                                result_ids = line.replace("[RESULT_IDS]:", "").strip()
                                last_result_ids = result_ids
                    else:
                        # Legacy format - try to extract SQL from content
                        if "SELECT" in content or "select" in content:
                            lines = content.split('\n')
                            for line in lines:
                                if "SELECT" in line.upper():
                                    sql_query = line.strip()
                                    break

                    # Show answer summary (first 200 chars)
                    prompt += f"ASSISTANT: {answer_part[:200]}{'...' if len(answer_part) > 200 else ''}\n"
                    if sql_query:
                        prompt += f"  SQL USED: {sql_query}\n"
                    if result_ids:
                        # Show the IDs from previous query results
                        ids_list = result_ids.split(",")
                        prompt += f"  RESULT IDS (ECodes): {result_ids} ({len(ids_list)} records)\n"
                    prompt += "\n"

            # Add explicit instructions for using previous result IDs
            prompt += "\n[CRITICAL] FOLLOW-UP QUERY INSTRUCTIONS:\n"
            prompt += "1. Check conversation history to understand what 'them', 'those', 'it', 'these' refers to\n"
            prompt += "2. If RESULT_IDS are shown above from a previous query, you MUST filter your new query using:\n"
            prompt += "   WHERE e.Ecode IN (id1, id2, id3, ...) -- Always use table alias!\n"
            prompt += "   This ensures you query ONLY the records from the previous result set!\n"

            if last_result_ids:
                prompt += f"\n[!] PREVIOUS QUERY RETURNED THESE IDs: {last_result_ids}\n"
                prompt += f"   If user asks about 'them' or 'those', use: WHERE e.Ecode IN ({last_result_ids})\n"
            elif last_sql_query:
                # No IDs available (previous query was aggregation) - provide the SQL for reference
                prompt += f"\n[!] PREVIOUS QUERY (use this logic as a subquery/CTE for follow-up):\n"
                prompt += f"   {last_sql_query[:500]}{'...' if len(last_sql_query) > 500 else ''}\n"
                prompt += "\n   Since no RESULT_IDS are available (previous query was COUNT/aggregation),\n"
                prompt += "   you should REUSE the same CTE/WHERE conditions from the previous query to filter the same records.\n"
                prompt += "   Example: Copy the CTE and WHERE conditions, but change SELECT to get the new information.\n"

            prompt += "\n3. ALWAYS use table aliases (e.g., e.Ecode, lp.ECode) to avoid 'Ambiguous column name' errors\n"
            prompt += "4. If the previous query used a specific view/table, check the schema docs to see which columns that view/table has\n"
            prompt += "5. If the previous view doesn't have the columns you need, JOIN with another table or switch views\n"
            prompt += "6. Example: AllEmployeeUnion only has basic columns - for department info use vw_EmployeeMaster_Vms instead\n\n"

        prompt += f"""

USER QUESTION:
{question}

INSTRUCTIONS:
1. Study the example queries above to understand patterns and best practices
2. Analyze the user's question carefully
3. Use ONLY the tables and columns provided in the schema context above
4. Generate a valid SQL Server query (T-SQL syntax) similar to the examples
5. Use appropriate JOINs if multiple tables are needed
6. DO NOT use TOP clause - return ALL results (frontend handles pagination)
7. Use clear aliases for readability (e.g., e.Ecode, lp.ECode) to AVOID ambiguous column errors
8. Format dates appropriately for SQL Server (GETDATE(), DATEADD, etc.)
9. Ensure the query is safe and optimized
10. ALWAYS include Ecode/primary key in SELECT results when querying people/employees/students
    - This enables follow-up queries to filter on specific records
    - Example: SELECT e.Ecode, e.EmpName, ... FROM vw_EmployeeMaster_Vms e WHERE ...

[CRITICAL] VIEW-FIRST ARCHITECTURE - ALWAYS CHECK FOR VIEWS FIRST!

[!!!] MANDATORY POLICY [!!!]
Before writing ANY query, check if a VIEW exists that covers your requirements.
90% of queries can be answered using the 9 critical views below.
DO NOT manually JOIN base tables if a view already does it for you!

===========================================================================

**TIER 1 VIEWS - MUST USE FIRST** [5 STARS] (Priority: 5/5)

1. **vw_EmployeeMaster_Vms** [5 STARS]
   USE FOR: ANY employee query with department/section/branch
   COLUMNS: Ecode, CorpEmpCode, EmpName, Dname, SecName, BranchName, CName, Active, DateofJoin
   PRE-JOINS: 18 tables (EmployeeMaster + SectionMaster + DeptMaster + BranchMaster + ...)

   [YES] ALWAYS USE FOR:
   - "How many employees in each department?" -> SELECT Dname, COUNT(*) FROM vw_EmployeeMaster_Vms WHERE Active=1 GROUP BY Dname
   - "Show employees in IT department" -> SELECT * FROM vw_EmployeeMaster_Vms WHERE Active=1 AND Dname LIKE '%IT%'
   - "Employee count by branch" -> SELECT BranchName, COUNT(*) FROM vw_EmployeeMaster_Vms WHERE Active=1 GROUP BY BranchName
   - "List all active employees" -> SELECT Ecode, EmpName, Dname, SecName FROM vw_EmployeeMaster_Vms WHERE Active=1

   [NO] NEVER DO THIS:
   SELECT e.*, d.Dname FROM EmployeeMaster e JOIN SectionMaster s ON e.SecCode=s.SecCode JOIN DeptMaster d ON s.Dcode=d.Dcode

2. **vw_RawPunchDetail** [5 STARS]
   USE FOR: Raw punch/swipe records only (NOT for late arrivals!)
   COLUMNS: ATDate, ATTime, ECode, EmpName, Dname, MachineID, MachineName, InOut (1=IN, 0=OUT)
   PRE-JOINS: MachineRawPunch + EmployeeMaster + MachineMaster + DeptMaster + SectionMaster
   [!] WARNING: This view does NOT have InTime, OutTime, LateArrival, or WorkDuration columns!

   [YES] USE FOR:
   - "Show raw punches today" -> SELECT * FROM vw_RawPunchDetail WHERE ATDate = CAST(GETDATE() AS DATE)
   - "Show all swipes for employee" -> SELECT * FROM vw_RawPunchDetail WHERE ECode = '123'

   [NO] NEVER USE vw_RawPunchDetail FOR:
   - Late arrival queries (use vw_CompleteAttendanceReport instead)
   - Work hours queries (use vw_CompleteAttendanceReport instead)
   - InTime/OutTime queries (use vw_CompleteAttendanceReport instead)

3. **vw_CompleteAttendanceReport** [5 STARS] (CRITICAL FOR LATE ARRIVALS!)
   USE FOR: Late arrivals, early departures, work hours, attendance status
   COLUMNS: ATDate, CorpEmpCode, EmpName, Dname, InTime, OutTime, LateArrival (minutes), EarlyDeparture (minutes), WorkDuration (minutes), Status

   [YES] ALWAYS USE FOR:
   - "Who was late today?" -> SELECT CorpEmpCode, EmpName, Dname, InTime, LateArrival FROM vw_CompleteAttendanceReport WHERE ATDate = CAST(GETDATE() AS DATE) AND LateArrival > 0
   - "Who left early?" -> SELECT CorpEmpCode, EmpName, OutTime, EarlyDeparture FROM vw_CompleteAttendanceReport WHERE ATDate = CAST(GETDATE() AS DATE) AND EarlyDeparture > 0
   - "Show work hours" -> SELECT CorpEmpCode, EmpName, WorkDuration FROM vw_CompleteAttendanceReport WHERE ATDate = CAST(GETDATE() AS DATE)

   [NO] NEVER DO THIS:
   SELECT m.*, e.EmpName FROM MachineRawPunch m JOIN EmployeeMaster e ON m.ECode=e.Ecode

4. **AllEmployeeUnion** [5 STARS]
   USE FOR: Total employee count (active + deleted)
   UNION OF: EmployeeMaster + EmployeeMaster_Deleted

   [YES] ALWAYS USE FOR:
   - "How many total employees?" -> SELECT COUNT(*) FROM AllEmployeeUnion WHERE Active=1
   - "All employees (including deleted)" -> SELECT * FROM AllEmployeeUnion

   [NO] NEVER DO THIS:
   SELECT COUNT(*) FROM EmployeeMaster WHERE Active=1

===========================================================================

**TIER 2 VIEWS - DOMAIN-SPECIFIC** [4 STARS] (Priority: 3/5)

4. **View_Visitor_EnrollmentDetail** [4 STARS]
   USE FOR: Visitor management queries
   Example: SELECT * FROM View_Visitor_EnrollmentDetail WHERE EnrollmentDate = CAST(GETDATE() AS DATE)

5. **View_Contractor_Detail** [4 STARS]
   USE FOR: Contractor information queries
   Example: SELECT * FROM View_Contractor_Detail WHERE Active=1

6. **View_Employee_Terminal_Authentication_Relation** [5 STARS] (CRITICAL FOR DEVICE DATA PUSH!)
   USE FOR: Device data push queries, biometric access control, face access, fingerprint access
   COLUMNS: Ecode, CorpEmpCode, EmpName, DomainName (device name), AuthenticationID, Status

   [CRITICAL] AuthenticationID VALUES (MUST USE THESE!):
   - AuthenticationID = 2: Fingerprint access
   - AuthenticationID = 3: Card/Finger access
   - AuthenticationID = 7: Face Only access (use this for "face access" queries!)
   - AuthenticationID = 1001: REMOVED from device (use this for "removed" queries!)

   [YES] ALWAYS USE FOR:
   - "Who has face access?" -> WHERE AuthenticationID = 7
   - "Which students have face access on SUBWAY?" -> WHERE AuthenticationID = 7 AND DomainName LIKE '%SUBWAY%'
   - "Who is removed from devices?" -> WHERE AuthenticationID = 1001
   - "Device data push queries" -> Use View_Employee_Terminal_Authentication_Relation

   Example: SELECT DISTINCT CorpEmpCode, EmpName, DomainName FROM View_Employee_Terminal_Authentication_Relation WHERE AuthenticationID = 7 AND DomainName LIKE '%SUBWAY%'

7. **View_EmployeeByUserGroupPolicy** [4 STARS]
   USE FOR: User group/policy queries
   Example: SELECT * FROM View_EmployeeByUserGroupPolicy WHERE GroupName='Admin'

===========================================================================

**TIER 3 VIEWS - SPECIALIZED** [3 STARS] (Priority: 2/5)

8. **Vw_TerminalDetail_VMS** [3 STARS]
   USE FOR: Terminal/device configuration queries
   Example: SELECT * FROM Vw_TerminalDetail_VMS WHERE Status='Online'

9. **vw_VisitorBasicDetail** [3 STARS]
   USE FOR: Basic visitor lookup
   Example: SELECT * FROM vw_VisitorBasicDetail WHERE VisitorName LIKE '%John%'

===========================================================================

[!!!] MANDATORY: FACE ACCESS QUERY PATTERN [!!!]

When user asks about "face access", "who has face access", "face recognition access", "face data push":
-> ALWAYS use View_Employee_Terminal_Authentication_Relation with AuthenticationID = 7

[NO] WRONG - DO NOT DO THIS:
SELECT * FROM View_FACE_V1  -- This is for biometric images, NOT access control!
SELECT * FROM Biometric WHERE Format IN (250, 401)  -- Wrong table!

[YES] CORRECT - ALWAYS DO THIS:
SELECT CorpEmpCode, EmpName, DomainName FROM View_Employee_Terminal_Authentication_Relation
WHERE AuthenticationID = 7  -- 7 = Face Only access

===========================================================================

[!!!] DEPRECATED TABLES - DO NOT USE [!!!]

[NO] **EmpDepartRole** - EMPTY TABLE (0 rows)
   Replacement: Use vw_EmployeeMaster_Vms (has Dname column)

   [NO] WRONG: SELECT * FROM EmpDepartRole
   [YES] CORRECT: SELECT * FROM vw_EmployeeMaster_Vms

[NO] **View_FACE_V1** - This is for biometric IMAGES, NOT for access control!
   DO NOT USE for "face access" queries!
   Replacement: Use View_Employee_Terminal_Authentication_Relation WHERE AuthenticationID = 7

   [NO] WRONG: SELECT * FROM View_FACE_V1 (this is biometric image data!)
   [YES] CORRECT: SELECT * FROM View_Employee_Terminal_Authentication_Relation WHERE AuthenticationID = 7

===========================================================================

**CRITICAL EXAMPLES - LEARN FROM THESE:**

Example 1: Department employee count
[NO] WRONG: SELECT d.Dname, COUNT(e.Ecode) FROM EmployeeMaster e JOIN SectionMaster s ON e.SecCode=s.SecCode JOIN DeptMaster d ON s.Dcode=d.Dcode WHERE e.Active=1 GROUP BY d.Dname
[YES] CORRECT: SELECT Dname, COUNT(*) AS EmployeeCount FROM dbo.vw_EmployeeMaster_Vms WHERE Active=1 GROUP BY Dname ORDER BY EmployeeCount DESC

Example 2: Today's attendance
[NO] WRONG: SELECT m.ATDate, e.EmpName FROM MachineRawPunch m JOIN EmployeeMaster e ON m.ECode=e.Ecode WHERE m.ATDate=CAST(GETDATE() AS DATE)
[YES] CORRECT: SELECT ATDate, EmpName, InTime, OutTime FROM dbo.vw_RawPunchDetail WHERE ATDate=CAST(GETDATE() AS DATE)

Example 3: Active employee count
[NO] WRONG: SELECT COUNT(*) FROM EmployeeMaster WHERE Active=1
[YES] CORRECT: SELECT COUNT(*) FROM dbo.AllEmployeeUnion WHERE Active=1

Example 4: FACE ACCESS QUERIES (MANDATORY PATTERN!)
Question: "Which students have face access on SUBWAY devices?"
[NO] WRONG: SELECT * FROM View_FACE_V1 (this is for biometric images!)
[NO] WRONG: SELECT * FROM Employee_Terminal_Authentication_Relation (missing AuthenticationID filter!)
[YES] CORRECT: SELECT v.CorpEmpCode, v.EmpName, v.DomainName FROM dbo.View_Employee_Terminal_Authentication_Relation v JOIN dbo.vw_EmployeeMaster_Vms e ON v.Ecode = e.Ecode WHERE v.AuthenticationID = 7 AND v.DomainName LIKE '%SUBWAY%' AND e.AccessType = 'Student'

**FACE ACCESS = AuthenticationID = 7** (NEVER forget this filter!)

CRITICAL COLUMN NAME RULES:
[!] DO NOT hallucinate or invent column names that "sound right" but aren't in the schema!
[!] Use EXACT column names from the schema above, even if they are abbreviated
[!] Common mistakes to AVOID:
   - DO NOT use "DeptCode" - the actual column is "SecCode" (Section/Department Code)
   - DO NOT use "DeptName" - use the actual column names listed in the schema
   - DO NOT use "EmployeeCode" - the actual column is "Ecode"
   - DO NOT assume standard names - VERIFY each column exists in the schema
[!] If the schema says "SecCode", use "SecCode" - do NOT rename it to "DepartmentCode"
[!] Before writing SELECT/WHERE/GROUP BY, cross-check every column name against the schema

IMPORTANT RULES:
- Only return the SQL query, nothing else
- Do NOT include markdown code blocks or explanations
- Use SQL Server syntax (not MySQL or PostgreSQL)
- Always validate column names against the schema provided
- Follow the patterns shown in the examples above
- PREFER VIEWS over manual table JOINs whenever possible

SQL QUERY:"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """
        Call the configured LLM (Gemini or OpenRouter) to generate SQL

        Args:
            prompt: Complete prompt with question and schema

        Returns:
            Generated SQL query string
        """
        if self.llm_provider == 'openrouter':
            return self._call_openrouter(prompt)
        else:
            return self._call_gemini(prompt)

    async def _call_llm_async(self, prompt: str) -> str:
        """
        PERFORMANCE OPTIMIZED: Async wrapper for LLM calls.

        Uses asyncio.to_thread() to run blocking LLM calls in a thread pool,
        allowing the event loop to handle other requests while waiting.

        Args:
            prompt: Complete prompt with question and schema

        Returns:
            Generated SQL query string
        """
        logger.debug("[SQL_AGENT] Running LLM call in thread pool for non-blocking execution")
        return await asyncio.to_thread(self._call_llm, prompt)

    def _call_openrouter(self, prompt: str) -> str:
        """
        Call OpenRouter API to generate SQL

        Args:
            prompt: Complete prompt with question and schema

        Returns:
            Generated SQL query string
        """
        try:
            logger.info(f"[SQL_AGENT] Calling OpenRouter API with model: {self.openrouter_model}")

            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://oryggi.ai",
                "X-Title": "OryggiAI SQL Agent"
            }

            payload = {
                "model": self.openrouter_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert SQL query generator for SQL Server databases. Generate only valid T-SQL queries. Return ONLY the SQL query without any explanation, markdown, or code blocks."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": getattr(settings, 'gemini_max_tokens', 2000),
            }

            response = requests.post(
                f"{self.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = f"OpenRouter API error: {response.status_code} - {response.text}"
                logger.error(f"[SQL_AGENT] {error_msg}")
                raise Exception(error_msg)

            result = response.json()

            # Extract the SQL query from the response
            if 'choices' in result and len(result['choices']) > 0:
                sql_query = result['choices'][0]['message']['content'].strip()

                # Log which model was actually used (OpenRouter may route to different models)
                if 'model' in result:
                    logger.info(f"[SQL_AGENT] OpenRouter used model: {result['model']}")

                logger.info(f"[SQL_AGENT] OpenRouter response received, length: {len(sql_query)}")
                return sql_query
            else:
                raise Exception("OpenRouter returned empty response")

        except requests.exceptions.Timeout:
            logger.error("[SQL_AGENT] OpenRouter API timeout")
            raise Exception("OpenRouter API request timed out")
        except Exception as e:
            logger.error(f"[SQL_AGENT] OpenRouter API call failed: {str(e)}")
            raise

    def _call_gemini(self, prompt: str) -> str:
        """
        Call Gemini API to generate SQL

        Args:
            prompt: Complete prompt with question and schema

        Returns:
            Generated SQL query string
        """
        try:
            # Configure generation settings
            generation_config = {
                "temperature": self.temperature,
                "max_output_tokens": settings.gemini_max_tokens,
            }

            # Configure safety settings to allow SQL generation
            # SQL queries are legitimate code generation, not harmful content
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # Debug: Check response details
            logger.debug(f"Response finish_reason: {response.candidates[0].finish_reason if response.candidates else 'No candidates'}")
            if response.candidates:
                logger.debug(f"Safety ratings: {response.candidates[0].safety_ratings}")

            # Handle safety blocking
            if not response.text:
                if response.candidates and response.candidates[0].finish_reason == 2:
                    error_msg = "Gemini blocked SQL generation due to safety filters. "
                    if response.candidates[0].safety_ratings:
                        blocked_categories = [
                            f"{rating.category}: {rating.probability}"
                            for rating in response.candidates[0].safety_ratings
                            if rating.probability not in ["NEGLIGIBLE", "LOW"]
                        ]
                        if blocked_categories:
                            error_msg += f"Blocked categories: {', '.join(blocked_categories)}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            sql_query = response.text.strip()
            return sql_query

        except Exception as e:
            logger.error(f"[SQL_AGENT] Gemini API call failed: {str(e)}")
            raise

    def _clean_sql(self, sql_query: str) -> str:
        """
        Clean and validate generated SQL

        Args:
            sql_query: Raw SQL from Gemini

        Returns:
            Cleaned SQL query
        """
        # Remove markdown code blocks if present
        if sql_query.startswith("```"):
            lines = sql_query.split("\n")
            sql_query = "\n".join(lines[1:-1]) if len(lines) > 2 else sql_query

        # Remove common prefixes
        sql_query = sql_query.strip()
        if sql_query.lower().startswith("sql"):
            sql_query = sql_query[3:].strip()

        # Remove trailing semicolons (not needed for pyodbc)
        sql_query = sql_query.rstrip(";")
        
        # FIX: Validate and fix malformed COUNT syntax
        # Common error: "SELECT COUNT FROM..." instead of "SELECT COUNT(*) FROM..."
        import re
        
        # Pattern to find malformed COUNT (COUNT followed by FROM without parentheses)
        malformed_count_pattern = r'\bCOUNT\s+FROM\b'
        if re.search(malformed_count_pattern, sql_query, re.IGNORECASE):
            logger.warning("[WARNING] Detected malformed COUNT syntax (missing parentheses). Auto-correcting...")
            sql_query = re.sub(malformed_count_pattern, 'COUNT(*) FROM', sql_query, flags=re.IGNORECASE)
            logger.info(f"[OK] Corrected SQL: {sql_query[:100]}...")
        
        # Also check for COUNT at the end of SELECT (e.g., "SELECT COUNT" with nothing after)
        malformed_count_end = r'\bSELECT\s+COUNT\s*$'
        if re.search(malformed_count_end, sql_query, re.IGNORECASE):
            logger.warning("[WARNING] Detected incomplete COUNT syntax. Adding (*) FROM...")
            sql_query = re.sub(malformed_count_end, 'SELECT COUNT(*) FROM', sql_query, flags=re.IGNORECASE)

        return sql_query

    def execute_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Execute generated SQL query

        Args:
            sql_query: SQL query to execute

        Returns:
            List of result rows as dictionaries
        """
        logger.info(f"Executing SQL: {sql_query[:100]}...")
        
        # DEBUG: Log the full SQL query
        import sys
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"FULL SQL QUERY BEING EXECUTED:", file=sys.stderr)
        print(sql_query, file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
        
        # Validation: Check if it's a comment instead of SQL
        if sql_query.strip().startswith("--") or sql_query.strip().startswith("/*"):
            error_msg = "LLM generated a comment instead of SQL. This usually means it couldn't find relevant tables."
            logger.error(f"[ERROR] {error_msg}")
            # Return empty list or raise specific error that UI can handle gracefully
            # For now, raising error so it's caught and logged
            raise ValueError(error_msg)

        try:
            results = db_manager.execute_query(sql_query)
            logger.info(f"[OK] Query returned {len(results)} rows")
            return results

        except Exception as e:
            logger.error(f"[ERROR] Query execution failed: {str(e)}")
            print(f"ERROR DETAILS: {type(e).__name__}: {str(e)}", file=sys.stderr)
            raise

    def query_and_answer(self, question: str) -> Dict[str, Any]:
        """
        Complete workflow: generate SQL, execute, and format answer

        Args:
            question: User's natural language question

        Returns:
            Dict with sql_query, results, and natural_answer
        """
        logger.info(f"Processing question: {question}")

        try:
            # Generate SQL
            sql_result = self.generate_sql(question)
            sql_query = sql_result["sql_query"]

            # Execute query
            results = self.execute_query(sql_query)

            # Format natural language answer (include SQL query in the answer)
            natural_answer = self._format_answer(question, results, sql_query=sql_query)

            return {
                "sql_query": sql_query,
                "results": results,
                "result_count": len(results),
                "natural_answer": natural_answer,
                "tables_used": sql_result["tables_referenced"]
            }

        except Exception as e:
            logger.error(f"[ERROR] Query processing failed: {str(e)}")
            return {
                "sql_query": None,
                "results": [],
                "result_count": 0,
                "natural_answer": f"I encountered an error: {str(e)}",
                "error": str(e)
            }

    def _format_answer(
        self,
        question: str,
        results: List[Dict[str, Any]],
        max_rows: int = 10,
        sql_query: str = None
    ) -> str:
        """
        Format query results into natural language answer

        Args:
            question: Original question
            results: Query results
            max_rows: Maximum rows to include in answer
            sql_query: The SQL query that was executed

        Returns:
            Natural language answer string
        """
        # Start with empty answer (SQL query hidden from user response)
        answer = ""
        # Note: SQL query is still available in the API response for debugging
        # but not shown in the natural_answer text

        if not results:
            return "No results found for your query."

        # Return empty string - results are shown in the table UI
        # No need to duplicate data in text format
        return ""


# Global SQL agent instance
sql_agent = RAGSQLAgent()
