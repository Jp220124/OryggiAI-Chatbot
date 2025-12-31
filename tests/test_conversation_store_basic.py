"""
Basic test for ConversationStore without ChromaDB dependency
Tests that conversation storage works even when RAG features are unavailable
"""

from app.memory import ConversationStore, ConversationManager, CHROMADB_AVAILABLE

def test_chromadb_availability():
    """Test ChromaDB availability status"""
    print(f"\nChromaDB Available: {CHROMADB_AVAILABLE}")
    print(f"Expected: False (not installed)")
    assert CHROMADB_AVAILABLE == False, "ChromaDB should not be available"
    print("[PASS] ChromaDB availability check")

def test_conversation_store_import():
    """Test ConversationStore can be imported"""
    print("\nTesting ConversationStore import...")
    store = ConversationStore()
    assert store is not None
    print("[PASS] ConversationStore imported successfully")

def test_conversation_manager_without_rag():
    """Test ConversationManager works without RAG"""
    print("\nTesting ConversationManager without RAG...")
    manager = ConversationManager()

    # Verify RAG is disabled
    assert manager.enable_rag == False, "RAG should be disabled"
    assert manager.memory_retriever is None, "MemoryRetriever should be None"
    assert manager.conversation_store is not None, "ConversationStore should be available"

    print(f"  RAG Enabled: {manager.enable_rag}")
    print(f"  MemoryRetriever: {manager.memory_retriever}")
    print(f"  ConversationStore: Available")
    print("[PASS] ConversationManager works without RAG")

def test_session_creation():
    """Test session creation works"""
    print("\nTesting session creation...")
    manager = ConversationManager()

    session_id = manager.start_session(user_id="test_user_001")
    assert session_id is not None
    assert len(session_id) > 0

    print(f"  Created session: {session_id}")
    print("[PASS] Session creation works")

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 3 Memory System - Basic Tests (Without ChromaDB)")
    print("=" * 60)

    try:
        test_chromadb_availability()
        test_conversation_store_import()
        test_conversation_manager_without_rag()
        test_session_creation()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        print("\nSummary:")
        print("- ConversationStore: Working independently")
        print("- ConversationManager: Working without RAG")
        print("- ChromaDB RAG features: Disabled (not installed)")
        print("\nTo enable RAG features, install:")
        print("  pip install chromadb")
        print("  Note: Requires Microsoft Visual C++ 14.0+ on Windows")

    except Exception as e:
        print(f"\n[FAIL] Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
