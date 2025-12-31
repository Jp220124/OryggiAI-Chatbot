"""Test SQL generation via API and save to file"""
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

response = requests.post(url, json=payload)

# Save full response to file
with open("api_response.json", "w") as f:
    json.dump(response.json(), f, indent=2)

if response.status_code == 200:
    data = response.json()
    
    # Write detailed analysis to file
    with open("sql_analysis.txt", "w") as f:
        f.write(f"Question: {question}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Success: {data.get('success')}\n")
        f.write(f"Result Count: {data.get('result_count', 0)}\n\n")
        
        f.write("Tables Used:\n")
        for t in data.get('tables_used', []):
            f.write(f"  - {t}\n")
        
        f.write("\nGenerated SQL:\n")
        f.write("-" * 80 + "\n")
        f.write(data.get('sql_query', 'NO SQL'))
        f.write("\n" + "-" * 80 + "\n")
        
        # Analysis
        tables = data.get('tables_used', [])
        f.write("\n\nANALYSIS:\n")
        f.write("=" * 80 + "\n")
        
        wrong_tables = ['EmpDepartRole', 'DeptCategoryRelation', 'HolidayDepartmentRelation']
        bad = [t for t in tables if t in wrong_tables]
        if bad:
            f.write(f"[ERROR] Using empty/wrong tables: {', '.join(bad)}\n")
        
        if 'SectionMaster' not in tables:
            f.write("[ERROR] Missing SectionMaster - incorrect join pattern!\n")
            f.write("CORRECT PATTERN: EmployeeMaster -> SectionMaster -> DeptMaster\n")
        else:
            f.write("[OK] Using SectionMaster\n")
        
        if data.get('result_count', 0) == 0:
            f.write("\n[PROBLEM] Query returned 0 results!\n")
            if bad:
                f.write(f"Likely cause: Using empty table(s): {', '.join(bad)}\n")
        
    print("Analysis saved to sql_analysis.txt")
    print("Full response saved to api_response.json")
else:
    print(f"Error: {response.status_code}")
