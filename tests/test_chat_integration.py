"""
Test Chat API Integration with Phase 3 Memory System
Tests conversation storage, session continuity, and background sync
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.memory.conversation_store import conversation_store
from app.memory.memory_retriever import memory_retriever
import time


def test_chat_api_integration():
    """
    Test the full integration:
    1. Session ID generation
    2. Conversation storage
    3. Session continuity
    4. ChromaDB sync
    """
    print("\n" + "="*60)
    print("TEST: Chat API Integration with Phase 3 Memory")
    print("="*60)

    user_id = "test_integration_user"
    user_role = "ADMIN"

    # Step 1: Generate session ID
    print("\n[STEP 1] Testing session ID generation...")
    session_id = conversation_store.generate_session_id(user_id)
    print(f"  Generated session_id: {session_id}")
    assert session_id.startswith(f"session_{user_id}_")
    print("  [OK] Session ID format correct")

    # Step 2: Store user question
    print("\n[STEP 2] Testing user message storage...")
    user_question = "How many employees do we have?"
    user_msg_id = conversation_store.store_message(
        session_id=session_id,
        user_id=user_id,
        user_role=user_role,
        message_type="user",
        message_content=user_question
    )
    print(f"  Stored user message (ID: {user_msg_id})")
    print("  [OK] User message stored")

    # Step 3: Store assistant response
    print("\n[STEP 3] Testing assistant message storage...")
    assistant_answer = "Based on the SQL query, there are 150 employees."
    assistant_msg_id = conversation_store.store_message(
        session_id=session_id,
        user_id=user_id,
        user_role=user_role,
        message_type="assistant",
        message_content=assistant_answer,
        tools_used=["sql_tool"],
        data_returned={
            "sql_query": "SELECT COUNT(*) FROM Employees",
            "result_count": 1,
            "natural_answer": assistant_answer
        },
        success_flag=True
    )
    print(f"  Stored assistant message (ID: {assistant_msg_id})")
    print("  [OK] Assistant message stored")

    # Step 4: Retrieve session history
    print("\n[STEP 4] Testing session history retrieval...")
    history = conversation_store.get_session_history(
        session_id=session_id,
        user_id=user_id,
        limit=10
    )
    print(f"  Retrieved {len(history)} messages")

    if len(history) >= 2:
        print("  Messages in session:")
        for i, msg in enumerate(history, 1):
            print(f"    {i}. [{msg['message_type']}] {msg['message_content'][:40]}...")
        print("  [OK] Session history retrieved correctly")
    else:
        print("  [FAIL] Expected at least 2 messages")
        return False

    # Step 5: Test session continuity (add second exchange)
    print("\n[STEP 5] Testing session continuity...")

    # Use same session_id for second question
    user_question_2 = "Show me their departments"
    user_msg_id_2 = conversation_store.store_message(
        session_id=session_id,  # Same session
        user_id=user_id,
        user_role=user_role,
        message_type="user",
        message_content=user_question_2
    )

    assistant_answer_2 = "Here are the departments: Engineering (45), HR (12), Sales (30), Marketing (20), Operations (43)."
    assistant_msg_id_2 = conversation_store.store_message(
        session_id=session_id,  # Same session
        user_id=user_id,
        user_role=user_role,
        message_type="assistant",
        message_content=assistant_answer_2,
        tools_used=["sql_tool"],
        success_flag=True
    )

    # Verify continuity
    updated_history = conversation_store.get_session_history(
        session_id=session_id,
        user_id=user_id,
        limit=10
    )

    if len(updated_history) >= 4:  # 2 exchanges = 4 messages
        print(f"  Session now has {len(updated_history)} messages (continuity maintained)")
        print("  [OK] Session continuity works")
    else:
        print(f"  [FAIL] Expected at least 4 messages, got {len(updated_history)}")
        return False

    # Step 6: Test ChromaDB sync
    print("\n[STEP 6] Testing ChromaDB sync...")
    try:
        doc_ids = memory_retriever.add_conversation_to_index(
            session_id=session_id,
            user_id=user_id,
            conversation_messages=updated_history
        )
        print(f"  Created {len(doc_ids)} embeddings in ChromaDB")
        print("  [OK] ChromaDB sync successful")
    except Exception as e:
        print(f"  [FAIL] ChromaDB sync failed: {str(e)}")
        return False

    # Step 7: Test semantic search
    print("\n[STEP 7] Testing semantic search...")
    try:
        results = memory_retriever.semantic_search(
            query="How many employees are there?",
            user_id=user_id,
            n_results=2
        )

        if results:
            print(f"  Found {len(results)} relevant conversations:")
            for i, result in enumerate(results, 1):
                similarity = result.get('similarity_score', 0)
                content = result['document'][:50]
                print(f"    {i}. [Score: {similarity:.3f}] {content}...")
            print("  [OK] Semantic search works")
        else:
            print("  [WARN] No results from semantic search (may need time to index)")
    except Exception as e:
        print(f"  [FAIL] Semantic search failed: {str(e)}")
        return False

    # Step 8: Test RBAC (different user should not see messages)
    print("\n[STEP 8] Testing RBAC enforcement...")
    other_user_history = conversation_store.get_session_history(
        session_id=session_id,
        user_id="other_user",  # Different user
        limit=10
    )

    if len(other_user_history) == 0:
        print("  Other user cannot access this session's messages")
        print("  [OK] RBAC enforcement works")
    else:
        print(f"  [FAIL] Other user can see {len(other_user_history)} messages (RBAC breach!)")
        return False

    # Step 9: Get conversation stats
    print("\n[STEP 9] Testing conversation statistics...")
    stats = conversation_store.get_conversation_stats(
        user_id=user_id,
        days_back=7
    )

    print(f"  User Statistics:")
    print(f"    - Total Messages: {stats['total_messages']}")
    print(f"    - Total Sessions: {stats['total_sessions']}")
    print(f"    - User Messages: {stats['user_messages']}")
    print(f"    - Assistant Messages: {stats['assistant_messages']}")
    print("  [OK] Statistics retrieved")

    print("\n" + "="*60)
    print("[SUCCESS] All integration tests passed!")
    print("="*60)
    return True


if __name__ == "__main__":
    try:
        success = test_chat_api_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
