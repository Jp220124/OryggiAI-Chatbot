# ChromaDB with Docker Setup Guide

## Overview

This guide shows how to use ChromaDB in Docker instead of installing it locally, which eliminates the need for Microsoft Visual C++ Build Tools.

## Prerequisites

- ✅ Docker Desktop installed (version 28.3.0 detected)
- ❌ Docker Desktop must be **running**

## Setup Steps

### Step 1: Start Docker Desktop

1. Open **Docker Desktop** application
2. Wait for it to fully start (whale icon in system tray should be stable)
3. Verify Docker is running:
   ```bash
   docker --version
   docker ps
   ```

### Step 2: Start ChromaDB Server

```bash
cd Advance_Chatbot
docker-compose -f docker-compose-chromadb.yml up -d
```

This will:
- Download ChromaDB Docker image (if not cached)
- Start ChromaDB server on `http://localhost:8000`
- Create persistent storage volume `chromadb_data`

**Verify ChromaDB is running**:
```bash
docker ps | findstr chromadb
```

You should see:
```
chromadb_server   chromadb/chroma:latest   0.0.0.0:8000->8000/tcp
```

**Test ChromaDB endpoint**:
```bash
curl http://localhost:8000/api/v1/heartbeat
```

### Step 3: Install ChromaDB Python Client (Lightweight)

Install only the HTTP client (no C++ compiler needed):

```bash
cd Advance_Chatbot
venv\Scripts\pip.exe install chromadb-client
```

OR update requirements.txt:
```txt
# Replace this line:
chromadb==0.4.22

# With this:
chromadb-client==0.4.22
```

Then install:
```bash
venv\Scripts\pip.exe install -r requirements.txt
```

### Step 4: Configuration Already Set

The code has been updated to automatically use HTTP mode based on `.env` configuration:

#### `.env` Configuration (Already Added)

```bash
# ====================
# ChromaDB Configuration (Phase 3 - RAG Memory)
# ====================
# Connection Mode: 'http' (Docker) or 'embedded' (local)
CHROMADB_MODE=http
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# Only used when CHROMADB_MODE=embedded
CHROMADB_PERSIST_DIRECTORY=./chroma_db

# Collection name for conversation memory
CHROMADB_COLLECTION_NAME=conversation_memory
```

#### `app/memory/memory_retriever.py` (Already Updated)

The code now automatically detects the connection mode from `.env`:

```python
# Determine ChromaDB mode from environment if not specified
if chroma_mode is None:
    chroma_mode = os.getenv("CHROMADB_MODE", "http").lower()

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
    self.chroma_client = chromadb.PersistentClient(
        path=chroma_persist_directory,
        settings=Settings(anonymized_telemetry=False)
    )
    print(f"[MemoryRetriever] Using ChromaDB embedded mode at {chroma_persist_directory}")
```

**Key Features**:
- ✅ Automatic mode detection from environment variables
- ✅ Support for both HTTP (Docker) and embedded modes
- ✅ No code changes needed - just update `.env`
- ✅ Clear logging of connection mode

### Step 5: Test Docker Connection (When Docker is Running)

After Docker Desktop and ChromaDB container are started, test the connection:

```bash
cd Advance_Chatbot
venv\Scripts\python.exe tests\test_chromadb_docker.py
```

This test will:
1. Check ChromaDB availability
2. Test HTTP connection to Docker server
3. Test collection operations
4. Verify MemoryRetriever can connect in HTTP mode

## Docker Commands Reference

### Start ChromaDB
```bash
cd Advance_Chatbot
docker-compose -f docker-compose-chromadb.yml up -d
```

### Stop ChromaDB
```bash
docker-compose -f docker-compose-chromadb.yml down
```

### View ChromaDB Logs
```bash
docker logs chromadb_server
docker logs -f chromadb_server  # Follow logs
```

### Restart ChromaDB
```bash
docker-compose -f docker-compose-chromadb.yml restart
```

### Remove ChromaDB (including data)
```bash
docker-compose -f docker-compose-chromadb.yml down -v
```

### Check ChromaDB Status
```bash
docker ps | findstr chromadb
curl http://localhost:8000/api/v1/heartbeat
```

## Testing the Setup

### Test 1: Docker Connection

```bash
cd Advance_Chatbot
venv\Scripts\python.exe -c "import chromadb; client = chromadb.HttpClient(host='localhost', port=8000); print('Connected to ChromaDB:', client.heartbeat())"
```

### Test 2: Basic Operations

```python
import chromadb

# Connect to Docker server
client = chromadb.HttpClient(host='localhost', port=8000)

# Create collection
collection = client.get_or_create_collection("test_collection")

# Add test document
collection.add(
    documents=["This is a test"],
    ids=["test_1"]
)

# Query
results = collection.query(query_texts=["test"], n_results=1)
print("Query results:", results)
```

### Test 3: Run Memory System Tests

```bash
cd Advance_Chatbot
venv\Scripts\python.exe -m pytest tests/test_conversation_store_basic.py -v
```

## Advantages of Docker Approach

1. **No C++ Compiler Required**: Eliminates Visual C++ dependency
2. **Easy Deployment**: Same Docker image works everywhere
3. **Persistent Storage**: Data survives container restarts
4. **Easy Scaling**: Can run ChromaDB on separate server
5. **Version Control**: Lock ChromaDB version with Docker image
6. **Clean Separation**: ChromaDB isolated from Python app
7. **Production Ready**: Docker is standard for deployment

## Troubleshooting

### Docker Desktop Not Running
```
Error: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
```
**Solution**: Start Docker Desktop application

### Port 8000 Already in Use
```bash
# Check what's using port 8000
netstat -ano | findstr :8000

# Use different port in docker-compose-chromadb.yml
ports:
  - "8001:8000"  # Map to 8001 instead
```

### Cannot Connect to ChromaDB
```bash
# Check if container is running
docker ps

# Check logs
docker logs chromadb_server

# Restart container
docker-compose -f docker-compose-chromadb.yml restart
```

### Data Persistence Issues
```bash
# Check volume exists
docker volume ls | findstr chromadb

# Inspect volume
docker volume inspect advance_chatbot_chromadb_data
```

## Architecture Diagram

```
┌─────────────────────────────────────┐
│   FastAPI Application               │
│   (Python 3.12)                     │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  ConversationManager        │  │
│   │  (app/memory/)              │  │
│   └──────────┬──────────────────┘  │
│              │                      │
│   ┌──────────▼──────────┐          │
│   │  ChromaDB Client    │          │
│   │  (HTTP Mode)        │          │
│   └──────────┬──────────┘          │
└──────────────┼──────────────────────┘
               │ HTTP (localhost:8000)
               │
┌──────────────▼──────────────────────┐
│   Docker Container                  │
│   ┌─────────────────────────────┐  │
│   │  ChromaDB Server            │  │
│   │  (chromadb/chroma:latest)   │  │
│   └─────────────┬───────────────┘  │
│                 │                   │
│   ┌─────────────▼───────────────┐  │
│   │  Persistent Volume          │  │
│   │  (chromadb_data)            │  │
│   └─────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Next Steps

### Completed

1. ✅ Docker Compose file created (`docker-compose-chromadb.yml`)
2. ✅ `.env` configuration added with ChromaDB settings
3. ✅ `memory_retriever.py` updated to support HTTP mode
4. ✅ Code auto-detects connection mode from environment
5. ✅ Test script created (`tests/test_chromadb_docker.py`)
6. ✅ Documentation created (this file)

### To Do (Manual Steps)

1. ⏳ Start Docker Desktop (manual - user action required)
2. ⏳ Start ChromaDB container:
   ```bash
   cd Advance_Chatbot
   docker-compose -f docker-compose-chromadb.yml up -d
   ```
3. ⏳ Install ChromaDB client (optional, for HTTP mode testing):
   ```bash
   cd Advance_Chatbot
   venv\Scripts\pip.exe install chromadb-client
   ```
4. ⏳ Run connection test:
   ```bash
   cd Advance_Chatbot
   venv\Scripts\python.exe tests\test_chromadb_docker.py
   ```
5. ⏳ Verify MemoryRetriever works with Docker
6. ⏳ Run full memory system integration tests

## Alternative: Use docker run (without docker-compose)

If you prefer not to use docker-compose:

```bash
docker run -d \
  --name chromadb_server \
  -p 8000:8000 \
  -v chromadb_data:/chroma/chroma \
  -e ANONYMIZED_TELEMETRY=False \
  -e ALLOW_RESET=True \
  chromadb/chroma:latest
```

## Production Considerations

For production deployment:

1. **Security**: Add authentication to ChromaDB
2. **Networking**: Use Docker networks or separate server
3. **Backups**: Regular backup of `chromadb_data` volume
4. **Monitoring**: Add health checks and metrics
5. **Scaling**: Consider ChromaDB distributed mode
6. **SSL/TLS**: Use HTTPS for production

## Summary

Using ChromaDB in Docker:
- ✅ **Solves**: C++ compiler dependency issue
- ✅ **Production Ready**: Docker is standard for deployment
- ✅ **Easy Management**: Start/stop/restart with simple commands
- ✅ **Portable**: Same setup works on any machine with Docker
- ✅ **Persistent**: Data survives container restarts

This approach is actually **better than local installation** for development and production!
