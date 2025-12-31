"""
Comprehensive Test for PostgreSQL + ChromaDB Integration
Tests conversation storage, retrieval, and RAG functionality
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.memory.conversation_store import ConversationStore
from app.memory.memory_retriever import MemoryRetriever
import psycopg2
from datetime import datetime


def test_postgres_connection():
    """Test PostgreSQL connection and database schema"""
    print("\n" + "="*60)
    print("TEST 1: PostgreSQL Connection")
    print("="*60)

    try:
        # Test connection using settings
        from app.config import settings

        conn = psycopg2.connect(settings.postgres_dsn)
        cursor = conn.cursor()

        # Check if ConversationHistory table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'conversationhistory'
            )
        """)

        table_exists = cursor.fetchone()[0]

        if table_exists:
            print("[OK] PostgreSQL connection successful")
            print(f"[OK] ConversationHistory table exists")

            # Check table structure
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'conversationhistory'
                ORDER BY ordinal_position
            """)

            columns = cursor.fetchall()
            print(f"\n[STATS] Table Structure ({len(columns)} columns):")
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")

            # Check welcome message
            cursor.execute("""
                SELECT COUNT(*) FROM ConversationHistory
                WHERE user_id = 'system'
            """)
            system_messages = cursor.fetchone()[0]
            print(f"\n[OK] System initialization messages: {system_messages}")
        else:
            print("[FAIL] ConversationHistory table not found!")
            return False

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"[FAIL] PostgreSQL connection failed: {str(e)}")
        return False


def test_conversation_store():
    """Test ConversationStore operations"""
    print("\n" + "="*60)
    print("TEST 2: ConversationStore Operations")
    print("="*60)

    try:
        store = ConversationStore()

        # Generate session ID
        session_id = store.generate_session_id("test_user_001")
        print(f"[OK] Generated session ID: {session_id}")

        # Store user message
        user_msg_id = store.store_message(
            session_id=session_id,
            user_id="test_user_001",
            user_role="ADMIN",
            message_type="user",
            message_content="What is the total employee count?"
        )
        print(f"[OK] Stored user message (ID: {user_msg_id})")

        # Store assistant message with tools
        assistant_msg_id = store.store_message(
            session_id=session_id,
            user_id="test_user_001",
            user_role="ADMIN",
            message_type="assistant",
            message_content="Based on the SQL query, the total employee count is 150.",
            tools_used=["sql_tool"],
            data_returned={"query": "SELECT COUNT(*) FROM Employees", "result": 150},
            success_flag=True
        )
        print(f"[OK] Stored assistant message (ID: {assistant_msg_id})")

        # Retrieve session history
        history = store.get_session_history(
            session_id=session_id,
            user_id="test_user_001",
            limit=10
        )
        print(f"\n[OK] Retrieved {len(history)} messages from session")

        for msg in history:
            print(f"  - [{msg['message_type']}] {msg['message_content'][:50]}...")

        # Get conversation stats
        stats = store.get_conversation_stats(user_id="test_user_001", days_back=7)
        print(f"\n[STATS] Conversation Statistics:")
        print(f"  - Total Messages: {stats['total_messages']}")
        print(f"  - Total Sessions: {stats['total_sessions']}")
        print(f"  - User Messages: {stats['user_messages']}")
        print(f"  - Assistant Messages: {stats['assistant_messages']}")

        # Test RBAC (different user should not see these messages)
        other_user_history = store.get_session_history(
            session_id=session_id,
            user_id="other_user",  # Different user
            limit=10
        )
        print(f"\n[RBAC] RBAC Test: Other user retrieved {len(other_user_history)} messages (should be 0)")

        if len(other_user_history) == 0:
            print("[OK] RBAC enforcement working correctly")
        else:
            print("[FAIL] RBAC enforcement failed!")
            return False

        return True

    except Exception as e:
        print(f"[FAIL] ConversationStore test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_chromadb_connection():
    """Test ChromaDB connection"""
    print("\n" + "="*60)
    print("TEST 3: ChromaDB Connection")
    print("="*60)

    try:
        import chromadb
        from app.config import settings

        # Create HTTP client
        client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port
        )

        # Test connection by listing collections
        collections = client.list_collections()
        print(f"[OK] ChromaDB connection successful")
        print(f"[OK] Existing collections: {len(collections)}")

        for coll in collections:
            print(f"  - {coll.name}")

        return True

    except Exception as e:
        print(f"[FAIL] ChromaDB connection failed: {str(e)}")
        return False


def test_rag_functionality():
    """Test RAG (Retrieval-Augmented Generation) functionality"""
    print("\n" + "="*60)
    print("TEST 4: RAG Functionality")
    print("="*60)

    try:
        retriever = MemoryRetriever()
        store = ConversationStore()

        # Generate session ID
        session_id = store.generate_session_id("rag_test_user")

        # Store conversation about employees
        test_messages = [
            ("user", "How many employees do we have in the Engineering department?"),
            ("assistant", "Based on the SQL query results, there are 45 employees in the Engineering department."),
            ("user", "What about the HR department?"),
            ("assistant", "The HR department has 12 employees."),
            ("user", "Show me the salary report for Engineering department"),
            ("assistant", "I've generated the salary report showing average salary of $85,000 for Engineering department."),
        ]

        print("[NOTE] Storing test conversation...")
        for msg_type, content in test_messages:
            store.store_message(
                session_id=session_id,
                user_id="rag_test_user",
                user_role="ADMIN",
                message_type=msg_type,
                message_content=content,
                tools_used=["sql_tool"] if msg_type == "assistant" else None
            )

        print(f"[OK] Stored {len(test_messages)} messages")

        # Store in ChromaDB for RAG
        print("\n[SYNC] Syncing to ChromaDB...")
        history = store.get_session_history(
            session_id=session_id,
            user_id="rag_test_user",
            limit=100
        )

        # Add all messages to ChromaDB index at once
        doc_ids = retriever.add_conversation_to_index(
            session_id=session_id,
            user_id="rag_test_user",
            conversation_messages=history
        )

        print(f"[OK] Synced {len(history)} messages to ChromaDB ({len(doc_ids)} embeddings created)")

        # Test semantic search
        print("\n[SEARCH] Testing Semantic Search...")

        test_queries = [
            "How many people work in Engineering?",
            "What was the salary information?",
            "Tell me about HR department"
        ]

        for query in test_queries:
            print(f"\n  Query: '{query}'")
            results = retriever.semantic_search(
                query=query,
                user_id="rag_test_user",
                n_results=2
            )

            print(f"  Found {len(results)} relevant conversations:")
            for i, result in enumerate(results, 1):
                similarity = result.get('similarity_score', 0)
                content = result['document'][:60]
                print(f"    {i}. [{similarity:.3f}] {content}...")

        # Test RBAC in RAG (different user should not see these conversations)
        print("\n[RBAC] Testing RAG RBAC...")
        other_user_results = retriever.semantic_search(
            query="Engineering department",
            user_id="other_user",  # Different user
            n_results=5
        )
        print(f"  Other user found {len(other_user_results)} results (should be 0)")

        if len(other_user_results) == 0:
            print("[OK] RAG RBAC enforcement working correctly")
        else:
            print("[FAIL] RAG RBAC enforcement failed!")
            return False

        return True

    except Exception as e:
        print(f"[FAIL] RAG functionality test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "="*60)
    print("PostgreSQL + ChromaDB Integration Tests")
    print("Phase 3: Conversational Memory System")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        "PostgreSQL Connection": test_postgres_connection(),
        "ConversationStore Operations": test_conversation_store(),
        "ChromaDB Connection": test_chromadb_connection(),
        "RAG Functionality": test_rag_functionality()
    }

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "-"*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)

    if passed == total:
        print("[SUCCESS] All tests passed! System is working correctly.")
        return True
    else:
        print("[WARNING] Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
