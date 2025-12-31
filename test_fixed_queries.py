"""
Test script to verify the SQL syntax fix is working
Tests the queries that were previously failing with "[Errno 22] Invalid argument"
"""

import requests
import json

API_URL = "http://localhost:9000/api/chat/query"

# Test queries that were failing
test_queries = [
    "List all the terminal",
    "how many devices",
    "How many employees are there?",
    "Show me employee count by department"
]

def test_query(question: str):
    """Test a single query"""
    print(f"\n{'='*80}")
    print(f"Testing: {question}")
    print(f"{'='*80}")
    
    payload = {
        "question": question,
        "tenant_id": "default",
        "user_id": "admin",
        "user_role": "ADMIN"
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Status: Success")
            print(f"Answer: {data.get('answer', 'N/A')}")
            print(f"Result Count: {data.get('result_count', 0)}")
            
            if data.get('sql_query'):
                print(f"\nGenerated SQL:")
                print(f"  {data['sql_query']}")
            
            if data.get('error'):
                print(f"\n⚠️ Error: {data['error']}")
                return False
            
            return True
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Request timeout (30s)")
        return False
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTING SQL SYNTAX FIX")
    print("="*80)
    
    results = []
    for query in test_queries:
        success = test_query(query)
        results.append((query, success))
    
    # Summary
    print(f"\n\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for query, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {query}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The fix is working correctly.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check the errors above.")
