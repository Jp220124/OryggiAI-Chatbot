"""
Test Script to Verify VIEW-FIRST Architecture Fixes
Tests all previously failing queries to ensure they now work correctly
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    os.system('chcp 65001 > nul')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from app.agents.sql_agent import RAGSQLAgent
from app.database import init_database
from app.rag.chroma_manager import chroma_manager

def print_separator():
    print("\n" + "=" * 100 + "\n")

def test_query(sql_agent: RAGSQLAgent, question: str, test_number: int):
    """Test a single query and display results"""
    print(f"TEST {test_number}: {question}")
    print("-" * 100)

    try:
        # Generate SQL using the agent
        result = sql_agent.generate_sql(question)

        print(f"✓ Generated SQL:\n{result['sql_query']}\n")

        # Check if using views
        sql_lower = result['sql_query'].lower()
        uses_view = 'vw_' in sql_lower or 'view_' in sql_lower

        if uses_view:
            print("✅ USES VIEW (Correct!)")
            # Extract view name
            for view in ['vw_employeemaster_vms', 'vw_rawpunchdetail', 'allemployeeunion',
                         'view_visitor_enrollmentdetail', 'view_contractor_detail',
                         'view_employee_terminal_authentication_relation', 'vw_terminaldetail_vms']:
                if view in sql_lower:
                    print(f"   View used: {view}")
                    break
        else:
            print("⚠️ NOT USING VIEW (Check if this is expected)")

        # Check for deprecated tables
        if 'empdepartrole' in sql_lower:
            print("❌ CRITICAL ERROR: Using deprecated EmpDepartRole table!")

        # Execute and show results
        if result.get('result'):
            result_count = len(result['result']) if isinstance(result['result'], list) else 1
            print(f"\n✓ Query executed successfully!")
            print(f"✓ Result count: {result_count} rows")

            # Show first few results
            if isinstance(result['result'], list) and result['result']:
                print(f"\nFirst 5 results:")
                for i, row in enumerate(result['result'][:5], 1):
                    print(f"  {i}. {row}")

            return "PASS", uses_view, result_count
        else:
            print(f"\n✗ Query returned no results")
            return "FAIL", uses_view, 0

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        logger.error(f"Query test failed: {e}")
        return "ERROR", False, 0

def main():
    """Run all test queries"""
    print_separator()
    print("VIEW-FIRST ARCHITECTURE FIX VERIFICATION TEST")
    print("Testing all previously failing queries...")
    print_separator()

    # Initialize database and ChromaDB
    logger.info("Initializing database and RAG...")
    init_database()
    chroma_manager.initialize()

    # Initialize SQL agent
    sql_agent = RAGSQLAgent()

    # Define test queries (from user's failure examples)
    test_queries = [
        "How many employees are in each department?",
        "Show me the top 5 departments with the most employees",
        "which Employee have the highest logs",
        "List all employees in IT department",
        "Show attendance records for today",
        "How many total active employees?",
        "Which devices are online?"  # This one was working before
    ]

    # Run tests
    results = []
    for i, question in enumerate(test_queries, 1):
        status, uses_view, count = test_query(sql_agent, question, i)
        results.append({
            "question": question,
            "status": status,
            "uses_view": uses_view,
            "result_count": count
        })
        print_separator()

    # Summary
    print("TEST SUMMARY")
    print("=" * 100)
    print(f"{'#':<5} {'Status':<10} {'View?':<10} {'Rows':<10} {'Question'}")
    print("-" * 100)

    passed = 0
    failed = 0
    errors = 0
    view_usage = 0

    for i, r in enumerate(results, 1):
        status_icon = "✅" if r['status'] == "PASS" else ("❌" if r['status'] == "FAIL" else "⚠️")
        view_icon = "✅" if r['uses_view'] else "❌"

        print(f"{i:<5} {status_icon} {r['status']:<7} {view_icon} {str(r['uses_view']):<7} {r['result_count']:<10} {r['question']}")

        if r['status'] == "PASS":
            passed += 1
        elif r['status'] == "FAIL":
            failed += 1
        else:
            errors += 1

        if r['uses_view']:
            view_usage += 1

    print("=" * 100)
    print(f"\nTEST RESULTS:")
    print(f"  ✅ PASSED: {passed}/{len(test_queries)}")
    print(f"  ❌ FAILED: {failed}/{len(test_queries)}")
    print(f"  ⚠️  ERRORS: {errors}/{len(test_queries)}")
    print(f"  📊 View Usage: {view_usage}/{len(test_queries)} ({view_usage/len(test_queries)*100:.1f}%)")

    if passed == len(test_queries):
        print("\n🎉 ALL TESTS PASSED! VIEW-FIRST architecture is working correctly!")
    elif passed > failed:
        print(f"\n✓ Most tests passed ({passed}/{len(test_queries)}). Review failures above.")
    else:
        print(f"\n⚠️ Multiple failures detected ({failed}/{len(test_queries)}). Further investigation needed.")

    print_separator()

if __name__ == "__main__":
    main()
