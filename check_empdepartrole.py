"""Check if EmpDepartRole has data"""
from app.database.connection import init_database
from app.database import db_manager

init_database()

queries = [
    ("Check EmpDepartRole table", "SELECT COUNT(*) as cnt FROM EmpDepartRole"),
    ("Check DeptMaster table", "SELECT COUNT(*) as cnt FROM DeptMaster"),
    ("Sample from EmpDepartRole", "SELECT TOP 5 * FROM EmpDepartRole"),
    ("Sample from DeptMaster", "SELECT TOP 5 * FROM DeptMaster"),
    ("Test the JOIN", "SELECT COUNT(*) as cnt FROM DeptMaster dm INNER JOIN EmpDepartRole edr ON dm.Dcode = edr.Dcode"),
]

for desc, query in queries:
    print(f"\n{desc}:")
    print(f"  SQL: {query}")
    try:
        result = db_manager.execute_query(query)
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  ERROR: {e}")
