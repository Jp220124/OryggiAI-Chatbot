# Phase 3 Implementation Plan: Conversational Memory System

**Status:** Planning
**Duration:** 5-7 days
**Dependencies:** Phase 1 (RAG), Phase 2 (Tool Registry + RBAC)
**Goal:** Enable context-aware conversations with persistent memory

---

## Executive Summary

### What We're Building

A conversational memory system that allows the chatbot to:
- Remember past conversations with each user
- Provide context-aware responses based on conversation history
- Retrieve relevant past exchanges using RAG
- Enforce RBAC (users can only access their own conversation history)

### Why This Matters

**Current State:** Chatbot treats each question as isolated, no memory of past interactions

**Target State:** Chatbot remembers previous conversations, providing contextual answers like:
- "As we discussed yesterday, the IT department has 15 employees..."
- "Following up on your earlier question about attendance..."
- "You previously asked about John Doe - he's in the Finance department..."

### Success Metrics

- Conversation persistence: 100% (all messages saved)
- Memory retrieval accuracy: 90%+ (relevant past conversations retrieved)
- Context integration: 80%+ (bot successfully uses past context)
- RBAC enforcement: 100% (zero unauthorized access to other users' conversations)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER QUESTION                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              CONVERSATION MEMORY SYSTEM (Phase 3)                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  1. Store Current Message                               │    │
│  │     - Save user question to ConversationHistory         │    │
│  │     - Apply RBAC scoping (user_id)                      │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  2. Retrieve Relevant Past Conversations (RAG)          │    │
│  │     - Embed current question                            │    │
│  │     - Search ChromaDB for similar past exchanges        │    │
│  │     - Filter by user_id (RBAC enforcement)              │    │
│  │     - Return top-k relevant conversations               │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  3. Build Context for LLM                               │    │
│  │     - Current question                                  │    │
│  │     - Relevant past conversations                       │    │
│  │     - System prompt with memory context                 │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              TOOL REGISTRY (Phase 2)                             │
│  Execute tools with memory-enhanced context                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              RESPONSE + SAVE TO MEMORY                           │
│  - Generate answer using QueryDatabaseTool/other tools           │
│  - Save bot response to ConversationHistory                      │
│  - Update embeddings for future retrieval                        │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction

```
┌──────────────────────┐
│  FastAPI Endpoint    │
│  /api/chat/message   │
└──────────────────────┘
         ↓
┌──────────────────────┐
│ ConversationManager  │ ← NEW: Orchestrates memory + tools
│  - store_message()   │
│  - retrieve_context()│
│  - execute_with_ctx()│
└──────────────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
┌─────────┐ ┌─────────────────┐
│ Memory  │ │ Tool Registry   │
│ Storage │ │ (Phase 2)       │
└─────────┘ └─────────────────┘
    ↓              ↓
┌─────────┐ ┌─────────────────┐
│ChromaDB │ │QueryDatabaseTool│
│ (RAG)   │ │                 │
└─────────┘ └─────────────────┘
    ↓              ↓
┌───────────────────────────────┐
│  SQL Server Database          │
│  - ConversationHistory table  │
│  - UserRoles table (Phase 2)  │
└───────────────────────────────┘
```

---

## Database Schema

### ConversationHistory Table

```sql
CREATE TABLE dbo.ConversationHistory (
    -- Primary Key
    ConversationId INT IDENTITY(1,1) PRIMARY KEY,

    -- Session Management
    SessionId NVARCHAR(100) NOT NULL,  -- Group related messages
    UserId NVARCHAR(50) NOT NULL,      -- User who sent message
    UserRole NVARCHAR(20) NOT NULL,    -- User's role at time of message

    -- Message Content
    MessageType NVARCHAR(10) NOT NULL  -- 'user' or 'assistant'
        CHECK (MessageType IN ('user', 'assistant')),
    MessageContent NVARCHAR(MAX) NOT NULL,

    -- Context & Metadata
    ToolsUsed NVARCHAR(MAX),           -- JSON array of tools used
    DataReturned NVARCHAR(MAX),        -- JSON summary of data returned
    SuccessFlag BIT DEFAULT 1,         -- Whether query succeeded

    -- Timestamps
    Timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),

    -- Soft Delete
    IsActive BIT NOT NULL DEFAULT 1,

    -- Foreign Keys
    FOREIGN KEY (UserId) REFERENCES UserRoles(UserId)
);

-- Indexes for Performance
CREATE NONCLUSTERED INDEX IX_ConversationHistory_UserId
    ON dbo.ConversationHistory(UserId, Timestamp DESC)
    WHERE IsActive = 1;

CREATE NONCLUSTERED INDEX IX_ConversationHistory_SessionId
    ON dbo.ConversationHistory(SessionId, Timestamp ASC)
    WHERE IsActive = 1;

CREATE NONCLUSTERED INDEX IX_ConversationHistory_Timestamp
    ON dbo.ConversationHistory(Timestamp DESC)
    WHERE IsActive = 1;
```

### ConversationEmbeddings Table (for RAG)

```sql
CREATE TABLE dbo.ConversationEmbeddings (
    EmbeddingId INT IDENTITY(1,1) PRIMARY KEY,
    ConversationId INT NOT NULL,
    UserId NVARCHAR(50) NOT NULL,

    -- Embedding Vector (stored as JSON or binary)
    EmbeddingVector NVARCHAR(MAX) NOT NULL,  -- JSON array of floats

    -- Metadata for filtering
    MessageType NVARCHAR(10) NOT NULL,
    Timestamp DATETIME2 NOT NULL,

    FOREIGN KEY (ConversationId) REFERENCES ConversationHistory(ConversationId),
    FOREIGN KEY (UserId) REFERENCES UserRoles(UserId)
);

CREATE NONCLUSTERED INDEX IX_ConversationEmbeddings_UserId
    ON dbo.ConversationEmbeddings(UserId, Timestamp DESC);
```

### Sample Data

```sql
-- Example conversation
INSERT INTO dbo.ConversationHistory
(SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
-- User asks question
('session_001', 'manager_001', 'HR_MANAGER', 'user',
 'How many employees in the IT department?',
 NULL, NULL, 1),

-- Assistant responds
('session_001', 'manager_001', 'HR_MANAGER', 'assistant',
 'The IT department has 15 employees.',
 '["query_database"]',
 '{"query_result": {"count": 15}, "tables_used": ["Employees", "Departments"]}',
 1),

-- Follow-up question (uses context)
('session_001', 'manager_001', 'HR_MANAGER', 'user',
 'What about Finance?',
 NULL, NULL, 1),

-- Context-aware response
('session_001', 'manager_001', 'HR_MANAGER', 'assistant',
 'The Finance department has 12 employees.',
 '["query_database"]',
 '{"query_result": {"count": 12}}',
 1);
```

---

## Implementation Components

### 1. Memory Storage System

**File:** `app/memory/conversation_store.py`

```python
"""
Conversation Storage System
Handles persistent storage of chat messages
"""

from typing import List, Dict, Optional
from datetime import datetime
import pyodbc
from loguru import logger

from app.config import Config


class ConversationStore:
    """
    Manages conversation history storage in SQL Server

    Features:
    - Store user and assistant messages
    - Retrieve conversation history by session
    - Apply RBAC filtering (users can only see own conversations)
    - Support for soft deletion
    """

    def __init__(self, connection_string: Optional[str] = None):
        """Initialize with optional connection string for testing"""
        self._connection_string = connection_string

    @property
    def connection_string(self) -> str:
        """Lazy-load connection string from Config"""
        if not self._connection_string:
            from app.config import Config
            self._connection_string = Config.DATABASE_CONNECTION_STRING
        return self._connection_string

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
        Store a message in conversation history

        Args:
            session_id: Session identifier (groups related messages)
            user_id: User who sent/received message
            user_role: User's role at time of message
            message_type: 'user' or 'assistant'
            message_content: The actual message text
            tools_used: List of tools used (for assistant messages)
            data_returned: Summary of data returned (for assistant messages)
            success_flag: Whether the query succeeded

        Returns:
            conversation_id: ID of stored message

        Example:
            # Store user question
            conv_id = store.store_message(
                session_id="session_123",
                user_id="manager_001",
                user_role="HR_MANAGER",
                message_type="user",
                message_content="How many employees in IT?"
            )

            # Store assistant response
            store.store_message(
                session_id="session_123",
                user_id="manager_001",
                user_role="HR_MANAGER",
                message_type="assistant",
                message_content="There are 15 employees in IT.",
                tools_used=["query_database"],
                data_returned={"count": 15, "tables": ["Employees"]},
                success_flag=True
            )
        """
        conn = pyodbc.connect(self.connection_string)
        cursor = conn.cursor()

        try:
            # Convert tools_used and data_returned to JSON
            import json
            tools_json = json.dumps(tools_used) if tools_used else None
            data_json = json.dumps(data_returned) if data_returned else None

            query = """
            INSERT INTO dbo.ConversationHistory
            (SessionId, UserId, UserRole, MessageType, MessageContent,
             ToolsUsed, DataReturned, SuccessFlag)
            OUTPUT INSERTED.ConversationId
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            cursor.execute(query, (
                session_id,
                user_id,
                user_role,
                message_type,
                message_content,
                tools_json,
                data_json,
                success_flag
            ))

            conversation_id = cursor.fetchone()[0]
            conn.commit()

            logger.info(f"Stored {message_type} message (ID: {conversation_id}) for {user_id}")
            return conversation_id

        except Exception as e:
            logger.error(f"Failed to store message: {str(e)}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_session_history(
        self,
        session_id: str,
        user_id: str,  # RBAC: Only return this user's messages
        limit: int = 50
    ) -> List[Dict]:
        """
        Retrieve conversation history for a session

        Args:
            session_id: Session to retrieve
            user_id: User requesting history (RBAC enforcement)
            limit: Maximum messages to return

        Returns:
            List of message dictionaries

        Example:
            history = store.get_session_history(
                session_id="session_123",
                user_id="manager_001",
                limit=20
            )
            # Returns: [
            #   {"message_type": "user", "content": "How many..."},
            #   {"message_type": "assistant", "content": "There are 15..."}
            # ]
        """
        conn = pyodbc.connect(self.connection_string)
        cursor = conn.cursor()

        try:
            query = """
            SELECT TOP (?)
                ConversationId,
                MessageType,
                MessageContent,
                ToolsUsed,
                DataReturned,
                Timestamp
            FROM dbo.ConversationHistory
            WHERE SessionId = ?
              AND UserId = ?  -- RBAC: Only this user's messages
              AND IsActive = 1
            ORDER BY Timestamp ASC
            """

            cursor.execute(query, (limit, session_id, user_id))
            rows = cursor.fetchall()

            messages = []
            for row in rows:
                import json
                messages.append({
                    "conversation_id": row[0],
                    "message_type": row[1],
                    "message_content": row[2],
                    "tools_used": json.loads(row[3]) if row[3] else None,
                    "data_returned": json.loads(row[4]) if row[4] else None,
                    "timestamp": row[5].isoformat()
                })

            return messages

        finally:
            conn.close()

    def get_user_conversations(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Retrieve all conversations for a user within date range

        Args:
            user_id: User to retrieve conversations for
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum messages to return

        Returns:
            List of message dictionaries
        """
        conn = pyodbc.connect(self.connection_string)
        cursor = conn.cursor()

        try:
            query = """
            SELECT TOP (?)
                ConversationId,
                SessionId,
                MessageType,
                MessageContent,
                Timestamp
            FROM dbo.ConversationHistory
            WHERE UserId = ?  -- RBAC: Only this user's messages
              AND IsActive = 1
            """

            params = [limit, user_id]

            if start_date:
                query += " AND Timestamp >= ?"
                params.append(start_date)

            if end_date:
                query += " AND Timestamp <= ?"
                params.append(end_date)

            query += " ORDER BY Timestamp DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            conversations = []
            for row in rows:
                conversations.append({
                    "conversation_id": row[0],
                    "session_id": row[1],
                    "message_type": row[2],
                    "message_content": row[3],
                    "timestamp": row[4].isoformat()
                })

            return conversations

        finally:
            conn.close()

    def delete_session(
        self,
        session_id: str,
        user_id: str  # RBAC: Only delete this user's sessions
    ) -> int:
        """
        Soft-delete a conversation session

        Args:
            session_id: Session to delete
            user_id: User requesting deletion (RBAC enforcement)

        Returns:
            Number of messages deleted
        """
        conn = pyodbc.connect(self.connection_string)
        cursor = conn.cursor()

        try:
            query = """
            UPDATE dbo.ConversationHistory
            SET IsActive = 0
            WHERE SessionId = ?
              AND UserId = ?  -- RBAC: Only delete this user's messages
              AND IsActive = 1
            """

            cursor.execute(query, (session_id, user_id))
            rows_affected = cursor.rowcount
            conn.commit()

            logger.info(f"Deleted {rows_affected} messages from session {session_id}")
            return rows_affected

        except Exception as e:
            logger.error(f"Failed to delete session: {str(e)}")
            conn.rollback()
            raise
        finally:
            conn.close()


# Global conversation store instance
conversation_store = ConversationStore()
```

### 2. Memory Retrieval with RAG

**File:** `app/memory/memory_retriever.py`

```python
"""
Memory Retrieval System
Uses RAG to find relevant past conversations
"""

from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from loguru import logger


class MemoryRetriever:
    """
    Retrieves relevant past conversations using RAG

    Features:
    - Embed conversation messages
    - Semantic search for relevant past exchanges
    - Filter by user_id (RBAC enforcement)
    - Return top-k most relevant conversations
    """

    def __init__(
        self,
        collection_name: str = "conversation_memory",
        persist_directory: str = "./data/chroma_db_memory"
    ):
        """Initialize ChromaDB for conversation memory"""

        # Initialize ChromaDB client
        self.chroma_client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory
        ))

        # Get or create collection
        try:
            self.collection = self.chroma_client.get_collection(collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except:
            self.collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {collection_name}")

        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Memory retriever initialized")

    def add_conversation_to_memory(
        self,
        conversation_id: int,
        user_id: str,
        message_content: str,
        message_type: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Add a conversation message to the memory vector store

        Args:
            conversation_id: Unique ID from ConversationHistory table
            user_id: User who sent/received message
            message_content: The message text
            message_type: 'user' or 'assistant'
            metadata: Optional additional metadata

        Example:
            retriever.add_conversation_to_memory(
                conversation_id=123,
                user_id="manager_001",
                message_content="How many employees in IT?",
                message_type="user",
                metadata={"session_id": "session_123", "timestamp": "2025-01-14"}
            )
        """
        try:
            # Generate embedding
            embedding = self.embedding_model.encode(message_content).tolist()

            # Prepare metadata
            full_metadata = {
                "user_id": user_id,
                "message_type": message_type,
                "conversation_id": conversation_id
            }
            if metadata:
                full_metadata.update(metadata)

            # Add to ChromaDB
            self.collection.add(
                ids=[f"conv_{conversation_id}"],
                embeddings=[embedding],
                documents=[message_content],
                metadatas=[full_metadata]
            )

            logger.debug(f"Added conversation {conversation_id} to memory")

        except Exception as e:
            logger.error(f"Failed to add conversation to memory: {str(e)}")

    def retrieve_relevant_conversations(
        self,
        query: str,
        user_id: str,  # RBAC: Only retrieve this user's conversations
        top_k: int = 5,
        message_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve relevant past conversations using semantic search

        Args:
            query: Current user question
            user_id: User requesting retrieval (RBAC enforcement)
            top_k: Number of relevant conversations to return
            message_type: Optional filter by 'user' or 'assistant'

        Returns:
            List of relevant conversation dictionaries

        Example:
            # User asks: "What about Finance?"
            relevant = retriever.retrieve_relevant_conversations(
                query="What about Finance?",
                user_id="manager_001",
                top_k=3
            )
            # Returns past conversations about departments/employees
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()

            # Build filter for RBAC
            where_filter = {"user_id": user_id}
            if message_type:
                where_filter["message_type"] = message_type

            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter  # RBAC: Only this user's conversations
            )

            # Format results
            relevant_conversations = []
            for i in range(len(results['ids'][0])):
                relevant_conversations.append({
                    "conversation_id": results['metadatas'][0][i]['conversation_id'],
                    "message_content": results['documents'][0][i],
                    "message_type": results['metadatas'][0][i]['message_type'],
                    "distance": results['distances'][0][i] if 'distances' in results else None,
                    "metadata": results['metadatas'][0][i]
                })

            logger.info(f"Retrieved {len(relevant_conversations)} relevant conversations for {user_id}")
            return relevant_conversations

        except Exception as e:
            logger.error(f"Failed to retrieve conversations: {str(e)}")
            return []

    def clear_user_memory(
        self,
        user_id: str
    ) -> int:
        """
        Clear all conversation memory for a user

        Args:
            user_id: User whose memory to clear

        Returns:
            Number of conversations removed
        """
        try:
            # Get all conversation IDs for this user
            results = self.collection.get(
                where={"user_id": user_id}
            )

            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Cleared {len(results['ids'])} conversations for {user_id}")
                return len(results['ids'])

            return 0

        except Exception as e:
            logger.error(f"Failed to clear memory: {str(e)}")
            return 0


# Global memory retriever instance
memory_retriever = MemoryRetriever()
```

### 3. Conversation Manager

**File:** `app/memory/conversation_manager.py`

```python
"""
Conversation Manager
Orchestrates memory storage, retrieval, and tool execution
"""

from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime
from loguru import logger

from app.memory.conversation_store import conversation_store
from app.memory.memory_retriever import memory_retriever
from app.tools import tool_registry


class ConversationManager:
    """
    High-level conversation management

    Workflow:
    1. Store user message
    2. Retrieve relevant past conversations
    3. Build context for LLM
    4. Execute tool with enhanced context
    5. Store assistant response
    6. Update memory embeddings
    """

    def __init__(self):
        """Initialize conversation manager"""
        self.store = conversation_store
        self.retriever = memory_retriever
        logger.info("Conversation manager initialized")

    def process_message(
        self,
        user_id: str,
        user_role: str,
        message: str,
        session_id: Optional[str] = None,
        use_memory: bool = True,
        tool_name: str = "query_database"
    ) -> Dict[str, Any]:
        """
        Process a user message with conversational memory

        Args:
            user_id: User sending message
            user_role: User's role
            message: User's question/message
            session_id: Optional session ID (creates new if not provided)
            use_memory: Whether to use past conversations for context
            tool_name: Tool to execute (default: query_database)

        Returns:
            {
                "success": bool,
                "answer": str,
                "session_id": str,
                "memory_used": bool,
                "relevant_conversations": List[Dict],
                "tool_result": Dict
            }

        Example:
            result = manager.process_message(
                user_id="manager_001",
                user_role="HR_MANAGER",
                message="How many employees in IT?",
                session_id="session_123"
            )
        """
        start_time = datetime.now()

        # Generate session ID if not provided
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"
            logger.info(f"Created new session: {session_id}")

        try:
            # Step 1: Store user message
            user_conv_id = self.store.store_message(
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                message_type="user",
                message_content=message
            )

            # Add to memory embeddings
            self.retriever.add_conversation_to_memory(
                conversation_id=user_conv_id,
                user_id=user_id,
                message_content=message,
                message_type="user",
                metadata={"session_id": session_id}
            )

            # Step 2: Retrieve relevant past conversations (if enabled)
            relevant_conversations = []
            memory_context = ""

            if use_memory:
                relevant_conversations = self.retriever.retrieve_relevant_conversations(
                    query=message,
                    user_id=user_id,
                    top_k=3
                )

                # Build memory context string
                if relevant_conversations:
                    memory_context = self._format_memory_context(relevant_conversations)
                    logger.info(f"Retrieved {len(relevant_conversations)} relevant past conversations")

            # Step 3: Execute tool with enhanced context
            enhanced_question = message
            if memory_context:
                enhanced_question = f"{memory_context}\n\nCurrent question: {message}"

            tool_result = tool_registry.execute_tool(
                tool_name=tool_name,
                user_role=user_role,
                question=enhanced_question,
                user_id=user_id
            )

            # Step 4: Format assistant response
            if tool_result["success"]:
                assistant_message = tool_result["result"]["natural_answer"]
                tools_used = [tool_name]
                data_summary = {
                    "result_count": tool_result["result"].get("result_count", 0),
                    "data_scoped": tool_result["result"].get("data_scoped", False)
                }
            else:
                assistant_message = f"I encountered an error: {tool_result['error']}"
                tools_used = [tool_name]
                data_summary = {"error": tool_result['error']}

            # Step 5: Store assistant response
            assistant_conv_id = self.store.store_message(
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                message_type="assistant",
                message_content=assistant_message,
                tools_used=tools_used,
                data_returned=data_summary,
                success_flag=tool_result["success"]
            )

            # Add assistant response to memory
            self.retriever.add_conversation_to_memory(
                conversation_id=assistant_conv_id,
                user_id=user_id,
                message_content=assistant_message,
                message_type="assistant",
                metadata={"session_id": session_id}
            )

            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

            return {
                "success": tool_result["success"],
                "answer": assistant_message,
                "session_id": session_id,
                "memory_used": use_memory and len(relevant_conversations) > 0,
                "relevant_conversations": relevant_conversations,
                "tool_result": tool_result,
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "success": False,
                "answer": f"I encountered an error: {str(e)}",
                "session_id": session_id,
                "memory_used": False,
                "relevant_conversations": [],
                "tool_result": None,
                "error": str(e)
            }

    def _format_memory_context(
        self,
        conversations: List[Dict]
    ) -> str:
        """
        Format relevant past conversations into context string

        Args:
            conversations: List of relevant conversation dicts

        Returns:
            Formatted context string for LLM
        """
        if not conversations:
            return ""

        context_parts = ["Here are some relevant past conversations:"]

        for i, conv in enumerate(conversations, 1):
            context_parts.append(
                f"\n{i}. {conv['message_type'].upper()}: {conv['message_content']}"
            )

        return "\n".join(context_parts)

    def get_session_summary(
        self,
        session_id: str,
        user_id: str
    ) -> Dict:
        """
        Get summary of a conversation session

        Args:
            session_id: Session to summarize
            user_id: User requesting summary (RBAC)

        Returns:
            Session summary with statistics
        """
        history = self.store.get_session_history(
            session_id=session_id,
            user_id=user_id,
            limit=1000
        )

        user_messages = [m for m in history if m["message_type"] == "user"]
        assistant_messages = [m for m in history if m["message_type"] == "assistant"]

        return {
            "session_id": session_id,
            "total_messages": len(history),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "tools_used": list(set([
                tool
                for msg in assistant_messages
                if msg["tools_used"]
                for tool in msg["tools_used"]
            ])),
            "first_message": history[0] if history else None,
            "last_message": history[-1] if history else None
        }


# Global conversation manager instance
conversation_manager = ConversationManager()
```

---

## Day-by-Day Implementation Plan

### Day 1: Database Schema + Storage System

**Tasks:**

1. **Create ConversationHistory table**
   - Run SQL script to create table
   - Add indexes for performance
   - Verify foreign keys

2. **Implement ConversationStore class**
   - `store_message()` method
   - `get_session_history()` method
   - `get_user_conversations()` method
   - `delete_session()` method

3. **Unit Tests for Storage**
   - Test message storage
   - Test session retrieval
   - Test RBAC enforcement (users can only see own messages)
   - Test soft deletion

**Deliverable:** Working conversation storage with RBAC

**Success Criteria:**
- All messages stored successfully
- RBAC prevents cross-user access
- 10/10 storage tests passing

---

### Day 2: Memory Retrieval with RAG

**Tasks:**

1. **Setup ChromaDB for conversations**
   - Create separate collection for conversation memory
   - Configure embedding model (all-MiniLM-L6-v2)

2. **Implement MemoryRetriever class**
   - `add_conversation_to_memory()` method
   - `retrieve_relevant_conversations()` method
   - `clear_user_memory()` method

3. **Test RAG retrieval**
   - Store sample conversations
   - Test semantic search
   - Test RBAC filtering (user_id)
   - Verify top-k retrieval accuracy

**Deliverable:** Working memory retrieval with RAG

**Success Criteria:**
- Semantic search returns relevant conversations
- RBAC prevents cross-user retrieval
- Retrieval accuracy > 90%
- 10/10 retrieval tests passing

---

### Day 3: Conversation Manager

**Tasks:**

1. **Implement ConversationManager class**
   - `process_message()` orchestration
   - Memory context formatting
   - Tool execution with enhanced context

2. **Integrate with Tool Registry**
   - Pass memory context to tools
   - Handle tool responses
   - Store results in conversation history

3. **Test End-to-End Workflow**
   - User sends message → stored
   - Relevant past conversations retrieved
   - Tool executed with context
   - Assistant response stored

**Deliverable:** Complete conversation workflow

**Success Criteria:**
- Messages flow through full pipeline
- Context correctly retrieved and used
- Tool execution successful
- 15/15 integration tests passing

---

### Day 4: API Integration

**Tasks:**

1. **Update FastAPI endpoints**
   - Modify `/api/chat/query` to use ConversationManager
   - Add `/api/chat/history` endpoint
   - Add `/api/chat/sessions` endpoint

2. **Session Management**
   - Generate session IDs
   - Track active sessions
   - Support session continuation

3. **Response Format**
   - Include memory_used flag
   - Return relevant conversations
   - Add session metadata

**Deliverable:** API endpoints with memory support

**Success Criteria:**
- `/api/chat/query` uses memory
- `/api/chat/history` returns session history
- 10/10 API tests passing

---

### Day 5: Testing + Documentation

**Tasks:**

1. **Comprehensive Testing**
   - Unit tests (storage, retrieval, manager)
   - Integration tests (end-to-end)
   - RBAC security tests
   - Performance tests (1000+ conversations)

2. **Documentation**
   - API endpoint docs
   - Usage examples
   - RBAC enforcement docs
   - Performance tuning guide

3. **Performance Optimization**
   - Add database indexes
   - Optimize ChromaDB queries
   - Cache frequent retrievals

**Deliverable:** Production-ready system with docs

**Success Criteria:**
- 90%+ test coverage
- All docs complete
- Performance benchmarks met

---

## Testing Strategy

### Unit Tests

**Storage Tests** (`tests/test_conversation_store.py`)
- Test message storage
- Test session retrieval
- Test user conversation retrieval
- Test RBAC filtering
- Test soft deletion

**Retrieval Tests** (`tests/test_memory_retriever.py`)
- Test conversation embedding
- Test semantic search
- Test RBAC filtering
- Test top-k accuracy
- Test memory clearing

**Manager Tests** (`tests/test_conversation_manager.py`)
- Test message processing
- Test memory context building
- Test tool integration
- Test session management

### Integration Tests

**End-to-End Tests** (`tests/test_memory_integration.py`)
- Test complete conversation flow
- Test multi-turn conversations
- Test context awareness
- Test RBAC enforcement
- Test error handling

### Performance Tests

**Benchmarks:**
- Store 1000 messages: < 5 seconds
- Retrieve session history (50 messages): < 500ms
- Semantic search (top-5): < 200ms
- Full message processing: < 3 seconds

---

## RBAC Integration

### User-Specific Memory Access

**Rule:** Users can ONLY access their own conversation history

**Implementation:**

1. **Storage Level:**
   ```python
   # Always filter by user_id in WHERE clause
   WHERE UserId = ? AND SessionId = ?
   ```

2. **Retrieval Level:**
   ```python
   # ChromaDB filter
   where={"user_id": user_id}
   ```

3. **API Level:**
   ```python
   # Extract user_id from JWT token
   current_user = get_current_user(token)

   # Only allow access to own conversations
   if requested_user_id != current_user.user_id:
       raise PermissionError("Cannot access other users' conversations")
   ```

### Audit Logging

Log all memory access:
```python
audit_logger.log_data_access(
    user_id=user_id,
    user_role=user_role,
    operation="retrieve_conversation",
    session_id=session_id,
    rows_returned=len(history)
)
```

---

## API Endpoints

### 1. Send Message (with Memory)

**Endpoint:** `POST /api/chat/message`

**Request:**
```json
{
  "message": "How many employees in Finance?",
  "session_id": "session_123",  // optional, creates new if not provided
  "use_memory": true,  // default: true
  "tool_name": "query_database"  // default: query_database
}
```

**Response:**
```json
{
  "success": true,
  "answer": "The Finance department has 12 employees. As we discussed earlier, IT has 15 employees.",
  "session_id": "session_123",
  "memory_used": true,
  "relevant_conversations": [
    {
      "message_content": "How many employees in IT?",
      "message_type": "user"
    },
    {
      "message_content": "The IT department has 15 employees.",
      "message_type": "assistant"
    }
  ],
  "execution_time_ms": 1250
}
```

### 2. Get Session History

**Endpoint:** `GET /api/chat/history/{session_id}`

**Response:**
```json
{
  "session_id": "session_123",
  "messages": [
    {
      "message_type": "user",
      "message_content": "How many employees in IT?",
      "timestamp": "2025-01-14T10:00:00"
    },
    {
      "message_type": "assistant",
      "message_content": "The IT department has 15 employees.",
      "timestamp": "2025-01-14T10:00:02"
    }
  ],
  "total_messages": 2
}
```

### 3. List User Sessions

**Endpoint:** `GET /api/chat/sessions`

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "session_123",
      "first_message": "How many employees...",
      "last_message": "The Finance department...",
      "message_count": 4,
      "created_at": "2025-01-14T10:00:00",
      "last_updated": "2025-01-14T10:15:00"
    }
  ],
  "total_sessions": 1
}
```

### 4. Delete Session

**Endpoint:** `DELETE /api/chat/sessions/{session_id}`

**Response:**
```json
{
  "success": true,
  "messages_deleted": 4
}
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Message Storage | 100% | All messages saved to database |
| Retrieval Accuracy | 90%+ | Relevant conversations retrieved |
| Context Integration | 80%+ | Bot uses past context successfully |
| RBAC Enforcement | 100% | Zero unauthorized access |
| Response Time | < 3s | Storage + retrieval + tool execution |
| Test Coverage | 90%+ | Unit + integration tests |

---

## Dependencies

### Python Packages

```bash
# Already installed from Phase 1-2:
# - chromadb
# - sentence-transformers
# - pyodbc
# - loguru
# - fastapi

# No new dependencies needed!
```

### Database

- SQL Server (existing)
- New tables: ConversationHistory, ConversationEmbeddings
- Foreign keys to UserRoles (Phase 2)

---

## Next Phase Preview

**Phase 4: Multi-Agent System**

With conversational memory in place, Phase 4 will add:
- Multiple specialized agents (SQL Agent, Report Agent, Action Agent)
- Agent orchestration with LangGraph
- Tool routing based on intent
- Multi-turn conversations with agent hand-offs

The memory system from Phase 3 will provide context to all agents!

---

**Document Version:** 1.0
**Status:** Ready for Implementation
**Estimated Timeline:** 5-7 days
