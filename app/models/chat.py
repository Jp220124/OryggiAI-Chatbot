"""
Pydantic Models for Chat API
Request and response models
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    """
    Request model for chat query endpoint
    """
    question: str = Field(..., description="User's natural language question", min_length=1)
    tenant_id: str = Field(default="default", description="Tenant identifier")
    user_id: str = Field(default="system", description="User identifier")
    user_role: str = Field(default="VIEWER", description="User role for RBAC (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity (auto-generated if not provided)")


class ChatQueryResponse(BaseModel):
    """
    Response model for chat query endpoint

    Includes clarification fields for handling unclear/ambiguous prompts.
    When needs_clarification=True, the frontend should display the
    clarification_question and options instead of processing the query.
    """
    session_id: str = Field(..., description="Session ID for conversation continuity")
    question: str = Field(..., description="Original question")
    sql_query: Optional[str] = Field(None, description="Generated SQL query")
    answer: str = Field(..., description="Natural language answer")
    result_count: int = Field(default=0, description="Number of results returned")
    tables_used: List[str] = Field(default_factory=list, description="Database tables referenced")
    execution_time: float = Field(..., description="Query execution time in seconds")
    success: bool = Field(..., description="Whether query succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="Structured query results for table display")

    # Clarification fields - for handling unclear prompts
    needs_clarification: bool = Field(default=False, description="Whether the query needs clarification")
    clarification_question: Optional[str] = Field(None, description="Clarifying question to ask user")
    clarification_options: Optional[List[str]] = Field(None, description="Selectable options for clarification")
    clarification_attempt: Optional[int] = Field(None, description="Current clarification attempt (1-3)")
    max_clarification_attempts: Optional[int] = Field(default=3, description="Maximum clarification attempts")
    original_unclear_question: Optional[str] = Field(None, description="Original question that was unclear")


class SchemaIndexRequest(BaseModel):
    """
    Request model for schema indexing endpoint
    """
    force_reindex: bool = Field(default=False, description="Force full re-indexing")


class SchemaIndexResponse(BaseModel):
    """
    Response model for schema indexing
    """
    success: bool = Field(..., description="Whether indexing succeeded")
    embeddings_count: int = Field(..., description="Number of embeddings created")
    tables_count: int = Field(..., description="Number of tables indexed")
    message: str = Field(..., description="Status message")
