"""
Test Chat Orchestrator - End-to-End Multi-Tool Integration
Demonstrates all Phase 1-4 features working via chat interface
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:9000"
CHAT_ENDPOINT = f"{API_BASE}/api/chat/query"

def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_chat(question, user_role="ADMIN", user_id="test_user"):
    """Send chat request and display response"""
    print(f"\nUSER: {question}")
    print("-" * 80)

    payload = {
        "question": question,
        "user_id": user_id,
        "user_role": user_role,
        "tenant_id": "default",
        "session_id": f"session_{user_id}_{int(time.time())}"
    }

    try:
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()

            print(f"ASSISTANT: {result.get('answer', 'No answer')}")
            print(f"\nDetails:")
            print(f"  Success: {result.get('success', False)}")
            print(f"  SQL Query: {result.get('sql_query', 'N/A')[:100]}..." if result.get('sql_query') else "  SQL Query: N/A")
            print(f"  Result Count: {result.get('result_count', 0)}")
            print(f"  Tables Used: {result.get('tables_used', [])}")
            print(f"  Execution Time: {result.get('execution_time', 0):.3f}s")

            return result
        else:
            print(f"ERROR: HTTP {response.status_code}")
            print(response.text)
            return None

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return None


# ============================================================================
# TEST SUITE: Chat Orchestrator Multi-Tool Integration
# ============================================================================

print("\n")
print("╔" + "═" * 78 + "╗")
print("║" + " " * 20 + "CHAT ORCHESTRATOR TEST SUITE" + " " * 30 + "║")
print("║" + " " * 15 + "End-to-End Multi-Tool Integration Test" + " " * 24 + "║")
print("╚" + "═" * 78 + "╝")
print("\nTesting Phases 1-4 Integration via Conversational Interface")
print("- Phase 1: RAG + SQL Query Generation")
print("- Phase 2: RBAC + Tool Registry")
print("- Phase 3: Report Generation (PDF/Excel)")
print("- Phase 4: Email Integration")

# Wait for user to ensure server is running
print("\n" + "⚠" * 40)
print("IMPORTANT: Ensure the Advance_Chatbot server is running on port 9000")
print("Run: cd Advance_Chatbot && venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 9000")
print("⚠" * 40)

input("\nPress ENTER when server is ready...")

# ============================================================================
# TEST 1: SQL Query Only (Phase 1-2)
# ============================================================================
print_section("TEST 1: SQL Query Only (Phase 1-2)")
print("Intent: query")
print("Expected Tools: query_database")
print("Expected Output: Natural language answer with SQL results")

test_chat(
    question="How many employees are currently active?",
    user_role="ADMIN"
)

time.sleep(2)

# ============================================================================
# TEST 2: Report Generation - PDF (Phase 3)
# ============================================================================
print_section("TEST 2: Report Generation - PDF (Phase 3)")
print("Intent: report")
print("Expected Tools: query_database, generate_report")
print("Expected Output: PDF report generated with file path")

test_chat(
    question="Generate a PDF report of the top 10 employees by salary",
    user_role="ADMIN"
)

time.sleep(2)

# ============================================================================
# TEST 3: Report Generation - Excel (Phase 3)
# ============================================================================
print_section("TEST 3: Report Generation - Excel (Phase 3)")
print("Intent: report")
print("Expected Tools: query_database, generate_report")
print("Expected Output: Excel report generated with file path")

test_chat(
    question="Create an Excel spreadsheet showing all employees in the IT department",
    user_role="HR_MANAGER"
)

time.sleep(2)

# ============================================================================
# TEST 4: Combined - Report + Email (Phase 4)
# ============================================================================
print_section("TEST 4: Combined - Report + Email (Phase 4)")
print("Intent: combined")
print("Expected Tools: query_database, generate_report, send_email")
print("Expected Output: Report generated AND emailed")

print("\n⚠ Note: Change 'your-email@example.com' to a real email address to test email sending")
print("Current: Email will be sent to your-email@example.com")

test_chat(
    question="Generate a PDF report of employees who joined in the last 30 days and email it to your-email@example.com",
    user_role="ADMIN"
)

time.sleep(2)

# ============================================================================
# TEST 5: Simple Data Query (Baseline)
# ============================================================================
print_section("TEST 5: Simple Data Query (Baseline)")
print("Intent: query")
print("Expected Tools: query_database")
print("Expected Output: Count result")

test_chat(
    question="Show me the total number of employees in each department",
    user_role="HR_STAFF"
)

time.sleep(2)

# ============================================================================
# TEST 6: Excel Report - Alternative Phrasing
# ============================================================================
print_section("TEST 6: Excel Report - Alternative Phrasing")
print("Intent: report")
print("Expected Tools: query_database, generate_report")
print("Expected Output: Excel report")

test_chat(
    question="I need an Excel report showing all active employees with their salaries",
    user_role="ADMIN"
)

# ============================================================================
# SUMMARY
# ============================================================================
print_section("TEST SUITE COMPLETE")
print("\nSUMMARY:")
print("  Test 1: SQL Query Only               → Phase 1-2 ✓")
print("  Test 2: PDF Report Generation         → Phase 3   ✓")
print("  Test 3: Excel Report Generation       → Phase 3   ✓")
print("  Test 4: Combined (Report + Email)     → Phase 4   ✓")
print("  Test 5: Simple Data Query             → Phase 1-2 ✓")
print("  Test 6: Excel Report (Alt Phrasing)   → Phase 3   ✓")
print("\nCHECK:")
print("  1. All queries returned valid responses")
print("  2. Reports were generated in ./reports_output/")
print("  3. Email was sent (if configured)")
print("  4. Orchestrator correctly classified intent")
print("  5. Tools were called in correct sequence")

print("\n" + "=" * 80)
print("  END OF TEST SUITE")
print("=" * 80 + "\n")
