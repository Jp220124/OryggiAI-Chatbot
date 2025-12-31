"""
Autonomous test script to verify frontend connection and query functionality
Tests:
1. Backend health endpoint
2. Frontend health check (same as frontend uses)
3. Actual queries that were failing
4. Connection status
"""

import requests
import time

def test_health_endpoint():
    """Test 1: Backend /health endpoint"""
    print("\n" + "="*80)
    print("TEST 1: Backend Health Endpoint")
    print("="*80)
    
    try:
        response = requests.get("http://localhost:9000/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS: Health endpoint responding")
            print(f"   Status: {data.get('status')}")
            print(f"   App: {data.get('app')}")
            print(f"   Version: {data.get('version')}")
            return True
        else:
            print(f"❌ FAIL: Health endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: {type(e).__name__}: {str(e)}")
        return False

def test_frontend_health_check():
    """Test 2: Simulate frontend health check"""
    print("\n" + "="*80)
    print("TEST 2: Frontend Health Check Simulation")
    print("="*80)
    print("This simulates exactly what the frontend does to check connection...")
    
    try:
        # This is what the frontend does now after our fix
        response = requests.get("http://localhost:9000/health", timeout=5)
        
        if response.ok:
            print(f"✅ PASS: Frontend would show 'Connected' (response.ok = True)")
            print(f"   HTTP Status: {response.status_code}")
            return True
        else:
            print(f"❌ FAIL: Frontend would show 'Disconnected' (response.ok = False)")
            print(f"   HTTP Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Frontend would show 'Disconnected' (exception occurred)")
        print(f"   Error: {type(e).__name__}: {str(e)}")
        return False

def test_query(question):
    """Test a query through the API"""
    print(f"\n{'─'*80}")
    print(f"Query: {question}")
    print(f"{'─'*80}")
    
    payload = {
        "question": question,
        "tenant_id": "default",
        "user_id": "admin",
        "user_role": "ADMIN"
    }
    
    try:
        start_time = time.time()
        response = requests.post("http://localhost:9000/api/chat/query", json=payload, timeout=30)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for errors in response
            if data.get('error'):
                print(f"❌ FAIL: Query returned error")
                print(f"   Error: {data['error']}")
                return False
            
            # Check for "[Errno 22]" which was the original problem
            answer = data.get('answer', '')
            if '[Errno 22]' in answer or 'Invalid argument' in answer:
                print(f"❌ FAIL: Still getting '[Errno 22] Invalid argument' error")
                print(f"   Answer: {answer}")
                return False
            
            print(f"✅ PASS: Query executed successfully")
            print(f"   Time: {elapsed:.2f}s")
            print(f"   Results: {data.get('result_count', 0)} row(s)")
            print(f"   Answer: {answer[:100]}...")
            
            if data.get('sql_query'):
                print(f"   SQL: {data['sql_query'][:80]}...")
            
            return True
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ FAIL: Request timeout (30s)")
        return False
    except Exception as e:
        print(f"❌ FAIL: {type(e).__name__}: {str(e)}")
        return False

def test_queries():
    """Test 3: Actual queries that were failing"""
    print("\n" + "="*80)
    print("TEST 3: Queries That Previously Failed")
    print("="*80)
    
    test_cases = [
        "List all the terminal",
        "how many devices",
        "How many employees are there?",
    ]
    
    results = []
    for query in test_cases:
        result = test_query(query)
        results.append((query, result))
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    return passed == total

def main():
    """Run all tests"""
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*20 + "FRONTEND CONNECTION & QUERY TEST" + " "*26 + "║")
    print("╚" + "="*78 + "╝")
    
    results = []
    
    # Test 1: Health endpoint
    results.append(("Health Endpoint", test_health_endpoint()))
    
    # Test 2: Frontend connection check
    results.append(("Frontend Connection", test_frontend_health_check()))
    
    # Test 3: Queries
    results.append(("Query Execution", test_queries()))
    
    # Final Summary
    print("\n" + "="*80)
    print("FINAL TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n{passed}/{total} test groups passed")
    
    if passed == total:
        print("\n" + "🎉"*40)
        print("✅ ALL TESTS PASSED!")
        print("✅ Frontend should show 'Connected'")
        print("✅ Queries working without '[Errno 22]' errors")
        print("🎉"*40)
        return 0
    else:
        print(f"\n⚠️ {total - passed} test group(s) failed.")
        print("Please check the error messages above.")
        return 1

if __name__ == "__main__":
    exit(main())
