from app.database.connection import init_database, get_db
from sqlalchemy import text

init_database()
db = next(get_db())

# Check Attendance table structure
print("=" * 60)
print("Attendance Table Structure:")
print("=" * 60)
result = db.execute(text("""
    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'Attendance'
    ORDER BY ORDINAL_POSITION
"""))
for row in result:
    print(f"  {row[0]}: {row[1]} ({row[2]})")

# Sample data from Attendance
print("\n" + "="*60)
print("Sample data from Attendance (first 2 rows):")
print("="*60)
result = db.execute(text("SELECT TOP 2 * FROM dbo.Attendance"))
columns = list(result.keys())
for row in result:
    for i, col in enumerate(columns):
        print(f"  {col}: {row[i]}")
    print("-" * 40)
