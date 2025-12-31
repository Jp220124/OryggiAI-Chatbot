"""
Test Conversation Context - Follow-up Questions
Tests if the chatbot remembers previous conversation and can answer follow-up questions
"""
import requests
import json
import sys
import os
import time

# Set UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    os.system('chcp 65001 > nul')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

API_URL = "http://localhost:9000/api/chat/query"

def test_conversation_context():
    """Test follow-up question with conversation context"""

    print("\n" + "="*100)
    print("CONVERSATION CONTEXT TEST")
    print("="*100)

    # Use admin user to avoid RBAC errors
    session_id = f"test_context_session_{int(time.time())}"
    user_id = "1"  # Numeric user ID to avoid RBAC SQL errors

    print(f"\nSession ID: {session_id}")
    print(f"User ID: {user_id}")

    # Query 1: Initial question
    print("\n" + "="*100)
    print("QUERY 1: Initial Question")
    print("="*100)

    question1 = "How many employees are in each department?"
    payload1 = {
        "question": question1,
        "user_id": user_id,
        "session_id": session_id
    }

    print(f"\nAsking: {question1}")
    response1 = requests.post(API_URL, json=payload1, timeout=30)

    if response1.status_code == 200:
        data1 = response1.json()
        sql1 = data1.get("sql_query", "")
        answer1 = data1.get("answer", "")

        print(f"\nSQL Generated: {sql1}")
        print(f"\nAnswer Preview: {answer1[:200]}...")

        # Wait a bit for message to be stored
        time.sleep(2)
    else:
        print(f"\n❌ Query 1 failed: {response1.status_code}")
        return

    # Query 2: Follow-up question using pronoun
    print("\n" + "="*100)
    print("QUERY 2: Follow-up Question (Testing Context)")
    print("="*100)

    question2 = "list all of them"  # Should reference departments from Query 1
    payload2 = {
        "question": question2,
        "user_id": user_id,
        "session_id": session_id  # Same session
    }

    print(f"\nAsking: {question2}")
    print(f"Expected: Should understand 'them' refers to departments from previous query")

    response2 = requests.post(API_URL, json=payload2, timeout=30)

    if response2.status_code == 200:
        data2 = response2.json()
        sql2 = data2.get("sql_query", "")
        answer2 = data2.get("answer", "")

        print(f"\nSQL Generated: {sql2}")
        print(f"\nAnswer Preview: {answer2[:200]}...")

        # Check if context was understood
        context_indicators = [
            "department" in sql2.lower(),
            "dname" in sql2.lower(),
            "vw_employeemaster" in sql2.lower()
        ]

        if any(context_indicators):
            print("\n✅ SUCCESS: Context was understood! Query references departments.")
        else:
            print("\n❌ FAIL: Context was NOT understood. Query doesn't reference departments.")
            print(f"   Generated SQL doesn't seem related to departments.")
    else:
        print(f"\n❌ Query 2 failed: {response2.status_code}")

    print("\n" + "="*100)

if __name__ == "__main__":
    try:
        # Test server health
        health = requests.get("http://localhost:9000/health", timeout=5)
        if health.status_code == 200:
            print("✅ Server is healthy\n")
            test_conversation_context()
        else:
            print("❌ Server health check failed")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
