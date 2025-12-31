"""
Phase 3: Conversational Memory System
Provides conversation history storage, retrieval, and semantic search
"""

from app.memory.conversation_store import ConversationStore, conversation_store

# Try to import MemoryRetriever (requires ChromaDB)
try:
    from app.memory.memory_retriever import MemoryRetriever, memory_retriever, CHROMADB_AVAILABLE
except (ImportError, RuntimeError):
    MemoryRetriever = None
    memory_retriever = None
    CHROMADB_AVAILABLE = False

# ConversationManager can work with or without MemoryRetriever
from app.memory.conversation_manager import ConversationManager, conversation_manager

__all__ = [
    "ConversationStore",
    "conversation_store",
    "MemoryRetriever",
    "memory_retriever",
    "ConversationManager",
    "conversation_manager",
    "CHROMADB_AVAILABLE"
]
