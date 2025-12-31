"""
Diagnostic script to analyze test failures
Shows actual SQL generated vs expected patterns
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

from loguru import logger
from app.database import init_database
from app.rag import faiss_manager, few_shot_manager
from app.agents.sql_agent import sql_agent

# Configure simple logging
logger.remove()
logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")

# Sample test cases to diagnose
TEST_CASES = [
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
    }
]

def diagnose():
    """Run diagnostic tests"""
    print("=" * 80)
    print("SQL GENERATION DIAGNOSTIC")
    print("=" * 80)

    # Initialize
    init_database()
    faiss_manager.initialize()
    few_shot_manager.initialize()

    print(f"\n[OK] Initialized services\n")

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/5: {test['id']}")
        print(f"{'=' * 80}")
        print(f"Category: {test['category']}")
        print(f"Question: {test['question']}")
        print(f"Expected Pattern: {test['expected_pattern']}")
        print()

        try:
            # Generate SQL
            result = sql_agent.generate_sql(test['question'])
            sql_query = result["sql_query"]

            # Check if pattern matches
            pattern_found = test['expected_pattern'].upper() in sql_query.upper()
            status = "[PASS]" if pattern_found else "[FAIL]"

            print(f"Status: {status}")
            print(f"\nGenerated SQL:")
            print(f"{sql_query}")

            if not pattern_found:
                print(f"\n[WARNING] Missing expected pattern: {test['expected_pattern']}")

            print(f"\nContext Used: {len(result['context_used'])} schema items")
            print(f"Tables Referenced: {', '.join(result.get('tables_referenced', []))}")

        except Exception as e:
            print(f"[ERROR] {str(e)}")

    print(f"\n{'=' * 80}")
    print("DIAGNOSIS COMPLETE")
    print(f"{'=' * 80}\n")

if __name__ == "__main__":
    diagnose()
