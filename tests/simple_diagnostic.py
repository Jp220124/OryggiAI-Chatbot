"""
Simple diagnostic - test one query and see the output
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

from app.database import init_database
from app.rag import faiss_manager, few_shot_manager
from app.agents.sql_agent import sql_agent

# Initialize
print("Initializing services...")
init_database()
faiss_manager.initialize()
few_shot_manager.initialize()
print("Services initialized\n")

# Test a simple JOIN query that failed
question = "List all employees with their department names"
expected = "JOIN"

print("=" * 80)
print(f"Question: {question}")
print(f"Expected Pattern: {expected}")
print("=" * 80)

try:
    result = sql_agent.generate_sql(question)
    sql_query = result["sql_query"]

    pattern_found = expected.upper() in sql_query.upper()

    print(f"\nGenerated SQL:")
    print(sql_query)
    print(f"\nPattern '{expected}' found: {pattern_found}")
    print(f"\nTables referenced: {result.get('tables_referenced', [])}")
    print(f"Context used: {len(result['context_used'])} schemas")

    # Try to execute
    print("\nExecuting query...")
    results = sql_agent.execute_query(sql_query)
    print(f"Query executed successfully! Returned {len(results)} rows")

    if results and len(results) > 0:
        print("\nFirst 3 results:")
        for i, row in enumerate(results[:3], 1):
            print(f"{i}. {row}")

except Exception as e:
    print(f"ERROR: {str(e)}")

print("\n" + "=" * 80)
