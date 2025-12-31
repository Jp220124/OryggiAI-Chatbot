"""Test SQL generation via API"""
import requests
import json

url = "http://localhost:9000/api/chat/query"

question = "Show me the top 5 departments with the most employees"

payload = {
    "question": question,
    "tenant_id": "default",
    "user_id": "admin",
    "user_role": "ADMIN",
    "session_id": "debug_session"
}

print(f"Testing: {question}")
print("=" * 60)

response = requests.post(url, json=payload)

if response.status_code == 200:
    data = response.json()
    
    print(f"\nSuccess: {data.get('success')}")
    print(f"Result Count: {data.get('result_count', 0)}")
    print(f"\nTables Used:")
    for t in data.get('tables_used', []):
        print(f"  - {t}")
    
    print(f"\nGenerated SQL:")
    print(data.get('sql_query', 'NO SQL'))
    
    print(f"\nAnswer:")
    print(data.get('answer', ''))
    
    # Check for wrong pattern
    tables = data.get('tables_used', [])
    wrong_tables = ['EmpDepartRole', 'DeptCategoryRelation']
    if any(t in tables for t in wrong_tables):
        print("\n[ERROR] Using wrong/empty tables!")
    
    if 'SectionMaster' not in tables:
        print("\n[ERROR] Missing SectionMaster - incorrect join pattern!")
    else:
        print("\n[OK] Using SectionMaster - correct pattern")
    
else:
    print(f"Error: {response.status_code}")
    print(response.text)
