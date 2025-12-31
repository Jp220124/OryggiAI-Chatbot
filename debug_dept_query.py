"""
Debug: Check what SQL is being generated for department queries
"""

from app.database.connection import init_database
from app.rag.chroma_manager import chroma_manager
from app.agents.sql_agent import sql_agent

print("=" * 80)
print("DEBUGGING: Department Query SQL Generation")
print("=" * 80)

# Initialize
init_database()
chroma_manager.initialize()

question = "Show me the top 5 departments with the most employees"

print(f"\nQuestion: {question}")
print("\n" + "=" * 80)
print("STEP 1: Schema Context Retrieved")
print("=" * 80)

# Get schema context
schema_context = chroma_manager.query_schemas(question, n_results=10)

print(f"\nRetrieved {len(schema_context['documents'])} tables:")
for i, (meta, dist) in enumerate(zip(schema_context['metadatas'], schema_context['distances']), 1):
    print(f"  {i}. {meta.get('table_name', 'Unknown')} (distance: {dist:.4f})")

print("\n" + "=" * 80)
print("STEP 2: Generated SQL")
print("=" * 80)

# Generate SQL
result = sql_agent.generate_sql(question)
sql_query = result['sql_query']

print(f"\nGenerated SQL:\n{sql_query}")

print("\n" + "=" * 80)
print("STEP 3: SQL Analysis")
print("=" * 80)

# Check for common issues
issues = []

if 'DeptCode' in sql_query:
    issues.append("❌ Still using 'DeptCode' (non-existent column)")
    
if 'SecCode' in sql_query:
    print("✓ Uses 'SecCode' from EmployeeMaster")
    
if 'DeptMaster' in sql_query:
    print("✓ References 'DeptMaster' table")
    
if 'JOIN' in sql_query.upper():
    print("✓ Uses JOIN (likely joining EmployeeMaster with DeptMaster)")
else:
    print("⚠️  No JOIN detected - might be querying single table")

print("\n" + "=" * 80)
print("STEP 4: Execute and Check Results")
print("=" * 80)

try:
    rows = sql_agent.execute_query(sql_query)
    print(f"\n✓ Query executed successfully")
    print(f"  Rows returned: {len(rows)}")
    
    if len(rows) == 0:
        print("\n⚠️  PROBLEM: Query returned 0 rows")
        print("  Possible reasons:")
        print("  1. No active employees (WHERE Active = 1)")
        print("  2. No matching data in joined tables")
        print("  3. Incorrect JOIN conditions")
        print("  4. Wrong column names in WHERE/GROUP BY")
        
        # Check if there's any data at all
        print("\n  Checking if EmployeeMaster has any active employees...")
        test_query = "SELECT COUNT(*) as TotalActive FROM EmployeeMaster WHERE Active = 1"
        test_result = sql_agent.execute_query(test_query)
        print(f"  Active employees: {test_result[0]['TotalActive']}")
        
        if 'DeptMaster' in sql_query:
            print("\n  Checking DeptMaster table...")
            dept_query = "SELECT COUNT(*) as TotalDepts FROM DeptMaster"
            dept_result = sql_agent.execute_query(dept_query)
            print(f"  Departments in DeptMaster: {dept_result[0]['TotalDepts']}")
    else:
        print("\n✓ Results found:")
        for i, row in enumerate(rows[:5], 1):
            print(f"  {i}. {row}")
            
except Exception as e:
    print(f"\n❌ Query execution failed: {str(e)}")
    issues.append(f"Execution error: {str(e)}")

if issues:
    print("\n" + "=" * 80)
    print("ISSUES DETECTED")
    print("=" * 80)
    for issue in issues:
        print(f"  {issue}")

print("\n" + "=" * 80)
