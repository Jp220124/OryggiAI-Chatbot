"""
Test SQL Generation via API - Check if Views are Used
"""
import requests
import json

BASE_URL = "http://localhost:9000/api/chat"

test_queries = [
    "How many employees are in each department?",
    "Show me punch records from yesterday",
    "List all active employees",
    "Show employees with biometric status"
]

print("TESTING SQL GENERATION WITH VIEWS (via API)")
print("="*80)

for query in test_queries:
    print(f"\n\nQuery: {query}")
    print("-"*80)
    
    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={"question": query},
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"FULL RESPONSE: {json.dumps(data, indent=2)}")
            
            sql = data.get('sql_query', 'NO SQL GENERATED')
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
                print(f"\n✓ USES VIEWS: {', '.join(matched_views)}")
            else:
                print("\n✗ DOES NOT USE VIEWS - uses manual JOINs or base tables")
            
            # Check result count
            result_count = data.get('result_count', 0)
            print(f"Result count: {result_count}")
            
        else:
            print(f"ERROR: Status code {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"ERROR: {e}")

print("\n\n" + "="*80)
print("TEST COMPLETE")
