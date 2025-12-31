"""
Conversation Manager - Phase 3
High-level orchestration for conversation memory system
Features: Session lifecycle, message storage, RAG integration, context management
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from app.memory.conversation_store import ConversationStore

# Try to import MemoryRetriever (requires ChromaDB)
try:
    from app.memory.memory_retriever import MemoryRetriever
    MEMORY_RETRIEVER_AVAILABLE = True
except (ImportError, RuntimeError):
    MemoryRetriever = None
    MEMORY_RETRIEVER_AVAILABLE = False


class ConversationManager:
    """
    High-level manager for conversation memory system.

    Orchestrates the entire conversation lifecycle:
    - Session creation and management
    - Message storage and retrieval
    - RAG-enhanced context retrieval
    - Conversation summarization
    - RBAC enforcement throughout

    This is the primary interface for the FastAPI layer.
    """

    def __init__(
        self,
        conversation_store: Optional[ConversationStore] = None,
        memory_retriever: Optional["MemoryRetriever"] = None,
        enable_rag: bool = True,
        auto_sync_embeddings: bool = False
    ):
        """
        Initialize ConversationManager.

        Args:
            conversation_store: ConversationStore instance
            memory_retriever: MemoryRetriever instance (optional, requires ChromaDB)
            enable_rag: Enable RAG-enhanced context retrieval (only if MemoryRetriever available)
            auto_sync_embeddings: Automatically sync messages to vector database

        Note:
            If ChromaDB is not installed, RAG features will be disabled automatically.
        """
        # Initialize components
        if conversation_store:
            self.conversation_store = conversation_store
        else:
            self.conversation_store = ConversationStore()

        # Initialize MemoryRetriever if available
        if memory_retriever:
            self.memory_retriever = memory_retriever
        elif MEMORY_RETRIEVER_AVAILABLE and MemoryRetriever is not None:
            try:
                self.memory_retriever = MemoryRetriever(
                    conversation_store=self.conversation_store
                )
            except Exception:
                # If initialization fails, disable RAG
                self.memory_retriever = None
                enable_rag = False
        else:
            # MemoryRetriever not available (ChromaDB not installed)
            self.memory_retriever = None
            enable_rag = False

        self.enable_rag = enable_rag and (self.memory_retriever is not None)
        self.auto_sync_embeddings = auto_sync_embeddings and self.enable_rag

    def start_session(self, user_id: str) -> str:
        """
        Start a new conversation session.

        Args:
            user_id: User identifier

        Returns:
            New session ID
        """
        session_id = self.conversation_store.generate_session_id(user_id)
        return session_id

    def add_message(
        self,
        session_id: str,
        user_id: str,
        user_role: str,
        message_type: str,
        message_content: str,
        tools_used: Optional[List[str]] = None,
        data_returned: Optional[Dict] = None,
        success_flag: bool = True
    ) -> Dict[str, Any]:
        """
        Add a message to the conversation.

        Stores message in database and optionally syncs to vector database for RAG.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)
            user_role: User role (ADMIN, HR_MANAGER, etc.)
            message_type: 'user' or 'assistant'
            message_content: Message text
            tools_used: List of tools used (for assistant messages)
            data_returned: Tool execution results
            success_flag: Whether message/tool execution was successful

        Returns:
            Dict with conversation_id and sync status
        """
        # Store message
        conversation_id = self.conversation_store.store_message(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            message_type=message_type,
            message_content=message_content,
            tools_used=tools_used,
            data_returned=data_returned,
            success_flag=success_flag
        )

        result = {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "message_type": message_type,
            "synced_to_rag": False
        }

        # Auto-sync to vector database if enabled
        if self.auto_sync_embeddings and self.enable_rag:
            try:
                # Get the message we just stored
                messages = self.conversation_store.get_session_history(
                    session_id=session_id,
                    user_id=user_id,
                    limit=1
                )

                if messages:
                    # Sync to vector database
                    doc_ids = self.memory_retriever.add_conversation_to_index(
                        session_id=session_id,
                        user_id=user_id,
                        conversation_messages=messages
                    )
                    result["synced_to_rag"] = True
                    result["rag_doc_ids"] = doc_ids

            except Exception as e:
                # Log but don't fail - RAG sync is not critical
                result["sync_error"] = str(e)

        return result

    def get_conversation_history(
        self,
        session_id: str,
        user_id: str,
        limit: int = 50,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        RBAC Enforcement: Only returns messages for the specified user.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)
            limit: Maximum number of messages
            include_inactive: Include soft-deleted messages

        Returns:
            List of conversation messages
        """
        return self.conversation_store.get_session_history(
            session_id=session_id,
            user_id=user_id,
            limit=limit,
            include_inactive=include_inactive
        )

    def get_context_with_rag(
        self,
        query: str,
        user_id: str,
        current_session_id: Optional[str] = None,
        n_results: int = 3,
        include_current_session: bool = True
    ) -> Dict[str, Any]:
        """
        Get conversation context enhanced with RAG.

        Combines current session history with semantically similar
        past conversations using vector search.

        RBAC Enforcement: Only searches user's own conversations.

        Args:
            query: Current user query
            user_id: User identifier (RBAC)
            current_session_id: Current session ID
            n_results: Number of RAG results to retrieve
            include_current_session: Include current session in RAG search

        Returns:
            Dict with current_session_history and rag_context
        """
        result = {
            "query": query,
            "user_id": user_id,
            "current_session_history": [],
            "rag_context": "",
            "rag_enabled": self.enable_rag
        }

        # Get current session history if provided
        if current_session_id:
            result["current_session_history"] = self.conversation_store.get_session_history(
                session_id=current_session_id,
                user_id=user_id,
                limit=20
            )

        # Get RAG context if enabled
        if self.enable_rag:
            try:
                # Determine if we should filter by session
                session_filter = None
                if current_session_id and not include_current_session:
                    # We want to exclude current session from RAG
                    # ChromaDB doesn't support NOT filters, so we'll get all results
                    # and filter in application code
                    pass

                # Get relevant context
                rag_context = self.memory_retriever.get_relevant_context(
                    query=query,
                    user_id=user_id,
                    n_results=n_results,
                    session_id=session_filter
                )

                result["rag_context"] = rag_context

            except Exception as e:
                result["rag_error"] = str(e)
                result["rag_context"] = "Error retrieving RAG context."

        return result

    def summarize_session(
        self,
        session_id: str,
        user_id: str,
        max_length: int = 500
    ) -> str:
        """
        Generate a summary of a conversation session.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)
            max_length: Maximum summary length in characters

        Returns:
            Summary text
        """
        # Get session history
        messages = self.conversation_store.get_session_history(
            session_id=session_id,
            user_id=user_id,
            limit=100
        )

        if not messages:
            return "No messages in this session."

        # Basic summarization (could be enhanced with LLM)
        user_messages = [m for m in messages if m['message_type'] == 'user']
        assistant_messages = [m for m in messages if m['message_type'] == 'assistant']

        # Extract tools used
        tools_used = set()
        for msg in assistant_messages:
            if msg.get('tools_used'):
                tools_used.update(msg['tools_used'])

        # Build summary
        summary_parts = []

        summary_parts.append(f"Session: {session_id}")
        summary_parts.append(f"Messages: {len(messages)} total ({len(user_messages)} user, {len(assistant_messages)} assistant)")

        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(sorted(tools_used))}")

        # Add first and last user queries
        if user_messages:
            first_query = user_messages[0]['message_content'][:100]
            summary_parts.append(f"First query: {first_query}...")

            if len(user_messages) > 1:
                last_query = user_messages[-1]['message_content'][:100]
                summary_parts.append(f"Last query: {last_query}...")

        summary = "\n".join(summary_parts)

        # Truncate if needed
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return summary

    def get_user_sessions(
        self,
        user_id: str,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.

        RBAC Enforcement: Only returns user's own sessions.

        Args:
            user_id: User identifier
            days_back: Look back N days

        Returns:
            List of session metadata with summaries
        """
        sessions = self.conversation_store.get_active_sessions(
            user_id=user_id,
            days_back=days_back
        )

        # Enhance with summaries
        for session in sessions:
            try:
                session["summary"] = self.summarize_session(
                    session_id=session["session_id"],
                    user_id=user_id,
                    max_length=200
                )
            except Exception as e:
                session["summary"] = f"Error generating summary: {str(e)}"

        return sessions

    def delete_session(
        self,
        session_id: str,
        user_id: str,
        hard_delete: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a conversation session.

        RBAC Enforcement: Only deletes user's own sessions.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            Dict with deletion results
        """
        # Delete from conversation store
        messages_deleted = self.conversation_store.delete_session(
            session_id=session_id,
            user_id=user_id,
            hard_delete=hard_delete
        )

        result = {
            "session_id": session_id,
            "messages_deleted": messages_deleted,
            "hard_delete": hard_delete,
            "embeddings_deleted": 0
        }

        # Delete from vector database if enabled
        if self.enable_rag:
            try:
                embeddings_deleted = self.memory_retriever.delete_user_embeddings(
                    user_id=user_id,
                    session_id=session_id
                )
                result["embeddings_deleted"] = embeddings_deleted
            except Exception as e:
                result["embedding_deletion_error"] = str(e)

        return result

    def sync_session_to_rag(
        self,
        session_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Manually sync a session to the RAG vector database.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)

        Returns:
            Dict with sync results
        """
        if not self.enable_rag:
            return {
                "success": False,
                "error": "RAG is not enabled"
            }

        try:
            doc_ids = self.memory_retriever.sync_session_to_index(
                session_id=session_id,
                user_id=user_id
            )

            return {
                "success": True,
                "session_id": session_id,
                "embeddings_created": len(doc_ids),
                "doc_ids": doc_ids
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def sync_all_user_sessions(
        self,
        user_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Sync all user sessions to the RAG vector database.

        Args:
            user_id: User identifier
            days_back: Sync sessions from last N days

        Returns:
            Dict with sync statistics
        """
        if not self.enable_rag:
            return {
                "success": False,
                "error": "RAG is not enabled"
            }

        try:
            sync_stats = self.memory_retriever.sync_all_user_sessions(
                user_id=user_id,
                days_back=days_back
            )

            return {
                "success": True,
                **sync_stats
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_statistics(
        self,
        user_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get conversation and RAG statistics.

        Args:
            user_id: If provided, user-specific stats. If None, global stats.
            days_back: Time window for statistics

        Returns:
            Dict with comprehensive statistics
        """
        # Get conversation stats from store
        conv_stats = self.conversation_store.get_conversation_stats(
            user_id=user_id,
            days_back=days_back
        )

        # Get RAG stats if enabled
        if self.enable_rag:
            try:
                rag_stats = self.memory_retriever.get_embedding_stats(
                    user_id=user_id
                )
                conv_stats["rag_stats"] = rag_stats
            except Exception as e:
                conv_stats["rag_error"] = str(e)

        conv_stats["rag_enabled"] = self.enable_rag
        conv_stats["auto_sync_enabled"] = self.auto_sync_embeddings

        return conv_stats


# Global instance
conversation_manager = ConversationManager(
    enable_rag=True,
    auto_sync_embeddings=False  # Disabled by default for performance
)
