"""Check actual column names in metadata tables"""

from app.config import settings
from sqlalchemy import create_engine, text, inspect

engine = create_engine(settings.database_url)
inspector = inspect(engine)

tables_to_check = ['CompanyMaster', 'BranchMaster', 'GenSetup', 'DepartmentMaster', 'DesignationMaster']

for table in tables_to_check:
    print(f"\n=== {table} Columns ===")
    try:
        cols = inspector.get_columns(table)
        for col in cols:
            print(f"  {col['name']} ({col['type']})")
    except Exception as e:
        print(f"  Error: {e}")

# Also query sample data from BranchMaster
print("\n=== Sample BranchMaster Data ===")
with engine.connect() as conn:
    try:
        result = conn.execute(text("SELECT TOP 5 * FROM BranchMaster"))
        cols = result.keys()
        print(f"Columns: {list(cols)}")
        for row in result:
            print(f"  {dict(row._mapping)}")
    except Exception as e:
        print(f"Error: {e}")
