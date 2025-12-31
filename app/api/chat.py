"""
Chat API Endpoints
Handles user queries with RAG-enhanced SQL generation

Multi-Tenant Support:
- /query - Original endpoint (uses default database from settings)
- /mt/query - Multi-tenant endpoint (uses authenticated user's tenant database)
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from loguru import logger
import time

from app.models.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    SchemaIndexRequest,
    SchemaIndexResponse
)
from app.agents.sql_agent import sql_agent
from app.rag import index_database_schema, chroma_manager, few_shot_manager
from app.config import settings

# Phase 3: Conversation Memory
from app.memory.conversation_store import conversation_store
from app.memory.memory_retriever import memory_retriever

# Phase 4: Multi-Tool Orchestration
from app.workflows.chatbot_orchestrator import chatbot_orchestrator

# Multi-tenant support
from app.database.platform_connection import get_platform_db
from app.api.deps import CurrentUserDep

# Multi-tenant SQL agent
from app.agents.tenant_sql_agent import tenant_sql_agent

# Usage tracking
from app.services.usage_service import usage_service

# Create router
router = APIRouter()


def sync_to_chromadb(session_id: str, user_id: str):
    """
    Background task to sync conversation to ChromaDB for RAG.
    Runs asynchronously to avoid blocking the response.
    """
    try:
        # Get session history
        session_messages = conversation_store.get_session_history(
            session_id=session_id,
            user_id=user_id,
            limit=100
        )

        # Add to ChromaDB index
        if session_messages:
            doc_ids = memory_retriever.add_conversation_to_index(
                session_id=session_id,
                user_id=user_id,
                conversation_messages=session_messages
            )
            logger.info(f"[BACKGROUND] Synced {len(doc_ids)} messages to ChromaDB for session {session_id}")
    except Exception as e:
        logger.error(f"[BACKGROUND] Failed to sync to ChromaDB: {str(e)}")


@router.post("/query", response_model=ChatQueryResponse)
async def query_chatbot(request: ChatQueryRequest, background_tasks: BackgroundTasks):
    """
    Process natural language query and return answer with conversation memory

    **Phase 3 Features:**
    - Session continuity across requests
    - Conversation storage in PostgreSQL
    - Background sync to ChromaDB for RAG

    **Example Request:**
    ```json
    {
        "question": "How many employees joined in the last 30 days?",
        "tenant_id": "default",
        "user_id": "admin",
        "user_role": "ADMIN",
        "session_id": "session_admin_20250117_abc123"
    }
    ```

    **Example Response:**
    ```json
    {
        "session_id": "session_admin_20250117_abc123",
        "question": "How many employees joined in the last 30 days?",
        "sql_query": "SELECT COUNT(*) FROM EmployeeMaster WHERE ...",
        "answer": "5 employees joined in the last 30 days.",
        "result_count": 1,
        "tables_used": ["EmployeeMaster"],
        "execution_time": 0.523,
        "success": true
    }
    ```
    """
    start_time = time.time()

    # Phase 3: Generate or reuse session ID
    session_id = request.session_id or conversation_store.generate_session_id(request.user_id)

    logger.info(f"[{request.tenant_id}:{request.user_id}:{session_id}] Query: {request.question}")

    # Phase 3: Store user question
    try:
        user_msg_id = conversation_store.store_message(
            session_id=session_id,
            user_id=request.user_id,
            user_role=request.user_role,
            message_type="user",
            message_content=request.question
        )
        logger.debug(f"[MEMORY] Stored user message (ID: {user_msg_id})")
    except Exception as e:
        logger.warning(f"[MEMORY] Failed to store user message: {str(e)}")

    try:
        # Phase 4: Process query using LangGraph multi-tool orchestrator
        logger.info("=" * 80)
        logger.info(f"[CHAT_API] Calling chatbot_orchestrator.process()")
        logger.info(f"[CHAT_API]   question: {request.question}")
        logger.info(f"[CHAT_API]   user_id: {request.user_id}")
        logger.info(f"[CHAT_API]   user_role: {request.user_role}")
        logger.info(f"[CHAT_API]   session_id: {session_id}")
        logger.info("=" * 80)

        result = await chatbot_orchestrator.process(
            question=request.question,
            user_id=request.user_id,
            user_role=request.user_role,
            session_id=session_id
        )

        logger.info("=" * 80)
        logger.info(f"[CHAT_API] chatbot_orchestrator.process() returned")
        logger.info(f"[CHAT_API]   success: {result.get('success')}")
        logger.info(f"[CHAT_API]   error: {result.get('error')}")
        logger.info(f"[CHAT_API]   tools_called: {result.get('tools_called')}")
        logger.info(f"[CHAT_API]   intent: {result.get('intent')}")
        logger.info(f"[CHAT_API]   answer length: {len(result.get('answer', ''))} chars")
        logger.info("=" * 80)

        execution_time = time.time() - start_time

        # Extract query result from orchestrator response (with null checking)
        query_result = result.get("query_result") or {}
        tools_used = result.get("tools_called") or ["query_database"]

        # Check if clarification is needed
        if result.get("needs_clarification"):
            logger.info(f"[CHAT_API] Clarification needed for: {request.question}")

            # Store clarification request in conversation history
            try:
                conversation_store.store_message(
                    session_id=session_id,
                    user_id=request.user_id,
                    user_role=request.user_role,
                    message_type="assistant",
                    message_content=result.get("answer", "Could you please clarify?"),
                    tools_used=["clarity_assessment"],
                    data_returned=result,
                    success_flag=True
                )
            except Exception as e:
                logger.warning(f"[MEMORY] Failed to store clarification request: {str(e)}")

            return ChatQueryResponse(
                session_id=session_id,
                question=request.question,
                sql_query=None,
                answer=result.get("answer", "Could you please clarify your request?"),
                result_count=0,
                tables_used=[],
                execution_time=execution_time,
                success=True,
                error=None,
                # Clarification fields
                needs_clarification=True,
                clarification_question=result.get("clarification_question"),
                clarification_options=result.get("clarification_options"),
                clarification_attempt=result.get("clarification_attempt", 1),
                max_clarification_attempts=result.get("max_clarification_attempts", 3),
                original_unclear_question=result.get("original_question")
            )

        # Check if workflow succeeded
        if not result.get("success"):
            # Phase 3: Store error response
            try:
                conversation_store.store_message(
                    session_id=session_id,
                    user_id=request.user_id,
                    user_role=request.user_role,
                    message_type="assistant",
                    message_content=result.get("answer", "Error processing request"),
                    tools_used=tools_used,
                    data_returned=result,
                    success_flag=False
                )
            except Exception as e:
                logger.warning(f"[MEMORY] Failed to store error response: {str(e)}")

            return ChatQueryResponse(
                session_id=session_id,
                question=request.question,
                sql_query=query_result.get("result", {}).get("sql_query") if query_result.get("success") else None,
                answer=result.get("answer", "Error processing request"),
                result_count=0,
                tables_used=[],
                execution_time=execution_time,
                success=False,
                error=result.get("error")
            )

        # Phase 3: Store successful response with context for follow-up queries
        try:
            # Build enriched message content with SQL and result identifiers for context
            answer_text = result.get("answer", "")
            enriched_content = answer_text

            # Extract SQL query and result identifiers from query_result
            if query_result and query_result.get("success"):
                tool_result = query_result.get("result", {})
                stored_sql = tool_result.get("sql_query", "")
                stored_results = tool_result.get("results", [])

                # Build context metadata for follow-up queries
                context_parts = []

                # Add SQL query (normalize to single line for reliable parsing)
                if stored_sql:
                    # Convert multi-line SQL to single line by normalizing whitespace
                    single_line_sql = ' '.join(stored_sql.split())
                    context_parts.append(f"[SQL_QUERY]: {single_line_sql}")

                # Extract key identifiers (ECodes, IDs) from results for follow-up filtering
                if stored_results and isinstance(stored_results, list) and len(stored_results) > 0:
                    # Look for common identifier columns
                    id_columns = ['Ecode', 'ECode', 'ecode', 'ID', 'Id', 'id', 'EmployeeId', 'StudentId']
                    found_ids = []

                    for row in stored_results:
                        if isinstance(row, dict):
                            for col in id_columns:
                                if col in row and row[col] is not None:
                                    found_ids.append(str(row[col]))
                                    break  # Take first matching ID column per row

                    if found_ids:
                        # Limit to first 50 IDs to avoid very long strings
                        ids_str = ",".join(found_ids[:50])
                        context_parts.append(f"[RESULT_IDS]: {ids_str}")
                        context_parts.append(f"[RESULT_COUNT]: {len(stored_results)}")

                # Append context to the message content
                if context_parts:
                    enriched_content = f"{answer_text}\n\n---CONTEXT_FOR_FOLLOWUP---\n" + "\n".join(context_parts)

            conversation_store.store_message(
                session_id=session_id,
                user_id=request.user_id,
                user_role=request.user_role,
                message_type="assistant",
                message_content=enriched_content,
                tools_used=tools_used,
                data_returned=result,
                success_flag=True
            )
            logger.debug(f"[MEMORY] Stored assistant response with context")

            # Phase 3: Schedule background sync to ChromaDB
            background_tasks.add_task(sync_to_chromadb, session_id, request.user_id)
        except Exception as e:
            logger.warning(f"[MEMORY] Failed to store assistant response: {str(e)}")

        # Successful response
        # Extract SQL query and result count from query_result if available
        sql_query = None
        result_count = 0
        tables_used_list = []
        results_data = None

        if query_result and query_result.get("success"):
            # ChatbotTool wraps results: {"success": bool, "result": {actual_data}}
            tool_result = query_result.get("result", {})
            sql_query = tool_result.get("sql_query")
            result_count = tool_result.get("result_count", 0)
            tables_used_list = tool_result.get("tables_used", [])
            # Extract the actual query results for frontend table rendering
            results_data = tool_result.get("results", None)
            # Frontend now supports pagination, so we can pass all results

        return ChatQueryResponse(
            session_id=session_id,
            question=request.question,
            sql_query=sql_query,
            answer=result.get("answer", ""),
            result_count=result_count,
            tables_used=tables_used_list,
            execution_time=execution_time,
            success=True,
            results=results_data
        )

    except Exception as e:
        logger.error(f"[ERROR] Query processing failed: {str(e)}", exc_info=True)
        execution_time = time.time() - start_time

        # Phase 3: Store exception in conversation history
        try:
            conversation_store.store_message(
                session_id=session_id,
                user_id=request.user_id,
                user_role=request.user_role,
                message_type="assistant",
                message_content=f"I encountered an error processing your question: {str(e)}",
                tools_used=["sql_tool"],
                data_returned={"error": str(e), "exception_type": type(e).__name__},
                success_flag=False
            )
        except Exception as mem_error:
            logger.warning(f"[MEMORY] Failed to store exception: {str(mem_error)}")

        return ChatQueryResponse(
            session_id=session_id,
            question=request.question,
            sql_query=None,
            answer=f"I encountered an error processing your question: {str(e)}",
            result_count=0,
            tables_used=[],
            execution_time=execution_time,
            success=False,
            error=str(e)
        )


@router.post("/index-schema", response_model=SchemaIndexResponse)
async def index_schema(request: SchemaIndexRequest):
    """
    Index database schema into vector store

    This endpoint extracts database schema (tables, columns, relationships)
    and creates embeddings for RAG-based query generation.

    **When to use:**
    - After database schema changes
    - Initial setup
    - When query accuracy drops

    **Example Request:**
    ```json
    {
        "force_reindex": true
    }
    ```

    **Example Response:**
    ```json
    {
        "success": true,
        "embeddings_count": 1250,
        "tables_count": 35,
        "message": "Schema indexed successfully"
    }
    ```
    """
    logger.info(f"Schema indexing requested (force_reindex={request.force_reindex})")

    try:
        # Force reindex if requested
        if request.force_reindex:
            chroma_manager.delete_all()

        # Index schema
        if settings.embedding_provider == "google":
            from reindex_schemas_google import reindex_schemas_google
            result = reindex_schemas_google()
            embeddings_count = result["total_embeddings"] if result else 0
        else:
            embeddings_count = index_database_schema()

        # Get stats
        stats = chroma_manager.get_collection_stats()

        return SchemaIndexResponse(
            success=True,
            embeddings_count=stats["count"],
            tables_count=len([
                meta for meta in stats.get("sample_documents", [])
                if "table" in str(meta).lower()
            ]),
            message="Schema indexed successfully"
        )

    except Exception as e:
        logger.error(f"[ERROR] Schema indexing failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Schema indexing failed: {str(e)}"
        )


@router.get("/schema-stats")
async def get_schema_stats():
    """
    Get vector store statistics

    Returns information about indexed schema:
    - Number of embeddings
    - Sample documents
    - Collection status

    **Example Response:**
    ```json
    {
        "count": 1250,
        "sample_ids": ["schema_EmployeeMaster", "column_EmployeeMaster_Ecode", ...],
        "status": "healthy"
    }
    ```
    """
    try:
        stats = chroma_manager.get_collection_stats()

        return {
            "count": stats["count"],
            "sample_ids": stats["sample_ids"][:10],
            "sample_documents": stats["sample_documents"][:3],
            "status": "healthy" if stats["count"] > 0 else "empty"
        }

    except Exception as e:
        logger.error(f"[ERROR] Failed to get schema stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get schema stats: {str(e)}"
        )


# =============================================================================
# MULTI-TENANT CHAT ENDPOINTS
# =============================================================================

class MultiTenantChatRequest:
    """Request model for multi-tenant chat (Pydantic model inline)"""
    pass


from pydantic import BaseModel, Field


class MTChatRequest(BaseModel):
    """Multi-tenant chat request with clarification support"""
    question: str = Field(..., description="User's natural language question")
    database_id: Optional[str] = Field(None, description="Specific database ID (uses default if not provided)")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    # Clarification fields
    clarification_response: Optional[str] = Field(None, description="User's response to a clarification question")
    original_unclear_question: Optional[str] = Field(None, description="The original question that needed clarification")
    clarification_attempt: int = Field(0, description="Current clarification attempt number")


@router.post("/mt/query", response_model=ChatQueryResponse)
async def multi_tenant_query(
    request: MTChatRequest,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_platform_db)
):
    """
    Multi-tenant chat endpoint - uses authenticated user's tenant database

    This endpoint requires JWT authentication and will use the tenant's
    configured database for queries.

    **Flow:**
    1. Authenticate user via JWT token
    2. Get user's tenant and default database
    3. Process query against tenant's database
    4. Return results with tenant isolation

    **Example Request:**
    ```json
    {
        "question": "How many employees joined in the last 30 days?",
        "database_id": null,  // Uses default database
        "session_id": null    // Auto-generated if not provided
    }
    ```

    **Headers Required:**
    - Authorization: Bearer <jwt_token>
    """
    start_time = time.time()

    # Get tenant's database
    from app.services.tenant_service import list_database_connections, get_database_connection
    import uuid as uuid_module

    tenant_id = current_user.tenant_id
    user_id = str(current_user.user_id)
    user_role = current_user.role.upper()

    # Determine which database to use
    if request.database_id:
        try:
            db_id = uuid_module.UUID(request.database_id)
            tenant_db = get_database_connection(db, db_id, tenant_id)
        except (ValueError, Exception) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid database ID: {str(e)}"
            )
    else:
        # Get default/active database for tenant
        databases = list_database_connections(db, tenant_id, include_inactive=False)
        if not databases:
            raise HTTPException(
                status_code=400,
                detail="No database configured for this tenant. Please add a database first."
            )
        # Use the first ready database (or first active one)
        tenant_db = next((d for d in databases if d.is_ready), databases[0])

    if not tenant_db:
        raise HTTPException(
            status_code=404,
            detail="Database not found"
        )

    # Check if database is onboarded
    if not tenant_db.schema_analyzed:
        raise HTTPException(
            status_code=400,
            detail=f"Database '{tenant_db.name}' has not been onboarded yet. "
                   f"Please run onboarding first via POST /api/tenant/databases/{tenant_db.id}/onboard"
        )

    # Check query limits
    limit_check = usage_service.check_query_limit(db, tenant_id)
    if not limit_check.get("allowed", True):
        raise HTTPException(
            status_code=429,
            detail=f"Daily query limit reached ({limit_check.get('limit', 0)} queries). "
                   f"Upgrade your plan for more queries."
        )

    # Generate session ID
    session_id = request.session_id or conversation_store.generate_session_id(user_id)

    logger.info(f"[MT:{str(tenant_id)[:8]}:{user_id[:8]}:{session_id[:12]}] Query: {request.question}")
    logger.info(f"[MT] Using database: {tenant_db.name} ({tenant_db.database_name})")

    # Store user question
    try:
        conversation_store.store_message(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            message_type="user",
            message_content=request.question
        )
    except Exception as e:
        logger.warning(f"[MEMORY] Failed to store user message: {str(e)}")

    try:
        # Fetch conversation history from conversation_store
        # This is critical for clarification flow - allows detecting user responses
        conversation_history = None
        try:
            history_result = conversation_store.get_session_history(session_id, user_id)
            if history_result and history_result.get("messages"):
                conversation_history = history_result.get("messages", [])
                logger.debug(f"[MT] Loaded {len(conversation_history)} messages for context")
        except Exception as hist_err:
            logger.warning(f"[MT] Failed to load conversation history: {hist_err}")

        # Process using the tenant-specific SQL agent
        # This uses the tenant's schema and few-shot examples from platform DB
        # and executes queries on the tenant's own database
        result = await tenant_sql_agent.process_query(
            question=request.question,
            tenant_database=tenant_db,
            platform_db=db,
            user_id=user_id,
            user_role=user_role,
            conversation_history=conversation_history,
            # Clarification parameters
            clarification_response=request.clarification_response,
            original_unclear_question=request.original_unclear_question,
            clarification_attempt=request.clarification_attempt
        )

        execution_time = time.time() - start_time
        response_time_ms = int(execution_time * 1000)

        # Check if clarification is needed (Light Mode)
        if result.get("needs_clarification"):
            logger.info(f"[MT] Light clarification needed for: {request.question}")

            # Store clarification request in conversation history
            try:
                conversation_store.store_message(
                    session_id=session_id,
                    user_id=user_id,
                    user_role=user_role,
                    message_type="assistant",
                    message_content=result.get("clarification_question", "Could you please clarify?"),
                    tools_used=["clarity_assessment"],
                    data_returned=result,
                    success_flag=True
                )
            except Exception as e:
                logger.warning(f"[MEMORY] Failed to store clarification request: {str(e)}")

            return ChatQueryResponse(
                session_id=session_id,
                question=request.question,
                sql_query=None,
                answer=result.get("natural_answer", "Could you please clarify your request?"),
                result_count=0,
                tables_used=[],
                execution_time=execution_time,
                success=True,
                error=None,
                # Clarification fields
                needs_clarification=True,
                clarification_question=result.get("clarification_question"),
                clarification_options=result.get("clarification_options"),
                clarification_attempt=result.get("clarification_attempt", 1),
                max_clarification_attempts=result.get("max_clarification_attempts", 3),
                original_unclear_question=result.get("original_question")
            )

        # Track usage metrics
        try:
            usage_service.track_query(
                db=db,
                tenant_id=tenant_id,
                success=result.get("success", False),
                tokens=0,  # TODO: Get actual token count from LLM
                response_time_ms=response_time_ms,
                is_sql_query=True,
                user_id=uuid_module.UUID(user_id),
                sql_query=result.get("sql_query"),
                rows_affected=result.get("result_count", 0)
            )
        except Exception as e:
            logger.warning(f"[USAGE] Failed to track query: {str(e)}")

        # Store response
        try:
            conversation_store.store_message(
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                message_type="assistant",
                message_content=result.get("natural_answer", ""),
                tools_used=["tenant_query_database"],
                data_returned=result,
                success_flag=result.get("success", False)
            )
            background_tasks.add_task(sync_to_chromadb, session_id, user_id)
        except Exception as e:
            logger.warning(f"[MEMORY] Failed to store response: {str(e)}")

        if not result.get("success"):
            return ChatQueryResponse(
                session_id=session_id,
                question=request.question,
                sql_query=result.get("sql_query"),
                answer=result.get("natural_answer", "Error processing request"),
                result_count=0,
                tables_used=[],
                execution_time=execution_time,
                success=False,
                error=result.get("error")
            )

        # Extract query details from tenant SQL agent result
        sql_query = result.get("sql_query")
        result_count = result.get("result_count", 0)
        tables_used_list = result.get("tables_used", [])
        results_data = result.get("results")
        # Frontend now supports pagination, so we can pass all results

        return ChatQueryResponse(
            session_id=session_id,
            question=request.question,
            sql_query=sql_query,
            answer=result.get("natural_answer", ""),
            result_count=result_count,
            tables_used=tables_used_list,
            execution_time=execution_time,
            success=True,
            results=results_data
        )

    except Exception as e:
        logger.error(f"[MT] Query processing failed: {str(e)}", exc_info=True)
        execution_time = time.time() - start_time

        return ChatQueryResponse(
            session_id=session_id,
            question=request.question,
            sql_query=None,
            answer=f"I encountered an error processing your question: {str(e)}",
            result_count=0,
            tables_used=[],
            execution_time=execution_time,
            success=False,
            error=str(e)
        )


@router.get("/mt/databases")
async def get_available_databases(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Get available databases for multi-tenant chat

    Returns list of databases the authenticated user can query.
    """
    from app.services.tenant_service import list_database_connections

    databases = list_database_connections(db, current_user.tenant_id, include_inactive=False)

    return {
        "tenant_id": str(current_user.tenant_id),
        "databases": [
            {
                "id": str(d.id),
                "name": d.name,
                "database_name": d.database_name,
                "db_type": d.db_type,
                "schema_analyzed": d.schema_analyzed,
                "analysis_status": d.analysis_status,
                "table_count": d.table_count or 0,
                "view_count": d.view_count or 0,
                "ready_to_chat": d.is_ready  # Uses is_ready property: is_active AND schema_analyzed AND analysis_status == COMPLETED
            }
            for d in databases
        ]
    }


@router.post(
    "/reload-fewshot",
    summary="Reload few-shot examples",
    description="Reload few-shot examples from JSON file and rebuild FAISS index"
)
async def reload_fewshot_examples():
    """
    Reload few-shot examples from disk and rebuild the FAISS index.
    Use this after updating few_shot_examples.json to apply changes without server restart.
    """
    try:
        logger.info("Reloading few-shot examples...")
        few_shot_manager.reload_examples()
        stats = few_shot_manager.get_stats()
        logger.info(f"[OK] Reloaded {stats['total_examples']} few-shot examples")
        return {
            "success": True,
            "message": f"Reloaded {stats['total_examples']} few-shot examples",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"[ERROR] Failed to reload few-shot examples: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
