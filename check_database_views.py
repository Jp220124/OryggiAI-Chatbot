"""
Check what database views exist
Views can simplify complex queries and improve performance
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.database import db_manager

print("Querying database for existing VIEWS...")
print("=" * 80)

# Query to get all views in the database
query = """
SELECT 
    TABLE_SCHEMA,
    TABLE_NAME,
    VIEW_DEFINITION
FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
ORDER BY TABLE_NAME
"""

try:
    db_manager.initialize()
    views = db_manager.execute_query(query)
    
    print(f"\nFound {len(views)} views:\n")
    
    for view in views:
        schema = view.get('TABLE_SCHEMA', 'dbo')
        name = view.get('TABLE_NAME', 'Unknown')
        definition = view.get('VIEW_DEFINITION', '')
        
        print(f"View: {schema}.{name}")
        print("-" * 80)
        
        # Check if it's related to employees/departments
        definition_lower = definition.lower() if definition else ''
        is_relevant = any(keyword in definition_lower for keyword in 
                         ['employee', 'department', 'section', 'dept', 'emp'])
        
        if is_relevant:
            print("✓ RELEVANT for employee/department queries")
            # Show first 200 chars of definition
            preview = definition[:200] + "..." if len(definition) > 200 else definition
            print(f"Definition preview: {preview}")
        else:
            print("(Not immediately relevant)")
        
        print()
    
    # Save full results to file
    with open("database_views.txt", "w", encoding="utf-8") as f:
        f.write("DATABASE VIEWS ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        for view in views:
            f.write(f"View: {view.get('TABLE_SCHEMA')}.{view.get('TABLE_NAME')}\n")
            f.write(f"Definition:\n{view.get('VIEW_DEFINITION', 'N/A')}\n")
            f.write("\n" + "=" * 80 + "\n\n")
    
    print(f"\nFull details saved to database_views.txt")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
