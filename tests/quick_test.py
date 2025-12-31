"""
Quick 10-test subset to estimate success rate
Tests covering all major SQL patterns
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

import time
from loguru import logger
from app.database import init_database
from app.rag import faiss_manager, few_shot_manager
from app.agents.sql_agent import sql_agent

# Configure simple logging
logger.remove()
logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")

# 10 representative test cases
TEST_CASES = [
    {
        "id": "test_001",
        "question": "How many total employees are there?",
        "expected_pattern": "COUNT",
        "category": "simple_count"
    },
    {
        "id": "test_003",
        "question": "How many employees joined in the last 30 days?",
        "expected_pattern": "DATEADD",
        "category": "date_operations"
    },
    {
        "id": "test_006",
        "question": "List all employees with their department names",
        "expected_pattern": "JOIN",
        "category": "simple_join"
    },
    {
        "id": "test_010",
        "question": "Show employee count by department",
        "expected_pattern": "GROUP BY",
        "category": "groupby_count"
    },
    {
        "id": "test_016",
        "question": "What is the average salary across all employees?",
        "expected_pattern": "AVG",
        "category": "aggregations"
    },
    {
        "id": "test_020",
        "question": "Which employees are in IT department?",
        "expected_pattern": "WHERE",
        "category": "filtering"
    },
    {
        "id": "test_024",
        "question": "Find employees whose names start with 'A'",
        "expected_pattern": "LIKE",
        "category": "like_pattern"
    },
    {
        "id": "test_030",
        "question": "Get the highest salary in IT department",
        "expected_pattern": "MAX",
        "category": "min_max"
    },
    {
        "id": "test_040",
        "question": "List employees sorted by hire date descending",
        "expected_pattern": "ORDER BY",
        "category": "sorting"
    },
    {
        "id": "test_045",
        "question": "Find distinct department names",
        "expected_pattern": "DISTINCT",
        "category": "distinct"
    }
]

def run_tests():
    """Run 10 quick tests"""
    print("=" * 80)
    print("QUICK TEST SUITE - 10 Representative Tests")
    print("=" * 80)

    # Initialize
    print("\nInitializing services...")
    init_database()
    faiss_manager.initialize()
    few_shot_manager.initialize()
    print("[OK] Services initialized\n")

    passed = 0
    failed = 0
    results = []

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/10: {test['id']} - {test['category']}")
        print(f"{'=' * 80}")
        print(f"Question: {test['question']}")
        print(f"Expected: {test['expected_pattern']}")

        try:
            # Generate SQL
            result = sql_agent.generate_sql(test['question'])
            sql_query = result["sql_query"]

            # Check pattern
            pattern_found = test['expected_pattern'].upper() in sql_query.upper()

            if pattern_found:
                print(f"[PASS] Pattern '{test['expected_pattern']}' found")
                passed += 1
                results.append({**test, "status": "PASS", "sql": sql_query})
            else:
                print(f"[FAIL] Pattern '{test['expected_pattern']}' NOT found")
                print(f"Generated SQL: {sql_query}")
                failed += 1
                results.append({**test, "status": "FAIL", "sql": sql_query})

            # Wait to avoid rate limit (30 seconds between requests = 2/minute)
            if i < len(TEST_CASES):
                print("\nWaiting 30s for rate limit...")
                time.sleep(30)

        except Exception as e:
            print(f"[ERROR] {str(e)}")
            failed += 1
            results.append({**test, "status": "ERROR", "error": str(e)})

    # Summary
    print(f"\n{'=' * 80}")
    print("QUICK TEST RESULTS")
    print(f"{'=' * 80}")
    print(f"Total Tests:  10")
    print(f"Passed:       {passed} ({passed*10}%)")
    print(f"Failed:       {failed} ({failed*10}%)")
    print(f"\nEstimated success rate: {passed*10}%")

    if passed >= 9:
        print("\n[SUCCESS] Excellent! Likely exceeds 90% target")
    elif passed >= 7:
        print("\n[GOOD] Strong performance, close to target")
    elif passed >= 5:
        print("\n[MODERATE] Needs improvement")
    else:
        print("\n[NEEDS WORK] Significant issues remain")

    print(f"{'=' * 80}\n")

if __name__ == "__main__":
    run_tests()
