import logging
from app.database import init_database, db_manager

# Suppress logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
from loguru import logger
logger.remove()

def test_join():
    init_database()
    
    print("\nTesting Join: Employee -> Section -> Dept")
    query = """
    SELECT TOP 5 
        E.EmpName, 
        S.SecName, 
        D.Dname 
    FROM EmployeeMaster E 
    JOIN SectionMaster S ON E.SecCode = S.SecCode 
    JOIN DeptMaster D ON S.Dcode = D.Dcode
    """
    
    try:
        results = db_manager.execute_query(query)
        for r in results:
            print(r)
        print("\nSUCCESS: Join worked!")
    except Exception as e:
        print(f"\nFAILURE: {e}")

if __name__ == "__main__":
    test_join()
