"""
End-to-End API Test for Multi-Modal RAG System
Tests the complete workflow: CSV loading → Intent routing → Query handling
"""
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000/api"

def test_load_csv_data():
    """Test loading CSV data for a project"""
    print("\n" + "="*80)
    print("TEST 1: Load CSV Data for apache-incubator-resilientdb")
    print("="*80)

    # Use the correct project_id (it's apache-incubator-resilientdb, not resilientdb-resilientdb)
    project_id = "apache-incubator-resilientdb"

    # Load CSV data with absolute paths
    csv_paths = {
        "commits_csv_path": "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv",
        "issues_csv_path": "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/issues.csv"
    }

    response = requests.post(
        f"{BASE_URL}/projects/{project_id}/load-csv",
        json=csv_paths
    )

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Status: {data['status']}")
        print(f"   Message: {data['message']}")
        print(f"   Loaded: {data['loaded']}")
        print(f"   Available data: {data['available_data']}")
        return True
    else:
        print(f"❌ Error: {response.text}")
        return False


def test_query_intent_routing():
    """Test different query types and intent routing"""
    print("\n" + "="*80)
    print("TEST 2: Query Intent Routing")
    print("="*80)

    test_queries = [
        ("Who is the latest committer?", "COMMITS"),
        ("What are the open issues?", "ISSUES"),
        ("Who are the maintainers?", "GOVERNANCE"),
        ("What is machine learning?", "GENERAL"),
        ("Show me recent commits", "COMMITS"),
        ("How many issues are there?", "ISSUES"),
    ]

    results = []

    for query, expected_intent in test_queries:
        print(f"\n📝 Query: '{query}'")
        print(f"   Expected Intent: {expected_intent}")

        response = requests.post(
            f"{BASE_URL}/query",
            json={
                "project_id": "apache-incubator-resilientdb",
                "query": query,
                "max_results": 5
            }
        )

        if response.status_code == 200:
            data = response.json()
            actual_intent = data['metadata'].get('intent', 'UNKNOWN')
            data_source = data['metadata'].get('data_source', 'unknown')
            confidence = data['metadata'].get('confidence', 0)

            match = "✅" if actual_intent == expected_intent else "❌"
            print(f"   {match} Actual Intent: {actual_intent} (confidence: {confidence:.2f})")
            print(f"   📊 Data Source: {data_source}")
            print(f"   💬 Response Preview: {data['response'][:150]}...")

            if 'records_found' in data['metadata']:
                print(f"   📈 Records Found: {data['metadata']['records_found']}")

            results.append({
                "query": query,
                "expected": expected_intent,
                "actual": actual_intent,
                "match": actual_intent == expected_intent
            })
        else:
            print(f"   ❌ Error: {response.status_code}")
            results.append({
                "query": query,
                "expected": expected_intent,
                "actual": "ERROR",
                "match": False
            })

    # Summary
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)

    correct = sum(1 for r in results if r["match"])
    total = len(results)

    print(f"\n✅ Correct: {correct}/{total} ({correct/total*100:.1f}%)")

    for r in results:
        status = "✅" if r["match"] else "❌"
        print(f"{status} {r['query'][:50]:50} | Expected: {r['expected']:12} | Got: {r['actual']:12}")

    return correct == total


def test_csv_query_responses():
    """Test the actual LLM responses for CSV data"""
    print("\n" + "="*80)
    print("TEST 3: CSV Query Response Quality")
    print("="*80)

    csv_queries = [
        "Who is the latest committer?",
        "Show me the top 3 contributors",
        "How many commits are there?",
        "What are the latest issues?",
    ]

    for query in csv_queries:
        print(f"\n🔍 Query: '{query}'")

        response = requests.post(
            f"{BASE_URL}/query",
            json={
                "project_id": "apache-incubator-resilientdb",
                "query": query,
                "max_results": 5
            }
        )

        if response.status_code == 200:
            data = response.json()
            print(f"   💬 Response:")
            print(f"   {data['response']}")
            print(f"\n   📋 Sources: {len(data.get('sources', []))} citations")

            for i, source in enumerate(data.get('sources', [])[:3]):
                print(f"      {i+1}. {source.get('file_path', 'N/A')}: {source.get('content', 'N/A')[:80]}")

            print(f"\n   ⏱️  Generation time: {data['metadata'].get('generation_time_ms', 0):.0f}ms")
        else:
            print(f"   ❌ Error: {response.status_code}")


def main():
    """Run all tests"""
    print("\n" + "🚀"*40)
    print("MULTI-MODAL RAG - END-TO-END API TEST")
    print("🚀"*40)

    try:
        # Test 1: Load CSV data
        csv_loaded = test_load_csv_data()

        if not csv_loaded:
            print("\n❌ CSV loading failed. Cannot proceed with further tests.")
            return

        # Test 2: Intent routing
        intent_test_passed = test_query_intent_routing()

        # Test 3: Response quality
        test_csv_query_responses()

        # Final summary
        print("\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)

        if csv_loaded and intent_test_passed:
            print("\n✅ All tests PASSED!")
            print("   - CSV data loaded successfully")
            print("   - Intent routing working correctly")
            print("   - Multi-modal RAG system operational")
        else:
            print("\n⚠️  Some tests failed. See details above.")

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API server.")
        print("   Make sure the backend is running on http://localhost:8000")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
