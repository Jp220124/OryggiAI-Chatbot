import requests
import json
import time
from datetime import datetime

API_URL = "http://localhost:9000/api/chat/query"

# Previously rate-limited and failed questions
questions = [
    # Rate-limited questions
    ("Q7", "What is the attendance percentage of Engineering department?"),
    ("Q13", "List all students who were late more than 3 times this week"),
    ("Q14", "What time did John Smith arrive today?"),
    ("Q23", "Which employees have overtime this week?"),
    ("Q24", "List staff who haven't punched out yesterday"),
    ("Q25", "Show early departures from Library staff today"),
    ("Q26", "Which department has the highest attendance rate?"),
    ("Q27", "Compare attendance between Science and Arts departments"),
    ("Q35", "Who visited the Dean's office this week?"),
    ("Q36", "Show visitor log for yesterday"),
    ("Q37", "Which department receives the most visitors?"),
    ("Q38", "How many vendors visited this month?"),
    ("Q39", "List parent visits for this semester"),
    ("Q48", "What is the overall attendance rate this semester?"),
    ("Q49", "Compare this month's attendance with last month"),
    ("Q50", "Show top 10 most punctual students this month"),
]

results = []

print("=" * 80)
print("RE-TESTING PREVIOUSLY FAILED QUESTIONS")
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

for qid, question in questions:
    try:
        start_time = time.time()
        response = requests.post(API_URL, json={"question": question}, timeout=60)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            result = {
                "id": qid,
                "question": question,
                "success": data.get("success", False),
                "sql_query": data.get("sql_query", ""),
                "error": data.get("error"),
                "result_count": data.get("result_count", 0),
                "execution_time": elapsed,
                "answer_preview": str(data.get("answer", ""))[:150]
            }
        else:
            result = {
                "id": qid,
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
            "id": qid,
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
    status = "PASS" if result["success"] and result["sql_query"] else "FAIL"
    error_info = ""
    if result["error"]:
        error_info = f" - ERROR: {result['error'][:40]}"
    elif "429" in result.get("answer_preview", ""):
        status = "RATE_LIMITED"
        error_info = " - API quota exceeded"

    print(f"{qid} [{status}] {question[:45]:<45}{error_info}")
    if result["sql_query"]:
        print(f"    SQL: {result['sql_query'][:80]}...")
    print()

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

successful = [r for r in results if r["success"] and r["sql_query"]]
failed = [r for r in results if not r["success"] or not r["sql_query"]]
rate_limited = [r for r in results if "429" in r.get("answer_preview", "")]

print(f"\nTotal Questions: {len(questions)}")
print(f"Successful (with SQL): {len(successful)} ({len(successful)/len(questions)*100:.1f}%)")
print(f"Failed/Rate-limited: {len(failed)} ({len(failed)/len(questions)*100:.1f}%)")

if failed:
    print("\n" + "-" * 40)
    print("STILL FAILING:")
    print("-" * 40)
    for r in failed:
        print(f"\n{r['id']}: {r['question']}")
        if r['error']:
            print(f"   Error: {r['error'][:100]}")
        if "429" in r.get("answer_preview", ""):
            print(f"   Issue: Rate limited")

# Save detailed results
with open("test_failed_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n\nDetailed results saved to test_failed_results.json")
print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
