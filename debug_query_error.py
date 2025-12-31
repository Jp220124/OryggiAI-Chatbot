"""
Debug script to test the query and identify the exact error
"""
from app.database.connection import init_database, db_manager
from app.rag.faiss_manager import faiss_manager
from app.agents.sql_agent import RAGSQLAgent

# Initialize
init_database()
faiss_manager.initialize()
agent = RAGSQLAgent()

# Generate SQL
question = "top 5 employees as highest number of in punches"
print(f"Question: {question}")
print("=" * 80)

result = agent.generate_sql(question)
sql = result['sql_query']

print(f"\nGenerated SQL:")
print(sql)
print("=" * 80)

# Try to execute
print("\nAttempting to execute...")
try:
    rows = db_manager.execute_query(sql)
    print(f"SUCCESS - Got {len(rows)} rows")
    if rows:
        print("\nFirst row:")
        print(rows[0])
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)}")
    
    # Try to understand the error
    print("\nDebugging...")
    print(f"SQL type: {type(sql)}")
    print(f"SQL length: {len(sql)}")
    print(f"SQL starts with: {sql[:50]}")
    
    # Try executing manually
    print("\nTrying manual execution...")
    try:
        with db_manager.engine.connect() as conn:
            from sqlalchemy import text
            result_proxy = conn.execute(text(sql))
            print(f"Result proxy type: {type(result_proxy)}")
            print(f"Returns rows: {result_proxy.returns_rows}")
            
            if result_proxy.returns_rows:
                print("Fetching rows...")
                rows = result_proxy.fetchall()
                print(f"Got {len(rows)} rows")
            else:
                print("Query does NOT return rows (DDL/DML statement?)")
    except Exception as e2:
        print(f"Manual execution also failed: {e2}")
