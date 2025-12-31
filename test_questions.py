import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:9000/api/chat/query"

# All 50 questions to test
questions = [
    # Student Attendance Questions (1-15)
    "Who was late today?",
    "How many students are absent today?",
    "Which students arrived late this week?",
    "Show me the attendance of Computer Science department today",
    "Who has the most late arrivals this month?",
    "List students who left early yesterday",
    "What is the attendance percentage of Engineering department?",
    "Show absent students from MBA program today",
    "Which students have perfect attendance this semester?",
    "How many students checked in before 9 AM today?",
    "Who hasn't arrived yet today?",
    "Show attendance summary for student ID 12345",
    "List all students who were late more than 3 times this week",
    "What time did John Smith arrive today?",
    "Show daily attendance trend for the past 7 days",

    # Employee/Staff Attendance (16-25)
    "How many staff members are present today?",
    "Which faculty members are absent today?",
    "Show late arrivals for administrative staff this week",
    "What are the working hours of Professor Johnson today?",
    "List all security staff currently on duty",
    "How many hours did maintenance staff work this month?",
    "Show attendance report for HR department",
    "Which employees have overtime this week?",
    "List staff who haven't punched out yesterday",
    "Show early departures from Library staff today",

    # Department-wise Analytics (26-32)
    "Which department has the highest attendance rate?",
    "Compare attendance between Science and Arts departments",
    "Show department-wise late arrival statistics",
    "List all departments with their employee count",
    "Which department has the most absences this week?",
    "Show average working hours by department",
    "Rank departments by punctuality score",

    # Visitor Management (33-40)
    "How many visitors came today?",
    "List all visitors currently in campus",
    "Who visited the Dean's office this week?",
    "Show visitor log for yesterday",
    "Which department receives the most visitors?",
    "How many vendors visited this month?",
    "List parent visits for this semester",
    "Show guest speakers who visited last month",

    # Access Control & Security (41-45)
    "Which doors were accessed after 10 PM yesterday?",
    "Show access log for Library building today",
    "List restricted area access attempts this week",
    "Which machines/devices are offline?",
    "Show all access points with their status",

    # Reports & Statistics (46-50)
    "Generate monthly attendance summary",
    "Show weekly punctuality report",
    "What is the overall attendance rate this semester?",
    "Compare this month's attendance with last month",
    "Show top 10 most punctual students this month",
]

results = []

print("=" * 80)
print("CHATBOT QUESTION TESTING - 50 QUESTIONS")
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

for i, question in enumerate(questions, 1):
    try:
        start_time = time.time()
        response = requests.post(API_URL, json={"question": question}, timeout=60)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            result = {
                "id": i,
                "question": question,
                "success": data.get("success", False),
                "sql_query": data.get("sql_query", ""),
                "error": data.get("error"),
                "result_count": data.get("result_count", 0),
                "execution_time": elapsed,
                "answer_preview": str(data.get("answer", ""))[:100]
            }
        else:
            result = {
                "id": i,
                "question": question,
                "success": False,
                "sql_query": "",
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "result_count": 0,
                "execution_time": elapsed,
                "answer_preview": ""
            }
    except Exception as e:
        result = {
            "id": i,
            "question": question,
            "success": False,
            "sql_query": "",
            "error": str(e),
            "result_count": 0,
            "execution_time": 0,
            "answer_preview": ""
        }

    results.append(result)

    # Print status
    status = "PASS" if result["success"] else "FAIL"
    error_msg = f" - ERROR: {result['error'][:50]}" if result["error"] else ""
    print(f"Q{i:02d} [{status}] {question[:50]:<50}{error_msg}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

successful = [r for r in results if r["success"]]
failed = [r for r in results if not r["success"]]
errors = [r for r in results if r["error"]]

print(f"\nTotal Questions: {len(questions)}")
print(f"Successful: {len(successful)} ({len(successful)/len(questions)*100:.1f}%)")
print(f"Failed: {len(failed)} ({len(failed)/len(questions)*100:.1f}%)")
print(f"With Errors: {len(errors)}")

if errors:
    print("\n" + "-" * 40)
    print("FAILED QUESTIONS:")
    print("-" * 40)
    for r in errors:
        print(f"\nQ{r['id']}: {r['question']}")
        print(f"   Error: {r['error']}")
        if r['sql_query']:
            print(f"   SQL: {r['sql_query'][:100]}...")

# Save detailed results to JSON
with open("test_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n\nDetailed results saved to test_results.json")
print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
