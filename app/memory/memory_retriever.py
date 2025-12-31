"""
Memory Retriever - Phase 3
Provides semantic search of conversation history using RAG
Features: ChromaDB vector storage, sentence transformers, RBAC enforcement
"""

import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
from app.memory.conversation_store import ConversationStore

# Optional ChromaDB and sentence transformers imports
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None


class MemoryRetriever:
    """
    Semantic search of conversation history using RAG.

    Features:
    - ChromaDB vector database for embedding storage
    - Sentence transformers for text embeddings
    - RBAC enforcement (users can only search their own conversations)
    - Hybrid search: semantic + keyword
    - Configurable result ranking
    """

    def __init__(
        self,
        conversation_store: Optional[ConversationStore] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        chroma_persist_directory: Optional[str] = "./chroma_db",
        collection_name: str = "conversation_memory",
        chroma_mode: Optional[str] = None,
        chroma_host: str = "localhost",
        chroma_port: int = 8000
    ):
        """
        Initialize MemoryRetriever with ChromaDB and embedding model.

        Args:
            conversation_store: ConversationStore instance for accessing conversation data
            embedding_model: Sentence transformer model name
            chroma_persist_directory: Directory to persist ChromaDB data (for embedded mode)
            collection_name: ChromaDB collection name
            chroma_mode: 'http' for Docker/remote server, 'embedded' for local storage, None for auto-detect
            chroma_host: ChromaDB server host (for http mode)
            chroma_port: ChromaDB server port (for http mode)

        Raises:
            RuntimeError: If ChromaDB or sentence-transformers are not installed
        """
        import os

        # Check if dependencies are available
        if not CHROMADB_AVAILABLE:
            raise RuntimeError(
                "ChromaDB is not installed. Install it with: pip install chromadb-client (for Docker/HTTP mode)\n"
                "Or: pip install chromadb (for embedded mode, requires Microsoft Visual C++ 14.0+ on Windows)"
            )

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is not installed. Install it with: pip install sentence-transformers"
            )

        # Initialize conversation store
        if conversation_store:
            self.conversation_store = conversation_store
        else:
            self.conversation_store = ConversationStore()

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dimension = self.embedding_model.get_sentence_embedding_dimension()

        # Determine ChromaDB mode from environment if not specified
        if chroma_mode is None:
            chroma_mode = os.getenv("CHROMADB_MODE", "http").lower()

        if chroma_host == "localhost":
            chroma_host = os.getenv("CHROMADB_HOST", "localhost")

        if chroma_port == 8000:
            chroma_port = int(os.getenv("CHROMADB_PORT", "8000"))

        if not chroma_persist_directory or chroma_persist_directory == "./chroma_db":
            chroma_persist_directory = os.getenv("CHROMADB_PERSIST_DIRECTORY", "./chroma_db")

        if collection_name == "conversation_memory":
            collection_name = os.getenv("CHROMADB_COLLECTION_NAME", "conversation_memory")

        # Initialize ChromaDB client based on mode
        self.chroma_mode = chroma_mode

        if chroma_mode == "http":
            # HTTP client for Docker or remote ChromaDB server
            self.chroma_client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=Settings(anonymized_telemetry=False)
            )
            print(f"[MemoryRetriever] Connected to ChromaDB server at {chroma_host}:{chroma_port} (HTTP mode)")

        elif chroma_mode == "embedded":
            # Embedded client for local persistent storage
            if chroma_persist_directory:
                self.chroma_client = chromadb.PersistentClient(
                    path=chroma_persist_directory,
                    settings=Settings(anonymized_telemetry=False)
                )
                print(f"[MemoryRetriever] Using ChromaDB embedded mode at {chroma_persist_directory}")
            else:
                # In-memory client for testing
                self.chroma_client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False)
                )
                print("[MemoryRetriever] Using ChromaDB in-memory mode")

        else:
            raise ValueError(f"Invalid CHROMADB_MODE: {chroma_mode}. Must be 'http' or 'embedded'.")

        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Conversation memory embeddings with RBAC"}
        )

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        return self.embedding_model.encode(text).tolist()

    def _format_conversation_text(self, message: Dict[str, Any]) -> str:
        """
        Format conversation message for embedding.

        Args:
            message: Message dict from ConversationStore

        Returns:
            Formatted text string
        """
        # Format: "MessageType: MessageContent [Tools: tool1, tool2]"
        text = f"{message['message_type'].upper()}: {message['message_content']}"

        if message.get('tools_used'):
            tools_str = ", ".join(message['tools_used'])
            text += f" [Tools: {tools_str}]"

        return text

    def add_conversation_to_index(
        self,
        session_id: str,
        user_id: str,
        conversation_messages: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add conversation messages to ChromaDB index.

        RBAC Enforcement: Only indexes messages for the specified user_id.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)
            conversation_messages: List of message dicts from ConversationStore

        Returns:
            List of ChromaDB document IDs created

        Raises:
            ValueError: If conversation_messages is empty
        """
        if not conversation_messages:
            raise ValueError("conversation_messages cannot be empty")

        # Prepare documents for ChromaDB
        documents = []
        embeddings = []
        metadatas = []
        ids = []

        for msg in conversation_messages:
            # Verify RBAC: Only index messages for this user
            if msg['user_id'] != user_id:
                continue

            # Format text for embedding
            text = self._format_conversation_text(msg)

            # Generate embedding
            embedding = self._generate_embedding(text)

            # Generate unique ID
            doc_id = str(uuid.uuid4())

            # Prepare metadata
            metadata = {
                "conversation_id": str(msg['conversation_id']),
                "session_id": session_id,
                "user_id": user_id,
                "user_role": msg['user_role'],
                "message_type": msg['message_type'],
                "timestamp": msg['timestamp'],
                "success_flag": str(msg['success_flag'])  # ChromaDB requires string
            }

            # Add to batch
            documents.append(text)
            embeddings.append(embedding)
            metadatas.append(metadata)
            ids.append(doc_id)

        # Add to ChromaDB
        if documents:
            self.collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )

        return ids

    def semantic_search(
        self,
        query: str,
        user_id: str,
        n_results: int = 5,
        session_id: Optional[str] = None,
        message_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on conversation history.

        RBAC Enforcement: Only searches conversations for the specified user_id.

        Args:
            query: Search query text
            user_id: User identifier (RBAC filter)
            n_results: Number of results to return
            session_id: Optional filter by session
            message_type: Optional filter by message type ('user' or 'assistant')

        Returns:
            List of search results with metadata and similarity scores
        """
        # Generate query embedding
        query_embedding = self._generate_embedding(query)

        # Build where filter for RBAC
        where_filter = {"user_id": user_id}

        if session_id:
            where_filter["session_id"] = session_id

        if message_type:
            where_filter["message_type"] = message_type

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )

        # Format results
        formatted_results = []

        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                result = {
                    "document_id": results['ids'][0][i],
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results else None,
                    "similarity_score": 1 - results['distances'][0][i] if 'distances' in results else None
                }
                formatted_results.append(result)

        return formatted_results

    def get_relevant_context(
        self,
        query: str,
        user_id: str,
        n_results: int = 3,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get relevant conversation context for a query.

        RBAC Enforcement: Only retrieves context from user's own conversations.

        Args:
            query: Search query
            user_id: User identifier (RBAC)
            n_results: Number of relevant messages to retrieve
            session_id: Optional filter by session

        Returns:
            Formatted context string for RAG augmentation
        """
        # Perform semantic search
        results = self.semantic_search(
            query=query,
            user_id=user_id,
            n_results=n_results,
            session_id=session_id
        )

        if not results:
            return "No relevant conversation history found."

        # Format context
        context_parts = [
            "=== Relevant Conversation History ===",
            ""
        ]

        for i, result in enumerate(results, 1):
            meta = result['metadata']
            score = result.get('similarity_score', 0)

            context_parts.append(
                f"{i}. [{meta['message_type'].upper()}] "
                f"(Session: {meta['session_id'][:20]}..., "
                f"Similarity: {score:.2f})"
            )
            context_parts.append(f"   {result['document']}")
            context_parts.append("")

        return "\n".join(context_parts)

    def delete_user_embeddings(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> int:
        """
        Delete embeddings for a user (RBAC enforced).

        Args:
            user_id: User identifier
            session_id: Optional - delete only specific session

        Returns:
            Number of embeddings deleted
        """
        # Build where filter
        where_filter = {"user_id": user_id}

        if session_id:
            where_filter["session_id"] = session_id

        # Get matching documents
        results = self.collection.get(where=where_filter)

        if results['ids']:
            # Delete by IDs
            self.collection.delete(ids=results['ids'])
            return len(results['ids'])

        return 0

    def get_embedding_stats(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about stored embeddings.

        Args:
            user_id: If provided, stats for specific user. If None, global stats.

        Returns:
            Dictionary with embedding statistics
        """
        if user_id:
            results = self.collection.get(where={"user_id": user_id})
            return {
                "user_id": user_id,
                "total_embeddings": len(results['ids']) if results['ids'] else 0,
                "collection_name": self.collection.name
            }
        else:
            # Global stats
            total = self.collection.count()
            return {
                "total_embeddings": total,
                "collection_name": self.collection.name,
                "embedding_dimension": self.embedding_dimension,
                "embedding_model": str(self.embedding_model)
            }

    def sync_session_to_index(
        self,
        session_id: str,
        user_id: str
    ) -> List[str]:
        """
        Sync a complete session to the embedding index.

        Retrieves session from ConversationStore and adds to ChromaDB.
        RBAC enforced through ConversationStore.

        Args:
            session_id: Session identifier
            user_id: User identifier (RBAC)

        Returns:
            List of ChromaDB document IDs created
        """
        # Get session history from ConversationStore
        messages = self.conversation_store.get_session_history(
            session_id=session_id,
            user_id=user_id,
            limit=1000,
            include_inactive=False
        )

        if not messages:
            return []

        # Add to index
        return self.add_conversation_to_index(
            session_id=session_id,
            user_id=user_id,
            conversation_messages=messages
        )

    def sync_all_user_sessions(
        self,
        user_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Sync all user sessions to the embedding index.

        Args:
            user_id: User identifier
            days_back: Only sync sessions from last N days

        Returns:
            Dictionary with sync statistics
        """
        # Get all user sessions
        sessions = self.conversation_store.get_active_sessions(
            user_id=user_id,
            days_back=days_back
        )

        total_embeddings = 0
        synced_sessions = 0

        for session in sessions:
            session_id = session['session_id']

            # Sync this session
            doc_ids = self.sync_session_to_index(
                session_id=session_id,
                user_id=user_id
            )

            if doc_ids:
                total_embeddings += len(doc_ids)
                synced_sessions += 1

        return {
            "user_id": user_id,
            "synced_sessions": synced_sessions,
            "total_sessions": len(sessions),
            "total_embeddings": total_embeddings,
            "days_back": days_back
        }


# Global instance (only create if ChromaDB is available)
if CHROMADB_AVAILABLE and SENTENCE_TRANSFORMERS_AVAILABLE:
    try:
        memory_retriever = MemoryRetriever()
    except Exception:
        # If initialization fails, set to None
        memory_retriever = None
else:
    memory_retriever = None
