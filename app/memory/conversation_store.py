"""
Conversation Store - Phase 3
Manages conversation history storage in PostgreSQL (Docker)
Features: RBAC enforcement, session management, soft deletion
Fallback: In-memory storage when PostgreSQL is not available
"""

import json
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

# Try to import psycopg2, but don't fail if not available
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    # Create mock psycopg2 for type hints when not available
    class _MockPsycopg2:
        Error = Exception
        def connect(self, *args, **kwargs):
            raise ImportError("psycopg2 not available")
    psycopg2 = _MockPsycopg2()
    logger.warning("psycopg2 not available, will use in-memory conversation storage")


class InMemoryConversationStore:
    """
    In-memory fallback for conversation storage when PostgreSQL is not available.
    WARNING: Data is lost on restart. Use only for development/testing.
    """

    def __init__(self):
        self._messages: List[Dict[str, Any]] = []
        self._counter = 0
        logger.warning("Using in-memory conversation store - data will be lost on restart!")

    def generate_session_id(self, user_id: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        short_uuid = str(uuid.uuid4())[:8]
        return f"session_{user_id}_{timestamp}_{short_uuid}"

    def store_message(
        self,
        session_id: str,
        user_id: str,
        user_role: str,
        message_type: str,
        message_content: str,
        tools_used: Optional[List[str]] = None,
        data_returned: Optional[Dict] = None,
        success_flag: bool = True
    ) -> int:
        if message_type not in ['user', 'assistant']:
            raise ValueError(f"Invalid message_type: {message_type}")

        self._counter += 1
        message = {
            "conversation_id": self._counter,
            "session_id": session_id,
            "user_id": user_id,
            "user_role": user_role,
            "message_type": message_type,
            "message_content": message_content,
            "tools_used": tools_used,
            "success_flag": success_flag,
            "error_message": json.dumps(data_returned) if data_returned and not success_flag else None,
            "timestamp": datetime.utcnow(),
            "is_active": True
        }
        self._messages.append(message)
        return self._counter

    def get_session_history(
        self,
        session_id: str,
        user_id: str,
        limit: int = 50,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        result = []
        for msg in self._messages:
            if msg["session_id"] == session_id and msg["user_id"] == user_id:
                if msg["is_active"] or include_inactive:
                    result.append({
                        **msg,
                        "timestamp": msg["timestamp"].isoformat() if msg["timestamp"] else None
                    })
        return sorted(result, key=lambda x: x["timestamp"] or "")[:limit]

    def get_user_history(
        self,
        user_id: str,
        limit: int = 100,
        days_back: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        cutoff = None
        if days_back:
            cutoff = datetime.utcnow() - timedelta(days=days_back)

        result = []
        for msg in self._messages:
            if msg["user_id"] == user_id and msg["is_active"]:
                if cutoff is None or (msg["timestamp"] and msg["timestamp"] >= cutoff):
                    result.append({
                        **msg,
                        "timestamp": msg["timestamp"].isoformat() if msg["timestamp"] else None
                    })
        return sorted(result, key=lambda x: x["timestamp"] or "", reverse=True)[:limit]

    def get_active_sessions(
        self,
        user_id: str,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        sessions = {}

        for msg in self._messages:
            if msg["user_id"] == user_id and msg["is_active"]:
                if msg["timestamp"] and msg["timestamp"] >= cutoff:
                    sid = msg["session_id"]
                    if sid not in sessions:
                        sessions[sid] = {
                            "session_id": sid,
                            "session_start": msg["timestamp"],
                            "session_end": msg["timestamp"],
                            "message_count": 0,
                            "user_messages": 0,
                            "assistant_messages": 0
                        }
                    sessions[sid]["message_count"] += 1
                    if msg["timestamp"] < sessions[sid]["session_start"]:
                        sessions[sid]["session_start"] = msg["timestamp"]
                    if msg["timestamp"] > sessions[sid]["session_end"]:
                        sessions[sid]["session_end"] = msg["timestamp"]
                    if msg["message_type"] == "user":
                        sessions[sid]["user_messages"] += 1
                    else:
                        sessions[sid]["assistant_messages"] += 1

        result = []
        for s in sessions.values():
            result.append({
                **s,
                "session_start": s["session_start"].isoformat() if s["session_start"] else None,
                "session_end": s["session_end"].isoformat() if s["session_end"] else None
            })
        return sorted(result, key=lambda x: x["session_start"] or "", reverse=True)

    def delete_session(
        self,
        session_id: str,
        user_id: str,
        hard_delete: bool = False
    ) -> int:
        count = 0
        if hard_delete:
            new_messages = []
            for msg in self._messages:
                if msg["session_id"] == session_id and msg["user_id"] == user_id:
                    count += 1
                else:
                    new_messages.append(msg)
            self._messages = new_messages
        else:
            for msg in self._messages:
                if msg["session_id"] == session_id and msg["user_id"] == user_id and msg["is_active"]:
                    msg["is_active"] = False
                    count += 1
        return count

    def get_conversation_stats(
        self,
        user_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        filtered = []
        for msg in self._messages:
            if msg["is_active"] and msg["timestamp"] and msg["timestamp"] >= cutoff:
                if user_id is None or msg["user_id"] == user_id:
                    filtered.append(msg)

        if not filtered:
            return {
                "total_messages": 0,
                "total_sessions": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "successful_messages": 0,
                "failed_messages": 0,
                "first_message": None,
                "last_message": None,
                "days_back": days_back
            }

        sessions = set(m["session_id"] for m in filtered)
        users = set(m["user_id"] for m in filtered)
        timestamps = [m["timestamp"] for m in filtered if m["timestamp"]]

        stats = {
            "total_messages": len(filtered),
            "total_sessions": len(sessions),
            "user_messages": sum(1 for m in filtered if m["message_type"] == "user"),
            "assistant_messages": sum(1 for m in filtered if m["message_type"] == "assistant"),
            "successful_messages": sum(1 for m in filtered if m["success_flag"]),
            "failed_messages": sum(1 for m in filtered if not m["success_flag"]),
            "first_message": min(timestamps).isoformat() if timestamps else None,
            "last_message": max(timestamps).isoformat() if timestamps else None,
            "days_back": days_back
        }
        if user_id:
            stats["user_id"] = user_id
        else:
            stats["total_users"] = len(users)
        return stats


class ConversationStore:
    """
    Manages conversation history storage in PostgreSQL.

    Features:
    - Store user and assistant messages
    - RBAC enforcement (users can only access their own conversations)
    - Session-based conversation grouping
    - Soft deletion (is_active flag)
    - Tool execution tracking
    - JSON metadata storage
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize ConversationStore with database connection.

        Args:
            connection_string: PostgreSQL connection string
                If None, will load from Config
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            # Lazy import to avoid circular dependencies
            from app.config import settings

            # Use PostgreSQL for conversations
            if settings.use_postgres_for_conversations and PSYCOPG2_AVAILABLE:
                self.connection_string = settings.postgres_dsn
            else:
                # Will use in-memory fallback instead
                self.connection_string = None
                logger.info("PostgreSQL not configured or unavailable, will use in-memory storage")

    def _get_connection(self) -> Any:
        """Get database connection."""
        return psycopg2.connect(self.connection_string)

    def generate_session_id(self, user_id: str) -> str:
        """
        Generate a new session ID for a conversation.

        Format: session_{user_id}_{timestamp}_{uuid}
        Example: session_admin_001_20250114_a1b2c3d4

        Args:
            user_id: User identifier

        Returns:
            Unique session ID
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        short_uuid = str(uuid.uuid4())[:8]
        return f"session_{user_id}_{timestamp}_{short_uuid}"

    def store_message(
        self,
        session_id: str,
        user_id: str,
        user_role: str,
        message_type: str,  # 'user' or 'assistant'
        message_content: str,
        tools_used: Optional[List[str]] = None,
        data_returned: Optional[Dict] = None,
        success_flag: bool = True
    ) -> int:
        """
        Store a message in conversation history.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)
            user_role: User role (ADMIN, HR_MANAGER, etc.)
            message_type: 'user' or 'assistant'
            message_content: The message text
            tools_used: List of tools used (for assistant messages)
            data_returned: Tool execution results (JSON)
            success_flag: Whether the message/tool execution was successful

        Returns:
            conversation_id (primary key of inserted row)

        Raises:
            ValueError: If message_type is invalid
            psycopg2.Error: If database operation fails
        """
        # Validate message type
        if message_type not in ['user', 'assistant']:
            raise ValueError(f"Invalid message_type: {message_type}. Must be 'user' or 'assistant'.")

        # Convert lists to PostgreSQL array format
        tools_array = tools_used if tools_used else None

        # Insert query (PostgreSQL syntax)
        query = """
            INSERT INTO ConversationHistory
                (session_id, user_id, user_role, message_type, message_content,
                 tools_used, success_flag, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING conversation_id
        """

        # Store data_returned as error_message if not successful
        error_msg = json.dumps(data_returned) if data_returned and not success_flag else None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                query,
                (
                    session_id,
                    user_id,
                    user_role,
                    message_type,
                    message_content,
                    tools_array,
                    success_flag,
                    error_msg
                )
            )

            # Get the inserted conversation_id
            conversation_id = cursor.fetchone()[0]

            conn.commit()
            cursor.close()
            conn.close()

            return conversation_id

        except psycopg2.Error as e:
            raise Exception(f"Failed to store message: {str(e)}")

    def get_session_history(
        self,
        session_id: str,
        user_id: str,  # RBAC: Only return this user's messages
        limit: int = 50,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a specific session.

        RBAC Enforcement: Only returns messages for the specified user_id.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC filter)
            limit: Maximum number of messages to return
            include_inactive: Whether to include soft-deleted messages

        Returns:
            List of conversation messages, ordered by timestamp (oldest first)
        """
        query = """
            SELECT
                conversation_id,
                session_id,
                user_id,
                user_role,
                message_type,
                message_content,
                tools_used,
                success_flag,
                error_message,
                timestamp,
                is_active
            FROM ConversationHistory
            WHERE session_id = %s
                AND user_id = %s
                AND (is_active = TRUE OR %s = TRUE)
            ORDER BY timestamp ASC
            LIMIT %s
        """

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                query,
                (
                    session_id,
                    user_id,
                    include_inactive,
                    limit
                )
            )

            messages = []
            for row in cursor.fetchall():
                message = {
                    "conversation_id": row[0],
                    "session_id": row[1],
                    "user_id": row[2],
                    "user_role": row[3],
                    "message_type": row[4],
                    "message_content": row[5],
                    "tools_used": row[6] if row[6] else None,
                    "success_flag": bool(row[7]),
                    "error_message": row[8],
                    "timestamp": row[9].isoformat() if row[9] else None,
                    "is_active": bool(row[10])
                }
                messages.append(message)

            cursor.close()
            conn.close()

            return messages

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve session history: {str(e)}")

    def get_user_history(
        self,
        user_id: str,
        limit: int = 100,
        days_back: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all conversation history for a user.

        RBAC Enforcement: Only returns messages for the specified user_id.

        Args:
            user_id: User identifier (RBAC filter)
            limit: Maximum number of messages to return
            days_back: Only return messages from the last N days

        Returns:
            List of conversation messages, ordered by timestamp (newest first)
        """
        if days_back:
            query = """
                SELECT
                    conversation_id,
                    session_id,
                    user_id,
                    user_role,
                    message_type,
                    message_content,
                    tools_used,
                    success_flag,
                    error_message,
                    timestamp,
                    is_active
                FROM ConversationHistory
                WHERE user_id = %s
                    AND is_active = TRUE
                    AND timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY timestamp DESC
                LIMIT %s
            """
            params = (user_id, days_back, limit)
        else:
            query = """
                SELECT
                    conversation_id,
                    session_id,
                    user_id,
                    user_role,
                    message_type,
                    message_content,
                    tools_used,
                    success_flag,
                    error_message,
                    timestamp,
                    is_active
                FROM ConversationHistory
                WHERE user_id = %s
                    AND is_active = TRUE
                ORDER BY timestamp DESC
                LIMIT %s
            """
            params = (user_id, limit)

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, params)

            messages = []
            for row in cursor.fetchall():
                message = {
                    "conversation_id": row[0],
                    "session_id": row[1],
                    "user_id": row[2],
                    "user_role": row[3],
                    "message_type": row[4],
                    "message_content": row[5],
                    "tools_used": row[6] if row[6] else None,
                    "success_flag": bool(row[7]),
                    "data_returned": json.loads(row[8]) if row[8] else None,
                    "timestamp": row[9].isoformat() if row[9] else None,
                    "is_active": bool(row[10])
                }
                messages.append(message)

            cursor.close()
            conn.close()

            return messages

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve user history: {str(e)}")

    def get_active_sessions(
        self,
        user_id: str,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user within a time window.

        RBAC Enforcement: Only returns sessions for the specified user_id.

        Args:
            user_id: User identifier (RBAC filter)
            days_back: Only return sessions from the last N days

        Returns:
            List of session metadata
        """
        query = """
            SELECT DISTINCT
                session_id,
                MIN(timestamp) AS session_start,
                MAX(timestamp) AS session_end,
                COUNT(*) AS message_count,
                SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END) AS user_messages,
                SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END) AS assistant_messages
            FROM ConversationHistory
            WHERE user_id = %s
                AND is_active = TRUE
                AND timestamp >= NOW() - INTERVAL '%s days'
            GROUP BY session_id
            ORDER BY session_start DESC
        """

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, (user_id, days_back))

            sessions = []
            for row in cursor.fetchall():
                session = {
                    "session_id": row[0],
                    "session_start": row[1].isoformat() if row[1] else None,
                    "session_end": row[2].isoformat() if row[2] else None,
                    "message_count": row[3],
                    "user_messages": row[4],
                    "assistant_messages": row[5]
                }
                sessions.append(session)

            cursor.close()
            conn.close()

            return sessions

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve active sessions: {str(e)}")

    def delete_session(
        self,
        session_id: str,
        user_id: str,  # RBAC: Only delete if user owns the session
        hard_delete: bool = False
    ) -> int:
        """
        Delete a conversation session (soft delete by default).

        RBAC Enforcement: Only deletes if all messages belong to user_id.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC enforcement)
            hard_delete: If True, permanently delete. If False, soft delete (is_active = FALSE)

        Returns:
            Number of messages deleted
        """
        if hard_delete:
            query = """
                DELETE FROM ConversationHistory
                WHERE session_id = %s
                    AND user_id = %s
            """
        else:
            query = """
                UPDATE ConversationHistory
                SET is_active = FALSE
                WHERE session_id = %s
                    AND user_id = %s
                    AND is_active = TRUE
            """

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, (session_id, user_id))
            rows_affected = cursor.rowcount

            conn.commit()
            cursor.close()
            conn.close()

            return rows_affected

        except psycopg2.Error as e:
            raise Exception(f"Failed to delete session: {str(e)}")

    def get_conversation_stats(
        self,
        user_id: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get conversation statistics.

        Args:
            user_id: If provided, stats for specific user. If None, global stats (ADMIN only)
            days_back: Time window for statistics

        Returns:
            Dictionary of statistics
        """
        if user_id:
            query = """
                SELECT
                    COUNT(*) AS total_messages,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END) AS user_messages,
                    SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END) AS assistant_messages,
                    SUM(CASE WHEN success_flag = TRUE THEN 1 ELSE 0 END) AS successful_messages,
                    SUM(CASE WHEN success_flag = FALSE THEN 1 ELSE 0 END) AS failed_messages,
                    MIN(timestamp) AS first_message,
                    MAX(timestamp) AS last_message
                FROM ConversationHistory
                WHERE user_id = %s
                    AND is_active = TRUE
                    AND timestamp >= NOW() - INTERVAL '%s days'
            """
            params = (user_id, days_back)
        else:
            # Global stats (ADMIN only)
            query = """
                SELECT
                    COUNT(*) AS total_messages,
                    COUNT(DISTINCT session_id) AS total_sessions,
                    COUNT(DISTINCT user_id) AS total_users,
                    SUM(CASE WHEN message_type = 'user' THEN 1 ELSE 0 END) AS user_messages,
                    SUM(CASE WHEN message_type = 'assistant' THEN 1 ELSE 0 END) AS assistant_messages,
                    SUM(CASE WHEN success_flag = TRUE THEN 1 ELSE 0 END) AS successful_messages,
                    SUM(CASE WHEN success_flag = FALSE THEN 1 ELSE 0 END) AS failed_messages,
                    MIN(timestamp) AS first_message,
                    MAX(timestamp) AS last_message
                FROM ConversationHistory
                WHERE is_active = TRUE
                    AND timestamp >= NOW() - INTERVAL '%s days'
            """
            params = (days_back,)

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, params)
            row = cursor.fetchone()

            if user_id:
                stats = {
                    "total_messages": row[0],
                    "total_sessions": row[1],
                    "user_messages": row[2],
                    "assistant_messages": row[3],
                    "successful_messages": row[4],
                    "failed_messages": row[5],
                    "first_message": row[6].isoformat() if row[6] else None,
                    "last_message": row[7].isoformat() if row[7] else None,
                    "user_id": user_id,
                    "days_back": days_back
                }
            else:
                stats = {
                    "total_messages": row[0],
                    "total_sessions": row[1],
                    "total_users": row[2],
                    "user_messages": row[3],
                    "assistant_messages": row[4],
                    "successful_messages": row[5],
                    "failed_messages": row[6],
                    "first_message": row[7].isoformat() if row[7] else None,
                    "last_message": row[8].isoformat() if row[8] else None,
                    "days_back": days_back
                }

            cursor.close()
            conn.close()

            return stats

        except psycopg2.Error as e:
            raise Exception(f"Failed to retrieve conversation stats: {str(e)}")


# Global instance - use in-memory fallback if PostgreSQL not configured
def _create_conversation_store():
    """Create the appropriate conversation store based on configuration."""
    from app.config import settings

    if settings.use_postgres_for_conversations and PSYCOPG2_AVAILABLE:
        try:
            store = ConversationStore()
            # Test connection
            conn = store._get_connection()
            conn.close()
            logger.info("Using PostgreSQL for conversation storage")
            return store
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}. Using in-memory storage.")
            return InMemoryConversationStore()
    else:
        logger.info("PostgreSQL not configured. Using in-memory conversation storage.")
        return InMemoryConversationStore()


conversation_store = _create_conversation_store()
