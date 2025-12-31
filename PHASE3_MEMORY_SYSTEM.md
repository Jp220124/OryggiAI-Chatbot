# Phase 3: Conversational Memory System

## Overview

Phase 3 introduces a production-ready conversational memory system that separates conversation storage from client databases. This architecture allows the chatbot to maintain conversation history with full write permissions while accessing client data in read-only mode.

## Architecture

### Key Components

1. **PostgreSQL in Docker** - Stores conversation history with full control
2. **ChromaDB in Docker** - Vector database for semantic search (RAG)
3. **ConversationStore** - Python module for conversation CRUD operations
4. **MemoryRetriever** - RAG system for context-aware responses

### Data Isolation

```
Client SQL Server (READ-ONLY)
  └─> Business Data Queries

PostgreSQL Docker (FULL CONTROL)
  └─> Conversation History
       └─> Auto-sync to ChromaDB
            └─> Semantic Search / RAG
```

## Installation & Setup

### 1. Start Docker Containers

```bash
# Start PostgreSQL + ChromaDB
docker-compose up -d

# Verify containers are running
docker ps
```

Expected output:
```
chatbot_postgres   5432   (healthy)
chatbot_chromadb   8000   (healthy)
```

### 2. Verify Database Schema

```bash
# Connect to PostgreSQL
docker exec -it chatbot_postgres psql -U chatbot_user -d chatbot_conversations

# Check table exists
\dt

# View table structure
\d ConversationHistory

# Exit
\q
```

### 3. Run Integration Tests

```bash
cd Advance_Chatbot
venv/Scripts/python.exe tests/test_postgres_chromadb.py
```

Expected result: **4/4 tests passed**

## Configuration

### Environment Variables (.env)

```bash
# ==================== PostgreSQL Configuration ====================
USE_POSTGRES_FOR_CONVERSATIONS=True

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_conversations
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password_2025

# ==================== ChromaDB Configuration ====================
CHROMADB_MODE=http
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
CHROMADB_COLLECTION_NAME=conversation_memory
```

## Usage

### Basic Conversation Storage

```python
from app.memory.conversation_store import ConversationStore

# Initialize
store = ConversationStore()

# Generate session ID
session_id = store.generate_session_id(user_id="admin_001")
# Output: session_admin_001_20251115_a1b2c3d4

# Store user message
user_msg_id = store.store_message(
    session_id=session_id,
    user_id="admin_001",
    user_role="ADMIN",
    message_type="user",
    message_content="How many employees do we have in Engineering?"
)

# Store assistant response
assistant_msg_id = store.store_message(
    session_id=session_id,
    user_id="admin_001",
    user_role="ADMIN",
    message_type="assistant",
    message_content="Based on the SQL query, there are 45 employees in Engineering.",
    tools_used=["sql_tool"],
    data_returned={"query": "SELECT COUNT(*) FROM Employees WHERE Department='Engineering'", "result": 45},
    success_flag=True
)

# Retrieve session history
history = store.get_session_history(
    session_id=session_id,
    user_id="admin_001",
    limit=50
)

print(f"Found {len(history)} messages")
for msg in history:
    print(f"[{msg['message_type']}] {msg['message_content']}")
```

### RAG Semantic Search

```python
from app.memory.memory_retriever import MemoryRetriever

# Initialize retriever
retriever = MemoryRetriever()

# Sync session to ChromaDB
doc_ids = retriever.add_conversation_to_index(
    session_id=session_id,
    user_id="admin_001",
    conversation_messages=history
)
print(f"Created {len(doc_ids)} embeddings")

# Semantic search
results = retriever.semantic_search(
    query="How many people work in Engineering?",
    user_id="admin_001",
    n_results=5
)

for i, result in enumerate(results, 1):
    similarity = result.get('similarity_score', 0)
    content = result['document']
    print(f"{i}. [Score: {similarity:.3f}] {content}")
```

### Conversation Statistics

```python
# User-specific stats
stats = store.get_conversation_stats(user_id="admin_001", days_back=30)

print(f"Total Messages: {stats['total_messages']}")
print(f"Total Sessions: {stats['total_sessions']}")
print(f"User Messages: {stats['user_messages']}")
print(f"Assistant Messages: {stats['assistant_messages']}")
print(f"Success Rate: {stats['successful_messages'] / stats['total_messages'] * 100:.1f}%")

# Get active sessions
sessions = store.get_active_sessions(user_id="admin_001", days_back=7)
for session in sessions:
    print(f"Session: {session['session_id']}")
    print(f"  Started: {session['session_start']}")
    print(f"  Messages: {session['message_count']}")
```

## Database Schema

### ConversationHistory Table

| Column | Type | Description |
|--------|------|-------------|
| conversation_id | SERIAL PRIMARY KEY | Auto-increment ID |
| session_id | VARCHAR(255) | Conversation session identifier |
| user_id | VARCHAR(255) | User identifier (RBAC) |
| user_role | VARCHAR(50) | User role (ADMIN, HR_MANAGER, etc.) |
| message_type | VARCHAR(20) | 'user', 'assistant', or 'system' |
| message_content | TEXT | Message text content |
| tools_used | TEXT[] | Array of tools used (PostgreSQL array) |
| success_flag | BOOLEAN | Whether operation succeeded |
| error_message | TEXT | Error details if failed |
| timestamp | TIMESTAMP WITH TIME ZONE | Message timestamp (UTC) |
| is_active | BOOLEAN | Soft delete flag |

### Indexes

- `idx_session_id` - Fast session lookups
- `idx_user_id` - Fast user queries
- `idx_timestamp` - Time-based queries
- `idx_session_user` - Combined session+user queries
- `idx_active_messages` - Filter active messages

## RBAC Enforcement

All operations enforce Role-Based Access Control:

```python
# Users can ONLY access their own conversations
my_history = store.get_session_history(
    session_id=session_id,
    user_id="admin_001"  # Only returns admin_001's messages
)

# Different user gets 0 results
other_history = store.get_session_history(
    session_id=session_id,
    user_id="other_user"  # Returns []
)

# RAG also enforces RBAC
my_results = retriever.semantic_search(
    query="Engineering employees",
    user_id="admin_001"  # Only searches admin_001's conversations
)
```

## Integration into Chat Workflow

### Current State

The `/query` endpoint (`app/api/chat.py:24`) currently:
- Receives user question
- Processes with SQL agent
- Returns SQL answer
- **Does NOT store conversations**

### Recommended Integration

```python
# app/api/chat.py

from app.memory.conversation_store import conversation_store
from app.memory.memory_retriever import memory_retriever

@router.post("/query", response_model=ChatQueryResponse)
async def query_chatbot(request: ChatQueryRequest):
    start_time = time.time()

    # Generate or retrieve session_id
    session_id = request.session_id or conversation_store.generate_session_id(request.user_id)

    # Optional: Get relevant past context from RAG
    past_context = memory_retriever.get_relevant_context(
        query=request.question,
        user_id=request.user_id,
        n_results=3,
        session_id=session_id  # Optional: limit to current session
    )

    # Store user question
    user_msg_id = conversation_store.store_message(
        session_id=session_id,
        user_id=request.user_id,
        user_role=request.user_role,  # Add to request model
        message_type="user",
        message_content=request.question
    )

    try:
        # Process query (optionally include past_context)
        result = sql_agent.query_and_answer(request.question)

        # Store assistant response
        assistant_msg_id = conversation_store.store_message(
            session_id=session_id,
            user_id=request.user_id,
            user_role=request.user_role,
            message_type="assistant",
            message_content=result["natural_answer"],
            tools_used=["sql_tool"],
            data_returned=result,
            success_flag=("error" not in result)
        )

        # Auto-sync to ChromaDB for RAG (async recommended)
        # Note: Could be done in background task
        session_messages = conversation_store.get_session_history(
            session_id=session_id,
            user_id=request.user_id,
            limit=100
        )
        memory_retriever.add_conversation_to_index(
            session_id=session_id,
            user_id=request.user_id,
            conversation_messages=session_messages
        )

        # Return response with session_id
        return ChatQueryResponse(
            session_id=session_id,  # Add to response model
            question=request.question,
            sql_query=result["sql_query"],
            answer=result["natural_answer"],
            # ... rest of response
        )

    except Exception as e:
        # Store error in conversation
        conversation_store.store_message(
            session_id=session_id,
            user_id=request.user_id,
            user_role=request.user_role,
            message_type="assistant",
            message_content=f"Error: {str(e)}",
            success_flag=False,
            data_returned={"error": str(e)}
        )
        raise
```

## Testing

### 1. PostgreSQL Connection Test

```bash
python -c "from app.memory.conversation_store import ConversationStore; store = ConversationStore(); print('✓ PostgreSQL connection successful')"
```

### 2. ChromaDB Connection Test

```bash
python -c "from app.memory.memory_retriever import MemoryRetriever; retriever = MemoryRetriever(); print('✓ ChromaDB connection successful')"
```

### 3. Full Integration Test

```bash
cd Advance_Chatbot
venv/Scripts/python.exe tests/test_postgres_chromadb.py
```

Expected output:
```
[OK] PASS - PostgreSQL Connection
[OK] PASS - ConversationStore Operations
[OK] PASS - ChromaDB Connection
[OK] PASS - RAG Functionality
------------------------------------------------------------
Results: 4/4 tests passed
```

## Deployment

### Development

```bash
# Start services
docker-compose up -d

# Run application
cd Advance_Chatbot
venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 9000
```

### Production

1. **Security Hardening**:
   - Change default passwords in `.env`
   - Use secrets management (AWS Secrets Manager, Azure Key Vault)
   - Enable SSL/TLS for PostgreSQL and ChromaDB

2. **Persistent Volumes**:
   ```yaml
   volumes:
     postgres_data:
       driver: local
       driver_opts:
         type: none
         o: bind
         device: /path/to/persistent/postgres
     chromadb_data:
       driver: local
       driver_opts:
         type: none
         o: bind
         device: /path/to/persistent/chromadb
   ```

3. **Backup Strategy**:
   ```bash
   # PostgreSQL backup
   docker exec chatbot_postgres pg_dump -U chatbot_user chatbot_conversations > backup_$(date +%Y%m%d).sql

   # ChromaDB backup (copy volume)
   docker run --rm -v chromadb_data:/data -v $(pwd):/backup busybox tar czf /backup/chromadb_backup_$(date +%Y%m%d).tar.gz /data
   ```

4. **Monitoring**:
   - Add healthcheck endpoints
   - Monitor container health
   - Track conversation stats
   - Alert on database connection failures

## Performance Considerations

### PostgreSQL

- **Indexes**: Already optimized for common queries
- **Connection Pooling**: Configure `POSTGRES_POOL_SIZE` in `.env`
- **Vacuuming**: Automatic with PostgreSQL 16
- **Partitioning**: Consider partitioning by date for large datasets

### ChromaDB

- **Batch Indexing**: Use `add_conversation_to_index` for bulk operations
- **Query Optimization**: Limit `n_results` to reasonable values (3-10)
- **Collection Management**: One collection per application
- **Embeddings Model**: all-MiniLM-L6-v2 (384 dimensions, fast)

### Application

- **Async Operations**: Use background tasks for ChromaDB sync
- **Caching**: Cache frequently accessed session data
- **Rate Limiting**: Prevent abuse of semantic search

## Troubleshooting

### Issue: "PostgreSQL container not healthy"

```bash
# Check logs
docker logs chatbot_postgres

# Verify port not in use
netstat -ano | findstr :5432

# Restart container
docker-compose restart postgres
```

### Issue: "ChromaDB connection refused"

```bash
# Check logs
docker logs chatbot_chromadb

# Verify port not in use
netstat -ano | findstr :8000

# Test HTTP endpoint
curl http://localhost:8000/api/v1/heartbeat
```

### Issue: "Invalid DSN format"

Ensure you're using `postgres_dsn` not `postgres_url`:

```python
# Correct (for psycopg2)
connection_string = settings.postgres_dsn

# Incorrect (for SQLAlchemy)
connection_string = settings.postgres_url
```

## API Reference

### ConversationStore Methods

- `generate_session_id(user_id)` - Generate unique session ID
- `store_message(...)` - Store conversation message
- `get_session_history(...)` - Retrieve session messages
- `get_user_history(...)` - Get all user messages
- `get_active_sessions(...)` - List active sessions
- `delete_session(...)` - Soft/hard delete session
- `get_conversation_stats(...)` - Get statistics

### MemoryRetriever Methods

- `add_conversation_to_index(...)` - Add messages to vector DB
- `semantic_search(...)` - Search similar conversations
- `get_relevant_context(...)` - Get formatted RAG context
- `delete_user_embeddings(...)` - Remove user embeddings
- `get_embedding_stats(...)` - Get vector DB stats
- `sync_session_to_index(...)` - Sync full session
- `sync_all_user_sessions(...)` - Bulk sync user sessions

## What's Next?

1. **✅ COMPLETED**: PostgreSQL + ChromaDB Docker setup
2. **✅ COMPLETED**: ConversationStore implementation
3. **✅ COMPLETED**: MemoryRetriever with semantic search
4. **✅ COMPLETED**: RBAC enforcement
5. **✅ COMPLETED**: Comprehensive integration tests

### Recommended Next Steps:

1. **Integrate into Chat API**: Add conversation storage to `/query` endpoint
2. **Session Management**: Add session continuity across requests
3. **Context Window**: Implement rolling context window for long conversations
4. **Performance Optimization**: Add background tasks for ChromaDB sync
5. **Monitoring Dashboard**: Build admin panel for conversation analytics

## License

This implementation is part of the Advance Chatbot Phase 3 development.

## Support

For issues or questions:
- Check troubleshooting section
- Review test results in `tests/test_postgres_chromadb.py`
- Verify configuration in `.env`
- Check Docker container logs
