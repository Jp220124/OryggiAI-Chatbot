"""
Tenant SQL Agent
Multi-tenant SQL agent that uses GLOBAL shared schema and few-shot examples.

ARCHITECTURE: All tenants use the SAME Oryggi Access Control database schema.
- Same tables (Employee, Cards, Doors, AccessLogs, etc.)
- Same views (vw_EmployeeMaster_Vms, vw_CardDetails, etc.)
- Only DATA differs per tenant (different employees, different buildings)

Therefore, we use GLOBAL shared resources:
- ChromaDB: database_schema collection (Oryggi schema embeddings)
- FAISS: few_shot_examples.json (Q&A pairs for Oryggi schema)

This works because the same SQL queries apply to ALL tenants!

CLARIFICATION SUPPORT (Light Mode):
- Only triggers for VERY unclear queries (threshold 0.5)
- Uses fast heuristics first, LLM only for edge cases
- Returns clarification options when needed
"""

from typing import Dict, Any, Optional, List
import json
import requests
import time
from loguru import logger
from sqlalchemy.orm import Session
import uuid
import google.generativeai as genai

from app.config import settings
from app.models.platform import TenantDatabase, SchemaCache, FewShotExample
from app.database.tenant_connection import tenant_db_manager
from app.gateway.query_router import query_router
from app.services.query_logging_service import get_query_logging_service

# GLOBAL shared managers - used by ALL tenants (same schema)
from app.rag import chroma_manager, few_shot_manager

# Clarity assessment for light clarification
from app.services.clarity_assessor import clarity_assessor, ClarityAssessment


class TenantSQLAgent:
    """
    Multi-tenant SQL Agent with GLOBAL RAG Enhancement

    ARCHITECTURE: All Oryggi clients use the SAME database schema.
    Therefore, we use GLOBAL shared resources for ALL tenants:
    - ChromaDB: database_schema collection (Oryggi schema embeddings)
    - FAISS: few_shot_examples.json (Q&A pairs for Oryggi schema)

    The same SQL queries work for ALL tenants - only the DATA differs.
    Supports multiple LLM providers: OpenRouter (default) and Gemini.

    CLARIFICATION: Light mode - only for very unclear queries.
    """

    # Light clarification threshold - lower than main chatbot (0.7)
    # Only trigger for VERY unclear queries
    LIGHT_CLARITY_THRESHOLD = 0.5
    MAX_CLARIFICATION_ATTEMPTS = 3

    def __init__(self):
        """Initialize Tenant SQL Agent with LLM client"""
        self.llm_provider = settings.llm_provider.lower()
        self.temperature = settings.gemini_temperature

        if self.llm_provider == "gemini":
            # Initialize Gemini
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(settings.gemini_model)
            self.HarmCategory = HarmCategory
            self.HarmBlockThreshold = HarmBlockThreshold
            logger.info(f"[TENANT_AGENT] Initialized with Gemini: {settings.gemini_model}")
        else:
            # OpenRouter configuration
            self.openrouter_api_key = settings.openrouter_api_key
            self.openrouter_model = settings.openrouter_model
            self.openrouter_base_url = settings.openrouter_base_url
            logger.info(f"[TENANT_AGENT] Initialized with OpenRouter: {self.openrouter_model}")

        logger.info("[TENANT_AGENT] Using GLOBAL ChromaDB and FAISS (same schema for all tenants)")

    def _is_clarification_response(
        self,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Check if user is responding to a previous clarification question.

        Looks at the last assistant message to see if it was a clarification request.
        If so, returns the original question that needed clarification.

        Args:
            conversation_history: List of previous messages

        Returns:
            Dict with:
            - is_response: True if user is responding to clarification
            - original_question: The original unclear question (if found)
            - clarification_asked: The clarification question that was asked
        """
        if not conversation_history or len(conversation_history) < 2:
            return {"is_response": False}

        # Look for the last assistant message
        last_assistant_msg = None
        original_user_question = None

        # Scan in reverse to find last assistant message and the user question before it
        for i in range(len(conversation_history) - 1, -1, -1):
            msg = conversation_history[i]
            msg_type = msg.get("message_type", "")

            if msg_type == "assistant" and last_assistant_msg is None:
                last_assistant_msg = msg
            elif msg_type == "user" and last_assistant_msg is not None:
                original_user_question = msg.get("message_content", "")
                break

        if not last_assistant_msg:
            return {"is_response": False}

        assistant_content = last_assistant_msg.get("message_content", "").lower()
        tools_used = last_assistant_msg.get("tools_used", [])

        # Check if the assistant message was a clarification request
        clarification_indicators = [
            "could you please",
            "could you specify",
            "what would you like",
            "can you clarify",
            "please clarify",
            "what do you mean",
            "which",
            "what information",
            "what kind of",
            "what type of",
            "what aspect",
            "?" in assistant_content and len(assistant_content) < 200  # Short questions
        ]

        # Also check if clarity_assessment tool was used
        is_clarification = (
            "clarity_assessment" in tools_used or
            any(indicator in assistant_content for indicator in clarification_indicators if isinstance(indicator, str)) or
            (clarification_indicators[-1] if isinstance(clarification_indicators[-1], bool) else False)
        )

        if is_clarification:
            logger.info(f"[TENANT_AGENT:CLARITY] Detected clarification response flow")
            return {
                "is_response": True,
                "original_question": original_user_question,
                "clarification_asked": last_assistant_msg.get("message_content", "")
            }

        return {"is_response": False}

    async def _check_light_clarity(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Light clarity check - only triggers for VERY unclear queries.

        Uses a lower threshold (0.5) compared to main chatbot (0.7).
        This means most queries pass through without clarification.

        IMPORTANT: If the user is responding to a previous clarification,
        we skip the clarity check and combine their response with the original question.

        Args:
            question: User's question
            conversation_history: Previous conversation context

        Returns:
            Dict with:
            - needs_clarification: bool
            - clarification_question, clarification_options (if needs_clarification)
            - combined_question (if user responded to clarification)
            - skip_clarity_check (if user is responding to clarification)
        """
        try:
            # FIRST: Check if user is responding to a previous clarification
            clarification_check = self._is_clarification_response(conversation_history)

            if clarification_check.get("is_response"):
                original_question = clarification_check.get("original_question", "")
                clarification_asked = clarification_check.get("clarification_asked", "")

                # Combine original question + user's response
                combined_question = f"{original_question} - {question}"
                logger.info(f"[TENANT_AGENT:CLARITY] User responding to clarification")
                logger.info(f"[TENANT_AGENT:CLARITY] Original: '{original_question}'")
                logger.info(f"[TENANT_AGENT:CLARITY] Response: '{question}'")
                logger.info(f"[TENANT_AGENT:CLARITY] Combined: '{combined_question}'")

                return {
                    "needs_clarification": False,
                    "skip_clarity_check": True,
                    "combined_question": combined_question,
                    "original_question": original_question
                }

            # Fast heuristic check first (no LLM call)
            heuristic_result = clarity_assessor._check_heuristics(question)

            if heuristic_result is not None:
                # Heuristic determined clarity
                if heuristic_result.is_clear:
                    logger.info(f"[TENANT_AGENT:CLARITY] Heuristic: CLEAR ({heuristic_result.reason})")
                    return {"needs_clarification": False}

                # Only ask for clarification if confidence is VERY low (< 0.5)
                if heuristic_result.confidence < self.LIGHT_CLARITY_THRESHOLD:
                    logger.info(f"[TENANT_AGENT:CLARITY] Heuristic: UNCLEAR (confidence={heuristic_result.confidence})")

                    # Generate clarification question
                    clarification = await clarity_assessor.generate_clarifying_question(
                        question=question,
                        assessment=heuristic_result,
                        previous_clarifications=[]
                    )

                    return {
                        "needs_clarification": True,
                        "clarification_question": clarification.question,
                        "clarification_options": clarification.options
                    }
                else:
                    # Borderline case - let it through (light mode is lenient)
                    logger.info(f"[TENANT_AGENT:CLARITY] Heuristic: BORDERLINE, allowing (confidence={heuristic_result.confidence})")
                    return {"needs_clarification": False}

            # For edge cases, do a quick LLM check
            assessment = await clarity_assessor.assess_clarity(question, conversation_history)

            # Light mode: only trigger if confidence is VERY low
            if not assessment.is_clear and assessment.confidence < self.LIGHT_CLARITY_THRESHOLD:
                logger.info(f"[TENANT_AGENT:CLARITY] LLM: UNCLEAR (confidence={assessment.confidence})")

                clarification = await clarity_assessor.generate_clarifying_question(
                    question=question,
                    assessment=assessment,
                    previous_clarifications=[]
                )

                return {
                    "needs_clarification": True,
                    "clarification_question": clarification.question,
                    "clarification_options": clarification.options
                }

            logger.info(f"[TENANT_AGENT:CLARITY] LLM: CLEAR (confidence={assessment.confidence})")
            return {"needs_clarification": False}

        except Exception as e:
            # On error, don't block - allow query to proceed
            logger.warning(f"[TENANT_AGENT:CLARITY] Check failed, allowing query: {e}")
            return {"needs_clarification": False}

    async def process_query(
        self,
        question: str,
        tenant_database: TenantDatabase,
        platform_db: Session,
        user_id: str = "system",
        user_role: str = "ADMIN",
        conversation_history: Optional[List[Dict]] = None,
        conversation_id: str = None,
        # Clarification parameters
        clarification_response: Optional[str] = None,
        original_unclear_question: Optional[str] = None,
        clarification_attempt: int = 0
    ) -> Dict[str, Any]:
        """
        Process a natural language query for a specific tenant database

        Args:
            question: User's natural language question
            tenant_database: TenantDatabase model instance
            platform_db: SQLAlchemy session for platform database
            user_id: User identifier
            user_role: User's role
            conversation_history: Optional conversation history
            conversation_id: Chat conversation ID for logging
            clarification_response: User's response to a clarification question
            original_unclear_question: The original question that needed clarification
            clarification_attempt: Current clarification attempt number

        Returns:
            Dict with sql_query, results, natural_answer, etc.
            If clarification needed: includes needs_clarification, clarification_question, clarification_options
        """
        tenant_db_id = tenant_database.id
        logger.info(f"[TENANT_AGENT] Processing query for tenant DB: {tenant_database.name}")
        logger.info(f"[TENANT_AGENT] Question: {question}")

        # =====================================================
        # LIGHT CLARIFICATION CHECK (Only for very unclear queries)
        # =====================================================
        # Skip clarity check if this is an explicit clarification response (from API params)
        is_explicit_clarification = bool(clarification_response and original_unclear_question)

        if is_explicit_clarification:
            # Explicit clarification response via API parameters
            logger.info(f"[TENANT_AGENT] Processing explicit clarification response: {clarification_response}")
            question = f"{original_unclear_question} - {clarification_response}"
        else:
            # Run clarity check (will also detect implicit clarification responses from history)
            clarity_result = await self._check_light_clarity(question, conversation_history)

            if clarity_result.get("needs_clarification"):
                logger.info(f"[TENANT_AGENT] Light clarification triggered for: {question}")
                return {
                    "success": True,
                    "needs_clarification": True,
                    "clarification_question": clarity_result.get("clarification_question"),
                    "clarification_options": clarity_result.get("clarification_options"),
                    "clarification_attempt": clarification_attempt + 1,
                    "max_clarification_attempts": self.MAX_CLARIFICATION_ATTEMPTS,
                    "original_question": question,
                    "sql_query": None,
                    "results": [],
                    "result_count": 0,
                    "natural_answer": clarity_result.get("clarification_question", "Could you please clarify?"),
                    "tables_used": [],
                    "tenant_db_name": tenant_database.name,
                    "error": None
                }

            # Check if user was responding to a clarification (auto-detected from history)
            if clarity_result.get("combined_question"):
                logger.info(f"[TENANT_AGENT] Using combined question from clarification response")
                question = clarity_result.get("combined_question")

        # Initialize logging service
        query_logging_service = get_query_logging_service()
        request_id = None
        sql_query = None
        generation_start_time = time.time()

        try:
            # Use GLOBAL ChromaDB and FAISS - same schema for ALL tenants
            # All Oryggi clients have identical database structure, only data differs

            # Step 1: Get schema context from GLOBAL ChromaDB
            schema_context = self._get_global_schema_context(question)
            logger.info(f"[TENANT_AGENT] Retrieved {len(schema_context)} schema items from GLOBAL ChromaDB")

            # Step 2: Get few-shot examples from GLOBAL FAISS
            few_shot_examples = self._get_global_fewshots(question)
            logger.info(f"[TENANT_AGENT] Retrieved {len(few_shot_examples)} few-shot examples from GLOBAL FAISS")

            # Step 3: Build prompt with tenant-specific context
            prompt = self._build_prompt(
                question=question,
                schema_context=schema_context,
                few_shot_examples=few_shot_examples,
                conversation_history=conversation_history,
                db_type=tenant_database.db_type
            )

            # Step 4: Generate SQL using LLM
            sql_query = self._generate_sql(prompt)
            sql_query = self._clean_sql(sql_query)
            generation_time_ms = int((time.time() - generation_start_time) * 1000)
            logger.info(f"[TENANT_AGENT] Generated SQL: {sql_query[:100]}...")

            # Step 4.5: Log the query (synchronous, non-blocking)
            llm_model = settings.gemini_model if self.llm_provider == "gemini" else self.openrouter_model
            try:
                request_id = query_logging_service.log_query(
                    tenant_id=tenant_database.tenant_id,
                    database_id=tenant_database.id,
                    sql_query=sql_query,
                    natural_language_question=question,
                    user_id=uuid.UUID(user_id) if user_id and user_id != "system" else None,
                    conversation_id=conversation_id,
                    llm_model=llm_model,
                    generation_time_ms=generation_time_ms,
                )
            except Exception as log_error:
                logger.warning(f"[TENANT_AGENT] Failed to log query (non-fatal): {log_error}")

            # Step 5: Execute query on tenant's database (using query_router for gateway support)
            execution_start_time = time.time()
            results = await query_router.execute_query(
                tenant_database=tenant_database,
                query=sql_query,
                timeout=60,
                max_rows=1000,
            )
            execution_time_ms = int((time.time() - execution_start_time) * 1000)
            logger.info(f"[TENANT_AGENT] Query returned {len(results)} rows in {execution_time_ms}ms")

            # Step 5.5: Update query log with success result
            if request_id:
                try:
                    query_logging_service.update_query_result(
                        request_id=request_id,
                        success=True,
                        row_count=len(results),
                        execution_time_ms=execution_time_ms,
                    )
                except Exception as log_error:
                    logger.warning(f"[TENANT_AGENT] Failed to update query log (non-fatal): {log_error}")

            # Step 6: Format natural language answer
            natural_answer = self._format_answer(question, results)

            return {
                "success": True,
                "sql_query": sql_query,
                "results": results,
                "result_count": len(results),
                "natural_answer": natural_answer,
                "tables_used": self._extract_tables_from_sql(sql_query),
                "tenant_db_name": tenant_database.name,
                "request_id": request_id,
                "error": None
            }

        except Exception as e:
            logger.error(f"[TENANT_AGENT] Query processing failed: {str(e)}", exc_info=True)

            # Update query log with error if we have a request_id
            if request_id:
                try:
                    query_logging_service.update_query_result(
                        request_id=request_id,
                        success=False,
                        error_message=str(e),
                        error_code="QUERY_FAILED",
                    )
                except Exception as log_error:
                    logger.warning(f"[TENANT_AGENT] Failed to update query log with error (non-fatal): {log_error}")

            return {
                "success": False,
                "sql_query": sql_query,
                "results": [],
                "result_count": 0,
                "natural_answer": f"I encountered an error: {str(e)}",
                "tables_used": [],
                "tenant_db_name": tenant_database.name,
                "request_id": request_id,
                "error": str(e)
            }

    def _get_global_schema_context(
        self,
        question: str,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get schema context from GLOBAL ChromaDB (shared across all tenants)

        Since all tenants use the same Oryggi schema, we use the shared
        ChromaDB embeddings for RAG-based schema retrieval.

        Args:
            question: User's natural language question
            n_results: Number of schema items to retrieve

        Returns:
            List of schema context dictionaries for prompt
        """
        try:
            # Query global ChromaDB for relevant schemas
            results = chroma_manager.query_schemas(question, n_results=n_results)

            context = []
            for i, (doc, metadata) in enumerate(zip(results.get("documents", []), results.get("metadatas", []))):
                context.append({
                    "table_name": metadata.get("table_name", metadata.get("table", "unknown")),
                    "table_type": metadata.get("table_type", "table"),
                    "schema_name": metadata.get("schema_name", "dbo"),
                    "columns": [],  # Full column info not stored in ChromaDB
                    "row_count": metadata.get("row_count", 0),
                    "description": metadata.get("description", ""),
                    "document": doc  # The full schema document text
                })

            logger.info(f"[TENANT_AGENT] Global ChromaDB returned {len(context)} relevant schemas")
            return context

        except Exception as e:
            logger.error(f"[TENANT_AGENT] Failed to get global schema context: {str(e)}")
            return []

    def _get_global_fewshots(
        self,
        question: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant few-shot examples from GLOBAL FAISS (shared across all tenants)

        Since all tenants use the same Oryggi schema, we use the shared
        few-shot examples from data/few_shot_examples.json via FAISS.

        Args:
            question: User's natural language question
            n_results: Number of examples to retrieve

        Returns:
            List of few-shot example dictionaries
        """
        try:
            # Query global FAISS for relevant few-shot examples
            examples = few_shot_manager.get_relevant_examples(question, n_results=n_results)

            formatted_examples = []
            for ex in examples:
                formatted_examples.append({
                    "question": ex.get("question", ""),
                    "sql": ex.get("sql", ""),
                    "explanation": ex.get("explanation", ""),
                    "module": ex.get("category", ""),  # Map category to module
                    "category": ex.get("category", "")
                })

            logger.info(f"[TENANT_AGENT] Global FAISS returned {len(formatted_examples)} relevant examples")
            return formatted_examples

        except Exception as e:
            logger.error(f"[TENANT_AGENT] Failed to get global few-shots: {str(e)}")
            return []

    # Keep old methods for backward compatibility (can be removed later)
    def _get_tenant_schema_context(
        self,
        platform_db: Session,
        tenant_db_id: uuid.UUID
    ) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Get schema context from SchemaCache for this tenant database
        Use _get_global_schema_context() instead for shared schema approach.
        """
        schema_records = platform_db.query(SchemaCache).filter(
            SchemaCache.tenant_db_id == tenant_db_id
        ).all()

        context = []
        for schema in schema_records:
            columns = []
            if schema.column_info:
                try:
                    columns = json.loads(schema.column_info)
                except json.JSONDecodeError:
                    pass

            schema_doc = f"Table: {schema.table_name} ({schema.table_type})"
            if columns:
                col_names = [c.get("column_name", c.get("name", "")) for c in columns]
                schema_doc += f"\nColumns: {', '.join(col_names[:20])}"
            if schema.llm_description:
                schema_doc += f"\nDescription: {schema.llm_description}"
            if schema.detected_module:
                schema_doc += f"\nModule: {schema.detected_module}"

            context.append({
                "table_name": schema.table_name,
                "table_type": schema.table_type,
                "schema_name": schema.schema_name,
                "columns": columns,
                "row_count": schema.row_count,
                "description": schema.llm_description,
                "document": schema_doc
            })

        return context

    def _get_tenant_fewshots(
        self,
        platform_db: Session,
        tenant_db_id: uuid.UUID,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Get few-shot examples from FewShotExample for this tenant database
        Use _get_global_fewshots() instead for shared examples approach.
        """
        fewshot_records = platform_db.query(FewShotExample).filter(
            FewShotExample.tenant_db_id == tenant_db_id,
            FewShotExample.is_active == True
        ).limit(limit).all()

        examples = []
        for fs in fewshot_records:
            examples.append({
                "question": fs.question,
                "sql": fs.sql_query,
                "explanation": fs.explanation,
                "module": fs.module,
                "category": fs.category
            })

        return examples

    def _build_prompt(
        self,
        question: str,
        schema_context: List[Dict[str, Any]],
        few_shot_examples: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict]] = None,
        db_type: str = "mssql"
    ) -> str:
        """Build comprehensive prompt with tenant-specific context"""

        # Determine SQL dialect
        if db_type.lower() == "mssql":
            dialect = "SQL Server (T-SQL)"
            dialect_notes = "Use TOP instead of LIMIT, GETDATE() for current date, DATEADD for date arithmetic"
        elif db_type.lower() == "postgresql":
            dialect = "PostgreSQL"
            dialect_notes = "Use LIMIT, CURRENT_DATE, date arithmetic with INTERVAL"
        elif db_type.lower() == "mysql":
            dialect = "MySQL"
            dialect_notes = "Use LIMIT, CURDATE(), DATE_ADD for date arithmetic"
        else:
            dialect = "SQL"
            dialect_notes = ""

        prompt = f"""You are an expert SQL query generator for {dialect} databases.

Given the user's question, relevant SQL query examples, and database schema information, generate a precise SQL query.

SQL DIALECT: {dialect}
{dialect_notes}

"""

        # Add few-shot examples if available
        if few_shot_examples:
            prompt += "\nRELEVANT SQL EXAMPLES:\n"
            for i, ex in enumerate(few_shot_examples, 1):
                prompt += f"\nExample {i}:\n"
                prompt += f"Question: {ex.get('question', '')}\n"
                prompt += f"SQL: {ex.get('sql', '')}\n"
                if ex.get('explanation'):
                    prompt += f"Explanation: {ex.get('explanation', '')}\n"

        # Add schema context
        prompt += "\n\nDATABASE SCHEMA CONTEXT:\n"
        for i, schema in enumerate(schema_context[:15], 1):  # Limit to 15 tables
            prompt += f"\n{i}. {schema.get('document', '')}\n"

        # Add conversation history if available
        if conversation_history and len(conversation_history) > 0:
            prompt += "\n\nCONVERSATION HISTORY:\n"
            prompt += "Use this history to understand context from previous queries.\n\n"

            for msg in conversation_history[-5:]:  # Last 5 messages
                msg_type = msg.get("message_type", "")
                content = msg.get("message_content", "")

                if msg_type == "user":
                    prompt += f"USER: {content}\n"
                elif msg_type == "assistant":
                    prompt += f"ASSISTANT: {content[:200]}...\n\n"

        prompt += f"""

USER QUESTION:
{question}

INSTRUCTIONS:
1. Study the example queries above to understand patterns and best practices
2. Analyze the user's question carefully
3. Use ONLY the tables and columns provided in the schema context above
4. Generate a valid {dialect} query
5. Use appropriate JOINs if multiple tables are needed
6. Include TOP/LIMIT clause for large result sets
7. Use clear aliases for readability
8. Format dates appropriately for the database type
9. Ensure the query is safe and optimized

IMPORTANT RULES:
- Only return the SQL query, nothing else
- Do NOT include markdown code blocks or explanations
- VERIFY each column exists in the schema before using it
- DO NOT hallucinate or invent column names

SQL QUERY:"""

        return prompt

    def _generate_sql(self, prompt: str) -> str:
        """Call LLM API to generate SQL (supports OpenRouter and Gemini)"""
        if self.llm_provider == "gemini":
            return self._generate_sql_gemini(prompt)
        else:
            return self._generate_sql_openrouter(prompt)

    def _generate_sql_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API to generate SQL"""
        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://oryggi.ai",
                "X-Title": "OryggiAI SQL Agent",
            }

            payload = {
                "model": self.openrouter_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": settings.gemini_max_tokens,
            }

            response = requests.post(
                f"{self.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"[TENANT_AGENT] OpenRouter API error: {response.status_code} - {error_detail}")
                raise Exception(f"OpenRouter API error: {response.status_code} - {error_detail}")

            result = response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                raise Exception("OpenRouter returned empty response")

            content = result["choices"][0]["message"]["content"]

            if not content:
                raise Exception("OpenRouter returned empty content")

            logger.info(f"[TENANT_AGENT] OpenRouter response received, model: {self.openrouter_model}")
            return content.strip()

        except requests.exceptions.Timeout:
            logger.error("[TENANT_AGENT] OpenRouter API timeout")
            raise Exception("OpenRouter API request timed out")
        except Exception as e:
            logger.error(f"[TENANT_AGENT] OpenRouter API call failed: {str(e)}")
            raise

    def _generate_sql_gemini(self, prompt: str) -> str:
        """Call Gemini API to generate SQL"""
        try:
            generation_config = {
                "temperature": self.temperature,
                "max_output_tokens": settings.gemini_max_tokens,
            }

            safety_settings = {
                self.HarmCategory.HARM_CATEGORY_HARASSMENT: self.HarmBlockThreshold.BLOCK_NONE,
                self.HarmCategory.HARM_CATEGORY_HATE_SPEECH: self.HarmBlockThreshold.BLOCK_NONE,
                self.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: self.HarmBlockThreshold.BLOCK_NONE,
                self.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: self.HarmBlockThreshold.BLOCK_NONE,
            }

            response = self.gemini_model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            if not response.text:
                raise Exception("Gemini returned empty response")

            return response.text.strip()

        except Exception as e:
            logger.error(f"[TENANT_AGENT] Gemini API call failed: {str(e)}")
            raise

    def _clean_sql(self, sql_query: str) -> str:
        """Clean and validate generated SQL"""
        import re

        # Remove markdown code blocks if present
        if sql_query.startswith("```"):
            lines = sql_query.split("\n")
            sql_query = "\n".join(lines[1:-1]) if len(lines) > 2 else sql_query

        # Remove common prefixes
        sql_query = sql_query.strip()
        if sql_query.lower().startswith("sql"):
            sql_query = sql_query[3:].strip()

        # Remove trailing semicolons
        sql_query = sql_query.rstrip(";")

        # Fix malformed COUNT syntax
        malformed_count_pattern = r'\bCOUNT\s+FROM\b'
        if re.search(malformed_count_pattern, sql_query, re.IGNORECASE):
            logger.warning("[TENANT_AGENT] Detected malformed COUNT syntax, auto-correcting...")
            sql_query = re.sub(malformed_count_pattern, 'COUNT(*) FROM', sql_query, flags=re.IGNORECASE)

        return sql_query

    def _extract_tables_from_sql(self, sql_query: str) -> List[str]:
        """Extract table names from SQL query"""
        import re
        tables = []

        # Find tables after FROM
        from_matches = re.findall(r'FROM\s+(\w+)', sql_query, re.IGNORECASE)
        tables.extend(from_matches)

        # Find tables after JOIN
        join_matches = re.findall(r'JOIN\s+(\w+)', sql_query, re.IGNORECASE)
        tables.extend(join_matches)

        return list(set(tables))

    def _format_answer(
        self,
        question: str,
        results: List[Dict[str, Any]],
        max_rows: int = 10
    ) -> str:
        """Format query results into natural language answer"""
        if not results:
            return "No results found for your query."

        # Count queries
        if len(results) == 1 and len(results[0]) == 1:
            value = list(results[0].values())[0]
            return f"The answer is: {value}"

        # Multiple results
        answer = f"Found {len(results)} result(s):\n\n"

        for i, row in enumerate(results[:max_rows], 1):
            row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
            answer += f"{i}. {row_str}\n"

        if len(results) > max_rows:
            answer += f"\n... and {len(results) - max_rows} more rows"

        return answer


# Global tenant SQL agent instance
tenant_sql_agent = TenantSQLAgent()
