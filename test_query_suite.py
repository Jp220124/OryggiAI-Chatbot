"""
Comprehensive Test Suite for Enriched Schema
Tests various query types to verify improvement
"""

from app.rag.faiss_manager import faiss_manager
from app.agents.sql_agent import RAGSQLAgent
from app.database.connection import init_database

# Initialize
init_database()
faiss_manager.initialize()
agent = RAGSQLAgent()

# Test queries covering different patterns
test_queries = [
    {
        "name": "Attendance In/Out Status",
        "question": "Show me employee in and out counts for today",
        "expected_tables": ["Attendance", "EmployeeMaster"]
    },
    {
        "name": "Employee Attendance Report",
        "question": "Generate attendance report with employee names and their in/out times",
        "expected_tables": ["Attendance", "EmployeeMaster"]
    },
    {
        "name": "Late Arrival Tracking",
        "question": "Find employees who arrived late (after 9 AM) today",
        "expected_tables": ["Attendance", "EmployeeMaster"]
    },
    {
        "name": "Department-wise Attendance",
        "question": "Show attendance count by department for this month",
        "expected_tables": ["Attendance", "EmployeeMaster", "DeptMaster"]
    },
    {
        "name": "Missing Punch Records",
        "question": "List employees who have in-time but no out-time today",
        "expected_tables": ["Attendance", "EmployeeMaster"]
    },
    {
        "name": "Biometric Data Query",
        "question": "Show biometric enrollment status by employee",
        "expected_tables": ["Biometric", "EmployeeMaster"]
    }
]

print("=" * 80)
print("COMPREHENSIVE SCHEMA ENRICHMENT TEST SUITE")
print("=" * 80)

results = []

for i, test in enumerate(test_queries, 1):
    print(f"\n\n[TEST {i}/{len(test_queries)}] {test['name']}")
    print("-" * 80)
    print(f"Query: {test['question']}")
    
    try:
        # Generate SQL
        result = agent.generate_sql(test['question'])
        
        # Check if SQL was generated
        if result['sql_query']:
            print(f"\nSUCCESS - Generated SQL:")
            # Print first 150 characters
            sql_preview = result['sql_query'].replace('\n', ' ').strip()
            print(sql_preview[:150] + "..." if len(sql_preview) > 150 else sql_preview)
            
            results.append({
                "test": test['name'],
                "status": "SUCCESS",
                "sql": result['sql_query']
            })
        else:
            print("\nFAILED - No SQL generated")
            results.append({
                "test": test['name'],
                "status": "FAILED",
                "sql": None
            })
            
    except Exception as e:
        print(f"\nERROR: {str(e)[:200]}")
        results.append({
            "test": test['name'],
            "status": "ERROR",
            "sql": None
        })

# Summary
print("\n\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
syntax_error_count = sum(1 for r in results if r['status'] == 'SYNTAX_ERROR')
failed_count = sum(1 for r in results if r['status'] in ['FAILED', 'ERROR'])

print(f"\nTotal Tests: {len(results)}")
print(f"  SUCCESS (valid SQL): {success_count}")
print(f"  SYNTAX ERRORS: {syntax_error_count}")
print(f"  FAILED: {failed_count}")
print(f"\nSuccess Rate: {(success_count / len(results) * 100):.1f}%")

# Detailed results
print("\n" + "=" * 80)
print("DETAILED RESULTS")
print("=" * 80)

for r in results:
    status_symbol = "OK" if r['status'] == 'SUCCESS' else "!!"
    print(f"\n[{status_symbol}] {r['test']}: {r['status']}")
    if r['sql']:
        print(f"    SQL: {r['sql'][:80]}...")

print("\n" + "=" * 80)
