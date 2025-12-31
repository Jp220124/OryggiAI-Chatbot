"""
Test Live API with Previously Failing Queries
Tests the running server to verify VIEW-FIRST fixes are working
"""
import requests
import json
import sys
import os

# Set UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    os.system('chcp 65001 > nul')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

API_URL = "http://localhost:9000/api/chat/query"

# Previously failing queries
test_queries = [
    "How many employees are in each department?",
    "Show me the top 5 departments with the most employees",
    "which Employee have the highest logs",
    "List all employees in IT department"
]

def test_query(question: str, test_number: int):
    """Test a single query via API"""
    print(f"\n{'='*100}")
    print(f"TEST {test_number}: {question}")
    print('='*100)

    payload = {
        "question": question,
        "user_id": "test_user",
        "session_id": "test_session"
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Debug: Print full response
            print(f"\nDEBUG - Full Response:")
            print(json.dumps(data, indent=2)[:500])

            # Check if SQL was generated
            sql_query = data.get("sql_query", "") or ""
            answer = data.get("answer", "") or ""
            result_count = len(data.get("results", []))

            # Check if using views
            uses_view = any(v in sql_query.lower() for v in ['vw_', 'view_', 'allemployeeunion']) if sql_query else False
            uses_deprecated = 'empdepartrole' in sql_query.lower() if sql_query else False

            print(f"\nSQL Generated:")
            print(f"  {sql_query}")
            print(f"\nUses View: {'✅ YES' if uses_view else '❌ NO'}")

            if uses_deprecated:
                print(f"⚠️ WARNING: Uses deprecated EmpDepartRole table!")
                status = "❌ FAIL"
            elif result_count > 0:
                print(f"✅ Results: {result_count} rows")
                status = "✅ PASS"
            elif result_count == 0 and not uses_deprecated:
                print(f"⚠️ WARNING: 0 results (but not using deprecated table)")
                status = "⚠️ WARNING"
            else:
                print(f"❌ No results")
                status = "❌ FAIL"

            print(f"\nAnswer Preview:")
            print(f"  {answer[:200]}...")

            print(f"\nStatus: {status}")

            return {
                "question": question,
                "sql": sql_query,
                "uses_view": uses_view,
                "result_count": result_count,
                "status": status
            }

        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"  {response.text}")
            return {
                "question": question,
                "sql": "",
                "uses_view": False,
                "result_count": 0,
                "status": "❌ ERROR"
            }

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {
            "question": question,
            "sql": "",
            "uses_view": False,
            "result_count": 0,
            "status": "❌ ERROR"
        }

def main():
    print("\n" + "="*100)
    print("LIVE API TEST - VIEW-FIRST ARCHITECTURE VERIFICATION")
    print("="*100)
    print(f"Testing API at: {API_URL}")

    # Test server health first
    try:
        health_response = requests.get("http://localhost:9000/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Server is healthy")
        else:
            print("⚠️ Server health check failed")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return

    # Run tests
    results = []
    for i, question in enumerate(test_queries, 1):
        result = test_query(question, i)
        results.append(result)

    # Summary
    print("\n" + "="*100)
    print("TEST SUMMARY")
    print("="*100)
    print(f"{'#':<5} {'Status':<15} {'View?':<10} {'Rows':<10} {'Question'}")
    print("-"*100)

    passed = 0
    failed = 0
    warnings = 0
    view_usage = 0

    for i, r in enumerate(results, 1):
        view_icon = "✅" if r['uses_view'] else "❌"

        print(f"{i:<5} {r['status']:<15} {view_icon} {str(r['uses_view']):<7} {r['result_count']:<10} {r['question']}")

        if "PASS" in r['status']:
            passed += 1
        elif "FAIL" in r['status']:
            failed += 1
        else:
            warnings += 1

        if r['uses_view']:
            view_usage += 1

    print("="*100)
    print(f"\nFINAL RESULTS:")
    print(f"  ✅ PASSED: {passed}/{len(test_queries)}")
    print(f"  ❌ FAILED: {failed}/{len(test_queries)}")
    print(f"  ⚠️  WARNINGS: {warnings}/{len(test_queries)}")
    print(f"  📊 View Usage: {view_usage}/{len(test_queries)} ({view_usage/len(test_queries)*100:.1f}%)")

    if passed == len(test_queries):
        print("\n🎉 ALL TESTS PASSED! VIEW-FIRST architecture is working perfectly!")
    elif passed > failed:
        print(f"\n✓ Most tests passed ({passed}/{len(test_queries)})")
    else:
        print(f"\n⚠️ Multiple failures detected ({failed}/{len(test_queries)})")

    print("="*100)

if __name__ == "__main__":
    main()
