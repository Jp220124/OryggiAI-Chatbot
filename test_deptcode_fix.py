"""
Test the DeptCode fix
Verify that the SQL agent now uses SecCode instead of hallucinating DeptCode
"""

from app.database.connection import init_database
from app.rag.chroma_manager import chroma_manager
from app.agents.sql_agent import sql_agent

print("=" * 80)
print("TESTING: DeptCode Fix Verification")
print("=" * 80)

# Initialize
init_database()
chroma_manager.initialize()

# Test queries
test_queries = [
    "Show me the top 5 departments with the most employees",
    "How many employees are in each department?",
    "List all employees grouped by department"
]

all_passed = True

for i, question in enumerate(test_queries, 1):
    print(f"\n{'=' * 80}")
    print(f"TEST {i}: {question}")
    print("=" * 80)
    
    try:
        result = sql_agent.generate_sql(question)
        sql_query = result['sql_query']
        
        print(f"\n✓ Generated SQL:")
        print(sql_query)
        print()
        
        # Check for the fix
        has_seccode = 'SecCode' in sql_query
        has_deptcode = 'DeptCode' in sql_query
        
        print("Validation:")
        if has_seccode:
            print("  ✓ PASS: Uses 'SecCode' (correct)")
        else:
            print("  ⚠️  WARNING: 'SecCode' not found in query")
        
        if has_deptcode:
            print("  ❌ FAIL: Still using 'DeptCode' (wrong - column doesn't exist)")
            all_passed = False
        else:
            print("  ✓ PASS: Does NOT use 'DeptCode' (good)")
        
        # Try to execute it
        print("\nExecution Test:")
        try:
            rows = sql_agent.execute_query(sql_query)
            print(f"  ✓ Query executed successfully! Returned {len(rows)} rows")
            if rows:
                print(f"  Sample result: {rows[0]}")
        except Exception as e:
            print(f"  ❌ Query execution failed: {str(e)}")
            all_passed = False
            
    except Exception as e:
        print(f"\n❌ SQL generation failed: {str(e)}")
        all_passed = False

print("\n" + "=" * 80)
print("FINAL RESULT")
print("=" * 80)

if all_passed:
    print("✅ ALL TESTS PASSED! The fix is working correctly.")
else:
    print("❌ SOME TESTS FAILED. The issue may still exist.")

print("=" * 80)
