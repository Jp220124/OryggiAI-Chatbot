"""
Unit Tests for MemoryRetriever - Phase 3
Tests semantic search, RAG capabilities, and RBAC enforcement
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from app.memory.memory_retriever import MemoryRetriever


class TestMemoryRetrieverInitialization:
    """Test MemoryRetriever initialization"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_init_with_defaults(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test initialization with default parameters"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        # Initialize
        retriever = MemoryRetriever()

        # Assertions
        assert retriever.embedding_dimension == 384
        assert retriever.collection == mock_collection
        mock_transformer.assert_called_once_with("all-MiniLM-L6-v2")
        mock_chromadb.PersistentClient.assert_called_once()

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_init_with_custom_params(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test initialization with custom parameters"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        # Initialize with custom params
        retriever = MemoryRetriever(
            embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
            chroma_persist_directory="./custom_chroma",
            collection_name="custom_collection"
        )

        # Assertions
        mock_transformer.assert_called_once_with("paraphrase-multilingual-MiniLM-L12-v2")
        mock_chromadb.PersistentClient.assert_called_once_with(
            path="./custom_chroma",
            settings=mock_chromadb.Settings(anonymized_telemetry=False)
        )

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    def test_init_in_memory_mode(self, mock_transformer, mock_chromadb):
        """Test initialization with in-memory ChromaDB"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.Client.return_value = mock_client

        # Initialize with in-memory
        retriever = MemoryRetriever(chroma_persist_directory=None)

        # Assertions
        mock_chromadb.Client.assert_called_once()
        mock_chromadb.PersistentClient.assert_not_called()


class TestMemoryRetrieverEmbedding:
    """Test embedding generation"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_generate_embedding(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test embedding generation"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Generate embedding
        embedding = retriever._generate_embedding("What is my salary?")

        # Assertions
        assert embedding == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with("What is my salary?")

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_format_conversation_text(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test conversation text formatting"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Test message without tools
        message = {
            "message_type": "user",
            "message_content": "What is my salary?",
            "tools_used": None
        }

        formatted = retriever._format_conversation_text(message)
        assert formatted == "USER: What is my salary?"

        # Test message with tools
        message_with_tools = {
            "message_type": "assistant",
            "message_content": "Your salary is $75,000",
            "tools_used": ["query_database", "format_response"]
        }

        formatted_tools = retriever._format_conversation_text(message_with_tools)
        assert formatted_tools == "ASSISTANT: Your salary is $75,000 [Tools: query_database, format_response]"


class TestMemoryRetrieverIndexing:
    """Test adding conversations to ChromaDB index"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_add_conversation_to_index_success(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test adding conversation messages to index"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Prepare test messages
        messages = [
            {
                "conversation_id": 1,
                "user_id": "test_user",
                "user_role": "ADMIN",
                "message_type": "user",
                "message_content": "What is my salary?",
                "tools_used": None,
                "success_flag": True,
                "timestamp": "2025-01-14T10:00:00"
            },
            {
                "conversation_id": 2,
                "user_id": "test_user",
                "user_role": "ADMIN",
                "message_type": "assistant",
                "message_content": "Your salary is $75,000",
                "tools_used": ["query_database"],
                "success_flag": True,
                "timestamp": "2025-01-14T10:00:05"
            }
        ]

        # Add to index
        doc_ids = retriever.add_conversation_to_index(
            session_id="session_001",
            user_id="test_user",
            conversation_messages=messages
        )

        # Assertions
        assert len(doc_ids) == 2
        mock_collection.add.assert_called_once()

        # Verify ChromaDB add was called with correct structure
        call_args = mock_collection.add.call_args
        assert len(call_args.kwargs['documents']) == 2
        assert len(call_args.kwargs['embeddings']) == 2
        assert len(call_args.kwargs['metadatas']) == 2
        assert len(call_args.kwargs['ids']) == 2

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_add_conversation_rbac_enforcement(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test RBAC enforcement - only index messages for specified user"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Messages from different users
        messages = [
            {
                "conversation_id": 1,
                "user_id": "test_user",
                "user_role": "ADMIN",
                "message_type": "user",
                "message_content": "What is my salary?",
                "tools_used": None,
                "success_flag": True,
                "timestamp": "2025-01-14T10:00:00"
            },
            {
                "conversation_id": 2,
                "user_id": "other_user",  # Different user
                "user_role": "ADMIN",
                "message_type": "user",
                "message_content": "What is my salary?",
                "tools_used": None,
                "success_flag": True,
                "timestamp": "2025-01-14T10:05:00"
            }
        ]

        # Add to index for test_user only
        doc_ids = retriever.add_conversation_to_index(
            session_id="session_001",
            user_id="test_user",
            conversation_messages=messages
        )

        # Assertions - only 1 message should be indexed
        assert len(doc_ids) == 1
        call_args = mock_collection.add.call_args
        assert len(call_args.kwargs['documents']) == 1

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_add_conversation_empty_messages(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test error handling for empty messages"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Test empty messages
        with pytest.raises(ValueError, match="conversation_messages cannot be empty"):
            retriever.add_conversation_to_index(
                session_id="session_001",
                user_id="test_user",
                conversation_messages=[]
            )


class TestMemoryRetrieverSearch:
    """Test semantic search functionality"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_semantic_search_success(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test semantic search with results"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            'ids': [['doc1', 'doc2']],
            'documents': [['USER: What is my salary?', 'ASSISTANT: Your salary is $75,000']],
            'metadatas': [[
                {'user_id': 'test_user', 'session_id': 'session_001', 'message_type': 'user'},
                {'user_id': 'test_user', 'session_id': 'session_001', 'message_type': 'assistant'}
            ]],
            'distances': [[0.2, 0.3]]
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Perform search
        results = retriever.semantic_search(
            query="salary information",
            user_id="test_user",
            n_results=5
        )

        # Assertions
        assert len(results) == 2
        assert results[0]['document_id'] == 'doc1'
        assert results[0]['document'] == 'USER: What is my salary?'
        assert results[0]['similarity_score'] == 0.8  # 1 - 0.2
        assert results[1]['similarity_score'] == 0.7  # 1 - 0.3

        # Verify RBAC filter
        call_args = mock_collection.query.call_args
        assert call_args.kwargs['where']['user_id'] == 'test_user'

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_semantic_search_with_filters(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test semantic search with session and message type filters"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {'ids': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Perform search with filters
        results = retriever.semantic_search(
            query="salary",
            user_id="test_user",
            n_results=3,
            session_id="session_001",
            message_type="user"
        )

        # Verify filters
        call_args = mock_collection.query.call_args
        assert call_args.kwargs['where']['user_id'] == 'test_user'
        assert call_args.kwargs['where']['session_id'] == 'session_001'
        assert call_args.kwargs['where']['message_type'] == 'user'

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_semantic_search_no_results(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test semantic search with no results"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {'ids': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Perform search
        results = retriever.semantic_search(
            query="nonexistent topic",
            user_id="test_user",
            n_results=5
        )

        # Assertions
        assert results == []


class TestMemoryRetrieverContext:
    """Test RAG context generation"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_get_relevant_context(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test getting formatted RAG context"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            'ids': [['doc1', 'doc2']],
            'documents': [['USER: What is my salary?', 'ASSISTANT: Your salary is $75,000']],
            'metadatas': [[
                {'user_id': 'test_user', 'session_id': 'session_test_001_20250114_abc123', 'message_type': 'user'},
                {'user_id': 'test_user', 'session_id': 'session_test_001_20250114_abc123', 'message_type': 'assistant'}
            ]],
            'distances': [[0.1, 0.15]]
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Get context
        context = retriever.get_relevant_context(
            query="salary information",
            user_id="test_user",
            n_results=2
        )

        # Assertions
        assert "=== Relevant Conversation History ===" in context
        assert "USER: What is my salary?" in context
        assert "ASSISTANT: Your salary is $75,000" in context
        assert "Similarity: 0.90" in context  # 1 - 0.1
        assert "Similarity: 0.85" in context  # 1 - 0.15

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_get_relevant_context_no_results(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test context generation with no results"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {'ids': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Get context
        context = retriever.get_relevant_context(
            query="nonexistent topic",
            user_id="test_user",
            n_results=3
        )

        # Assertions
        assert context == "No relevant conversation history found."


class TestMemoryRetrieverDeletion:
    """Test embedding deletion"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_delete_user_embeddings(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test deleting all embeddings for a user"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.get.return_value = {'ids': ['doc1', 'doc2', 'doc3']}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Delete embeddings
        deleted_count = retriever.delete_user_embeddings(user_id="test_user")

        # Assertions
        assert deleted_count == 3
        mock_collection.get.assert_called_once_with(where={'user_id': 'test_user'})
        mock_collection.delete.assert_called_once_with(ids=['doc1', 'doc2', 'doc3'])

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_delete_session_embeddings(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test deleting embeddings for specific session"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.get.return_value = {'ids': ['doc1', 'doc2']}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Delete session embeddings
        deleted_count = retriever.delete_user_embeddings(
            user_id="test_user",
            session_id="session_001"
        )

        # Assertions
        assert deleted_count == 2
        call_args = mock_collection.get.call_args
        assert call_args.kwargs['where']['user_id'] == 'test_user'
        assert call_args.kwargs['where']['session_id'] == 'session_001'


class TestMemoryRetrieverStatistics:
    """Test statistics methods"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_get_embedding_stats_user(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test getting embedding stats for specific user"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "conversation_memory"
        mock_collection.get.return_value = {'ids': ['doc1', 'doc2', 'doc3']}
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Get stats
        stats = retriever.get_embedding_stats(user_id="test_user")

        # Assertions
        assert stats['user_id'] == 'test_user'
        assert stats['total_embeddings'] == 3
        assert stats['collection_name'] == 'conversation_memory'

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_get_embedding_stats_global(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test getting global embedding stats"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "conversation_memory"
        mock_collection.count.return_value = 150
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        retriever = MemoryRetriever()

        # Get global stats
        stats = retriever.get_embedding_stats()

        # Assertions
        assert stats['total_embeddings'] == 150
        assert stats['collection_name'] == 'conversation_memory'
        assert stats['embedding_dimension'] == 384


class TestMemoryRetrieverSync:
    """Test session synchronization"""

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_sync_session_to_index(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test syncing a session to the index"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        mock_store = MagicMock()
        mock_store.get_session_history.return_value = [
            {
                "conversation_id": 1,
                "user_id": "test_user",
                "user_role": "ADMIN",
                "message_type": "user",
                "message_content": "Test message",
                "tools_used": None,
                "success_flag": True,
                "timestamp": "2025-01-14T10:00:00"
            }
        ]
        mock_store_class.return_value = mock_store

        retriever = MemoryRetriever(conversation_store=mock_store)

        # Sync session
        doc_ids = retriever.sync_session_to_index(
            session_id="session_001",
            user_id="test_user"
        )

        # Assertions
        assert len(doc_ids) == 1
        mock_store.get_session_history.assert_called_once_with(
            session_id="session_001",
            user_id="test_user",
            limit=1000,
            include_inactive=False
        )

    @patch('app.memory.memory_retriever.chromadb')
    @patch('app.memory.memory_retriever.SentenceTransformer')
    @patch('app.memory.memory_retriever.ConversationStore')
    def test_sync_all_user_sessions(self, mock_store_class, mock_transformer, mock_chromadb):
        """Test syncing all user sessions"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock()
        mock_model.encode.return_value.tolist.return_value = [0.1] * 384
        mock_transformer.return_value = mock_model

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client

        mock_store = MagicMock()
        mock_store.get_active_sessions.return_value = [
            {"session_id": "session_001", "message_count": 4},
            {"session_id": "session_002", "message_count": 6}
        ]
        mock_store.get_session_history.side_effect = [
            [{"conversation_id": 1, "user_id": "test_user", "user_role": "ADMIN", "message_type": "user", "message_content": "Test 1", "tools_used": None, "success_flag": True, "timestamp": "2025-01-14T10:00:00"}],
            [{"conversation_id": 2, "user_id": "test_user", "user_role": "ADMIN", "message_type": "user", "message_content": "Test 2", "tools_used": None, "success_flag": True, "timestamp": "2025-01-14T11:00:00"}]
        ]
        mock_store_class.return_value = mock_store

        retriever = MemoryRetriever(conversation_store=mock_store)

        # Sync all sessions
        sync_stats = retriever.sync_all_user_sessions(
            user_id="test_user",
            days_back=30
        )

        # Assertions
        assert sync_stats['synced_sessions'] == 2
        assert sync_stats['total_sessions'] == 2
        assert sync_stats['total_embeddings'] == 2
        assert sync_stats['user_id'] == 'test_user'
        assert sync_stats['days_back'] == 30


class TestMemoryRetrieverGlobalInstance:
    """Test global instance"""

    def test_global_instance_exists(self):
        """Test that global memory_retriever instance exists"""
        from app.memory.memory_retriever import memory_retriever
        assert memory_retriever is not None
        assert isinstance(memory_retriever, MemoryRetriever)
