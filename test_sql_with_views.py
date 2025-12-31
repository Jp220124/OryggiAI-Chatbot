"""
Test SQL Generation with Views
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.agents.sql_agent import get_sql_agent
from app.database import db_manager

# Initialize
db_manager.initialize()
sql_agent = get_sql_agent()

# Test queries that should use the new views
test_queries = [
    "How many employees are in each department?",
    "Show me punch records from yesterday",
    "List all active employees",
    "How many visitors checked in today?"
]

print("TESTING SQL GENERATION WITH VIEWS")
print("="*80)

for query in test_queries:
    print(f"\n\nQuery: {query}")
    print("-"*80)
    
    try:
        # Invoke the SQL agent
        result = sql_agent.invoke({"question": query})
        
        # Extract the SQL
        if "result" in result:
            sql = result["result"]
            print(f"\nGenerated SQL:")
            print(sql)
            
            # Check if using views
            view_names = [
                'AllEmployeeUnion', 'vw_RawPunchDetail', 'vw_EmployeeMaster_Vms',
                'View_Visitor_EnrollmentDetail', 'View_Contractor_Detail'
            ]
            
            uses_views = any(view in sql for view in view_names)
            if uses_views:
                matched_views = [v for v in view_names if v in sql]
                print(f"\n✓ Uses views: {', '.join(matched_views)}")
            else:
                print("\n✗ Does NOT use views - uses manual JOINs")
                
        else:
            print(f"No result found: {result}")
            
    except Exception as e:
        print(f"ERROR: {e}")

print("\n\n" + "="*80)
