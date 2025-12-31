"""
Unit Tests for ConversationStore - Phase 3
Tests conversation history storage and retrieval with RBAC enforcement
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from app.memory.conversation_store import ConversationStore


class TestConversationStoreInitialization:
    """Test suite for ConversationStore initialization"""

    def test_store_initialization_with_connection_string(self):
        """Test initialization with custom connection string"""
        custom_conn = "Server=localhost;Database=Test;Trusted_Connection=yes;"
        store = ConversationStore(connection_string=custom_conn)

        assert store.connection_string == custom_conn

    @patch('app.memory.conversation_store.settings')
    def test_store_initialization_from_config(self, mock_settings):
        """Test initialization loads connection from settings"""
        # Mock settings attributes
        mock_settings.db_driver = "ODBC Driver 17 for SQL Server"
        mock_settings.db_server = "testserver"
        mock_settings.db_name = "testdb"
        mock_settings.db_use_windows_auth = True

        store = ConversationStore()

        # Connection string should be built from settings
        assert store.connection_string is not None
        assert "testserver" in store.connection_string
        assert "testdb" in store.connection_string

    def test_generate_session_id_format(self):
        """Test session ID generation format"""
        store = ConversationStore()
        session_id = store.generate_session_id("testuser")

        # Format: session_{user_id}_{timestamp}_{uuid}
        assert session_id.startswith("session_testuser_")
        parts = session_id.split("_")
        assert len(parts) == 4  # session, testuser, timestamp, uuid
        assert len(parts[2]) == 8  # YYYYMMDD
        assert len(parts[3]) == 8  # 8-char UUID


class TestConversationStoreMessageStorage:
    """Test suite for storing messages"""

    @patch('app.memory.conversation_store.pyodbc')
    def test_store_user_message_success(self, mock_pyodbc):
        """Test storing a user message"""
        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [123]  # ConversationId
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        conversation_id = store.store_message(
            session_id="session_001",
            user_id="test_user",
            user_role="ADMIN",
            message_type="user",
            message_content="What is my salary?"
        )

        # Verify result
        assert conversation_id == 123

        # Verify database calls
        assert mock_cursor.execute.called
        assert mock_conn.commit.called
        assert mock_cursor.close.called
        assert mock_conn.close.called

    @patch('app.memory.conversation_store.pyodbc')
    def test_store_assistant_message_with_tools(self, mock_pyodbc):
        """Test storing assistant message with tool execution data"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [124]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        conversation_id = store.store_message(
            session_id="session_001",
            user_id="test_user",
            user_role="ADMIN",
            message_type="assistant",
            message_content="Your salary is $75,000.",
            tools_used=["query_database"],
            data_returned={"sql": "SELECT Salary FROM Employees", "rows": 1},
            success_flag=True
        )

        assert conversation_id == 124
        assert mock_cursor.execute.called

        # Verify JSON serialization in call
        call_args = mock_cursor.execute.call_args[0]
        assert '["query_database"]' in str(call_args)  # tools_used serialized

    def test_store_message_invalid_type(self):
        """Test storing message with invalid type raises error"""
        store = ConversationStore(connection_string="test")

        with pytest.raises(ValueError) as exc_info:
            store.store_message(
                session_id="session_001",
                user_id="test_user",
                user_role="ADMIN",
                message_type="invalid_type",  # Invalid
                message_content="Test"
            )

        assert "Invalid message_type" in str(exc_info.value)

    @patch('app.memory.conversation_store.pyodbc')
    def test_store_message_database_error(self, mock_pyodbc):
        """Test database error handling"""
        mock_pyodbc.connect.side_effect = Exception("Database connection failed")

        store = ConversationStore(connection_string="test")

        with pytest.raises(Exception) as exc_info:
            store.store_message(
                session_id="session_001",
                user_id="test_user",
                user_role="ADMIN",
                message_type="user",
                message_content="Test"
            )

        assert "Failed to store message" in str(exc_info.value)


class TestConversationStoreRetrieval:
    """Test suite for retrieving conversation history"""

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_session_history_success(self, mock_pyodbc):
        """Test retrieving session history"""
        # Mock database rows
        mock_rows = [
            (1, "session_001", "user_001", "ADMIN", "user", "What is my salary?", None, None, True, datetime.utcnow(), True),
            (2, "session_001", "user_001", "ADMIN", "assistant", "Your salary is $75,000", '["query_database"]', '{"rows": 1}', True, datetime.utcnow(), True)
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        messages = store.get_session_history(
            session_id="session_001",
            user_id="user_001"
        )

        # Verify results
        assert len(messages) == 2
        assert messages[0]["message_type"] == "user"
        assert messages[1]["message_type"] == "assistant"
        assert messages[1]["tools_used"] == ["query_database"]

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_session_history_rbac_enforcement(self, mock_pyodbc):
        """Test RBAC enforcement in session history retrieval"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        messages = store.get_session_history(
            session_id="session_001",
            user_id="user_001"
        )

        # Verify SQL includes user_id filter
        call_args = mock_cursor.execute.call_args[0]
        assert "UserId = ?" in call_args[0]
        assert "user_001" in call_args[1:]

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_user_history_with_limit(self, mock_pyodbc):
        """Test retrieving user history with limit"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        messages = store.get_user_history(
            user_id="user_001",
            limit=20
        )

        # Verify TOP clause
        call_args = mock_cursor.execute.call_args[0]
        assert "TOP (?)" in call_args[0]
        assert 20 in call_args[1:]

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_user_history_with_time_filter(self, mock_pyodbc):
        """Test retrieving user history with time filter"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        messages = store.get_user_history(
            user_id="user_001",
            days_back=7
        )

        # Verify DATEADD clause
        call_args = mock_cursor.execute.call_args[0]
        assert "DATEADD" in call_args[0]
        assert 7 in call_args[1:]


class TestConversationStoreSessionManagement:
    """Test suite for session management"""

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_active_sessions(self, mock_pyodbc):
        """Test retrieving active sessions"""
        mock_rows = [
            ("session_001", datetime.utcnow() - timedelta(hours=2), datetime.utcnow(), 10, 5, 5),
            ("session_002", datetime.utcnow() - timedelta(days=1), datetime.utcnow() - timedelta(days=1), 6, 3, 3)
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        sessions = store.get_active_sessions(
            user_id="user_001",
            days_back=7
        )

        # Verify results
        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session_001"
        assert sessions[0]["message_count"] == 10
        assert sessions[0]["user_messages"] == 5
        assert sessions[0]["assistant_messages"] == 5

    @patch('app.memory.conversation_store.pyodbc')
    def test_delete_session_soft_delete(self, mock_pyodbc):
        """Test soft deleting a session"""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        rows_deleted = store.delete_session(
            session_id="session_001",
            user_id="user_001",
            hard_delete=False  # Soft delete
        )

        # Verify soft delete (UPDATE)
        call_args = mock_cursor.execute.call_args[0]
        assert "UPDATE" in call_args[0]
        assert "IsActive = 0" in call_args[0]
        assert rows_deleted == 5

    @patch('app.memory.conversation_store.pyodbc')
    def test_delete_session_hard_delete(self, mock_pyodbc):
        """Test hard deleting a session"""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        rows_deleted = store.delete_session(
            session_id="session_001",
            user_id="user_001",
            hard_delete=True
        )

        # Verify hard delete (DELETE)
        call_args = mock_cursor.execute.call_args[0]
        assert "DELETE" in call_args[0]
        assert rows_deleted == 5

    @patch('app.memory.conversation_store.pyodbc')
    def test_delete_session_rbac_enforcement(self, mock_pyodbc):
        """Test RBAC enforcement in session deletion"""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No rows deleted (not the user's session)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        rows_deleted = store.delete_session(
            session_id="session_001",
            user_id="unauthorized_user",  # Different user
            hard_delete=False
        )

        # Should return 0 (RBAC prevents deletion)
        assert rows_deleted == 0


class TestConversationStoreStatistics:
    """Test suite for conversation statistics"""

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_user_stats(self, mock_pyodbc):
        """Test retrieving user conversation statistics"""
        mock_row = (
            100,  # total_messages
            10,   # total_sessions
            50,   # user_messages
            50,   # assistant_messages
            95,   # successful_messages
            5,    # failed_messages
            datetime.utcnow() - timedelta(days=30),  # first_message
            datetime.utcnow()  # last_message
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        stats = store.get_conversation_stats(
            user_id="user_001",
            days_back=30
        )

        # Verify results
        assert stats["total_messages"] == 100
        assert stats["total_sessions"] == 10
        assert stats["user_messages"] == 50
        assert stats["assistant_messages"] == 50
        assert stats["successful_messages"] == 95
        assert stats["failed_messages"] == 5
        assert stats["user_id"] == "user_001"

    @patch('app.memory.conversation_store.pyodbc')
    def test_get_global_stats(self, mock_pyodbc):
        """Test retrieving global statistics (ADMIN only)"""
        mock_row = (
            1000,  # total_messages
            150,   # total_sessions
            50,    # total_users
            500,   # user_messages
            500,   # assistant_messages
            950,   # successful_messages
            50,    # failed_messages
            datetime.utcnow() - timedelta(days=60),  # first_message
            datetime.utcnow()  # last_message
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        store = ConversationStore(connection_string="test")
        stats = store.get_conversation_stats(
            user_id=None,  # Global stats
            days_back=30
        )

        # Verify results
        assert stats["total_messages"] == 1000
        assert stats["total_sessions"] == 150
        assert stats["total_users"] == 50
        assert "user_id" not in stats  # Global stats


class TestConversationStoreIntegration:
    """Integration tests for common workflows"""

    @patch('app.memory.conversation_store.pyodbc')
    def test_full_conversation_workflow(self, mock_pyodbc):
        """Test complete conversation storage and retrieval workflow"""
        # Mock for store operations
        mock_cursor_store = MagicMock()
        mock_cursor_store.fetchone.side_effect = [[1], [2]]  # Two conversation IDs

        # Mock for retrieval
        mock_cursor_retrieve = MagicMock()
        mock_rows = [
            (1, "session_001", "user_001", "ADMIN", "user", "What is my salary?", None, None, True, datetime.utcnow(), True),
            (2, "session_001", "user_001", "ADMIN", "assistant", "Your salary is $75,000", '["query_database"]', '{"rows": 1}', True, datetime.utcnow(), True)
        ]
        mock_cursor_retrieve.fetchall.return_value = mock_rows

        mock_conn = MagicMock()
        # Return different cursors for different operations
        mock_conn.cursor.side_effect = [mock_cursor_store, mock_cursor_store, mock_cursor_retrieve]
        mock_pyodbc.connect.return_value = mock_conn

        # Workflow
        store = ConversationStore(connection_string="test")

        # 1. Generate session
        session_id = store.generate_session_id("user_001")
        assert session_id.startswith("session_user_001_")

        # 2. Store user message
        msg1_id = store.store_message(
            session_id=session_id,
            user_id="user_001",
            user_role="ADMIN",
            message_type="user",
            message_content="What is my salary?"
        )
        assert msg1_id == 1

        # 3. Store assistant response
        msg2_id = store.store_message(
            session_id=session_id,
            user_id="user_001",
            user_role="ADMIN",
            message_type="assistant",
            message_content="Your salary is $75,000",
            tools_used=["query_database"],
            data_returned={"rows": 1}
        )
        assert msg2_id == 2

        # 4. Retrieve conversation
        messages = store.get_session_history(
            session_id=session_id,
            user_id="user_001"
        )
        assert len(messages) == 2


class TestConversationStoreGlobalInstance:
    """Test global instance"""

    def test_global_instance_exists(self):
        """Test global conversation_store instance is available"""
        from app.memory import conversation_store

        assert conversation_store is not None
        assert isinstance(conversation_store, ConversationStore)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
