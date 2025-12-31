"""
Simple debug: What SQL is generated for department query?
"""

from app.database.connection import init_database
from app.rag.chroma_manager import chroma_manager
from app.agents.sql_agent import sql_agent

init_database()
chroma_manager.initialize()

question = "Show me the top 5 departments with the most employees"

print("Question:", question)
print()
print("="*80)

# Generate SQL
result = sql_agent.generate_sql(question)
sql_query = result['sql_query']

print("GENERATED SQL:")
print(sql_query)
print("="*80)

# Execute
try:
    rows = sql_agent.execute_query(sql_query)
    print(f"Rows returned: {len(rows)}")
    
    if len(rows) > 0:
        print("\nResults:")
        for row in rows[:10]:
            print(row)
    else:
        print("\nNO RESULTS - Checking why...")
        
        # Check active employees
        check1 = "SELECT COUNT(*) as cnt FROM EmployeeMaster WHERE Active = 1"
        r1 = sql_agent.execute_query(check1)
        print(f"Active employees in EmployeeMaster: {r1[0]['cnt']}")
        
        # Check if SecCode has values
        check2 = "SELECT COUNT(DISTINCT SecCode) as cnt FROM EmployeeMaster WHERE Active = 1 AND SecCode IS NOT NULL"
        r2 = sql_agent.execute_query(check2)
        print(f"Employees with non-null SecCode: {r2[0]['cnt']}")
        
        # Check DeptMaster
        check3 = "SELECT COUNT(*) as cnt FROM DeptMaster"
        r3 = sql_agent.execute_query(check3)
        print(f"Total departments in DeptMaster: {r3[0]['cnt']}")
        
except Exception as e:
    print(f"ERROR: {e}")
