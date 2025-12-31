"""Quick test to verify VIEW-FIRST SQL generation (no execution)"""
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    os.system('chcp 65001 > nul')

sys.path.insert(0, str(Path(__file__).parent))

from app.agents.sql_agent import RAGSQLAgent
from app.database import init_database
from app.rag.chroma_manager import chroma_manager

print("\n" + "="*80)
print("VIEW-FIRST SQL GENERATION TEST")
print("="*80 + "\n")

# Initialize
init_database()
chroma_manager.initialize()
agent = RAGSQLAgent()

# Test queries
queries = [
    "How many employees are in each department?",
    "Show me the top 5 departments with the most employees",
    "which Employee have the highest logs",
    "List all employees in IT department"
]

results = []
for i, question in enumerate(queries, 1):
    print(f"\nTEST {i}: {question}")
    print("-" * 80)

    result = agent.generate_sql(question)
    sql = result['sql_query']

    # Check for views
    uses_view = any(v in sql.lower() for v in ['vw_', 'view_', 'allemployeeunion'])
    uses_deprecated = 'empdepartrole' in sql.lower()

    print(f"SQL: {sql}")
    print(f"Uses View: {'YES' if uses_view else 'NO'}")

    if uses_deprecated:
        print("WARNING: Uses deprecated EmpDepartRole table!")
        status = "FAIL"
    elif uses_view:
        status = "PASS"
    else:
        status = "WARNING"

    print(f"Status: {status}")
    results.append({"query": question, "sql": sql, "uses_view": uses_view, "status": status})

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"PASSED: {passed}/{len(results)}")
print(f"View Usage: {sum(1 for r in results if r['uses_view'])}/{len(results)}")

if passed == len(results):
    print("\nSUCCESS: All queries use VIEW-FIRST architecture!")
else:
    print(f"\nPartial success: {passed}/{len(results)} queries use views")
