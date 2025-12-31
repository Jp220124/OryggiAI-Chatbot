"""Check more column names and sample data"""

from app.config import settings
from sqlalchemy import create_engine, text, inspect

engine = create_engine(settings.database_url)

# Get company name
print("=== CompanyMaster Data ===")
with engine.connect() as conn:
    try:
        result = conn.execute(text("SELECT * FROM CompanyMaster"))
        for row in result:
            print(f"  {dict(row._mapping)}")
    except Exception as e:
        print(f"Error: {e}")

# Check DeptMaster (different name)
print("\n=== Checking for Department tables ===")
inspector = inspect(engine)
all_tables = inspector.get_table_names(schema='dbo')
dept_tables = [t for t in all_tables if 'dept' in t.lower() or 'department' in t.lower()]
print(f"Department related tables: {dept_tables}")

for table in dept_tables[:3]:
    print(f"\n--- {table} columns ---")
    try:
        cols = inspector.get_columns(table, schema='dbo')
        for col in cols[:10]:
            print(f"  {col['name']} ({col['type']})")
        # Get sample data
        result = engine.connect().execute(text(f"SELECT TOP 5 * FROM [{table}]"))
        print(f"Sample data:")
        for row in result:
            print(f"  {dict(row._mapping)}")
    except Exception as e:
        print(f"  Error: {e}")
