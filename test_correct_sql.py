"""Test the correct SQL approach using EmployeeMaster.SecCode"""
from app.database.connection import init_database
from app.database import db_manager

init_database()

# The CORRECT query should use EmployeeMaster.SecCode
correct_sql = """
SELECT TOP 5
    SecCode,
    COUNT(Ecode) AS EmployeeCount
FROM EmployeeMaster
WHERE Active = 1
GROUP BY SecCode
ORDER BY EmployeeCount DESC
"""

print("CORRECT SQL (using EmployeeMaster.SecCode):")
print(correct_sql)
print()

try:
    result = db_manager.execute_query(correct_sql)
    print(f"Results: {len(result)} rows")
    for row in result:
        print(f"  Section {row['SecCode']}: {row['EmployeeCount']} employees")
except Exception as e:
    print(f"ERROR: {e}")
