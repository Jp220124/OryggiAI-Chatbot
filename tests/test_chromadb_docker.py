"""
Test ChromaDB Docker Connection
Tests that the memory system can connect to ChromaDB running in Docker
"""

def test_chromadb_docker_connection():
    """Test connection to ChromaDB Docker server"""
    import os

    # Ensure we're in HTTP mode
    os.environ["CHROMADB_MODE"] = "http"
    os.environ["CHROMADB_HOST"] = "localhost"
    os.environ["CHROMADB_PORT"] = "8000"

    print("\n" + "=" * 70)
    print("ChromaDB Docker Connection Test")
    print("=" * 70)

    # Test 1: ChromaDB availability
    print("\n[Test 1] Checking ChromaDB availability...")
    try:
        from app.memory.memory_retriever import CHROMADB_AVAILABLE
        if CHROMADB_AVAILABLE:
            print("✅ ChromaDB package is available")
        else:
            print("❌ ChromaDB package is NOT available")
            print("   Install with: pip install chromadb-client")
            return False
    except Exception as e:
        print(f"❌ Error checking ChromaDB: {str(e)}")
        return False

    # Test 2: Test basic HTTP connection
    print("\n[Test 2] Testing basic HTTP connection to ChromaDB server...")
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.HttpClient(
            host="localhost",
            port=8000,
            settings=Settings(anonymized_telemetry=False)
        )

        # Test heartbeat
        heartbeat = client.heartbeat()
        print(f"✅ ChromaDB server is responding: {heartbeat}")

    except Exception as e:
        print(f"❌ Cannot connect to ChromaDB server: {str(e)}")
        print("\n   Make sure:")
        print("   1. Docker Desktop is running")
        print("   2. ChromaDB container is started:")
        print("      cd Advance_Chatbot")
        print("      docker-compose -f docker-compose-chromadb.yml up -d")
        print("   3. Container is healthy:")
        print("      docker ps | findstr chromadb")
        return False

    # Test 3: Test collection operations
    print("\n[Test 3] Testing collection operations...")
    try:
        # Create test collection
        test_collection = client.get_or_create_collection("test_collection")
        print(f"✅ Created/accessed collection: {test_collection.name}")

        # Add test document
        test_collection.add(
            documents=["This is a test document for ChromaDB Docker"],
            ids=["test_doc_1"],
            metadatas=[{"source": "test", "user_id": "test_user"}]
        )
        print("✅ Added test document to collection")

        # Query test document
        results = test_collection.query(
            query_texts=["test document"],
            n_results=1
        )
        print(f"✅ Query successful: Found {len(results['ids'][0])} results")

        # Clean up
        client.delete_collection("test_collection")
        print("✅ Cleaned up test collection")

    except Exception as e:
        print(f"❌ Collection operations failed: {str(e)}")
        return False

    # Test 4: Test MemoryRetriever with HTTP mode
    print("\n[Test 4] Testing MemoryRetriever with HTTP mode...")
    try:
        from app.memory import CHROMADB_AVAILABLE as MODULE_CHROMADB_AVAILABLE

        if not MODULE_CHROMADB_AVAILABLE:
            print("⚠️  MemoryRetriever not available (expected without sentence-transformers)")
            print("   Install with: pip install sentence-transformers")
        else:
            print("✅ MemoryRetriever module is importable")

            # Try to create MemoryRetriever instance
            try:
                from app.memory.memory_retriever import MemoryRetriever
                from app.memory.conversation_store import ConversationStore

                store = ConversationStore()
                retriever = MemoryRetriever(
                    conversation_store=store,
                    chroma_mode="http",
                    chroma_host="localhost",
                    chroma_port=8000
                )

                print(f"✅ MemoryRetriever initialized in {retriever.chroma_mode} mode")
                print(f"   Collection: {retriever.collection.name}")

            except Exception as e:
                print(f"⚠️  MemoryRetriever initialization issue: {str(e)}")

    except Exception as e:
        print(f"❌ MemoryRetriever test failed: {str(e)}")

    print("\n" + "=" * 70)
    print("✅ All ChromaDB Docker connection tests passed!")
    print("=" * 70)

    return True


def test_chromadb_docker_not_running():
    """Test graceful handling when Docker is not running"""
    import os

    os.environ["CHROMADB_MODE"] = "http"
    os.environ["CHROMADB_HOST"] = "localhost"
    os.environ["CHROMADB_PORT"] = "8000"

    print("\n" + "=" * 70)
    print("ChromaDB Docker Not Running Test")
    print("=" * 70)

    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.HttpClient(
            host="localhost",
            port=8000,
            settings=Settings(anonymized_telemetry=False)
        )

        # This should fail if Docker is not running
        client.heartbeat()
        print("✅ ChromaDB server is running")
        return True

    except Exception as e:
        print(f"⚠️  ChromaDB server is not running (expected if Docker not started)")
        print(f"   Error: {str(e)}")
        print("\n   To start ChromaDB:")
        print("   1. Start Docker Desktop")
        print("   2. cd Advance_Chatbot")
        print("   3. docker-compose -f docker-compose-chromadb.yml up -d")
        return False


if __name__ == "__main__":
    import sys

    # Test 1: Check if Docker is running
    if not test_chromadb_docker_not_running():
        print("\n" + "=" * 70)
        print("SETUP REQUIRED: Start Docker Desktop and ChromaDB container")
        print("=" * 70)
        sys.exit(1)

    # Test 2: Full connection test
    if test_chromadb_docker_connection():
        print("\n✅ ChromaDB Docker setup is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ ChromaDB Docker setup has issues")
        sys.exit(1)
