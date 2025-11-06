"""
Test suite for keras-io project covering governance, commits, and issues
"""
import requests
import json
import time

API_URL = "http://localhost:8000/api/query"
PROJECT_ID = "keras-team-keras-io"

# Test questions covering all three intents
QUESTIONS = [
    # GOVERNANCE intent
    {"id": "G1", "query": "Who maintains this project?", "type": "GOVERNANCE"},
    {"id": "G2", "query": "How do I contribute to keras-io?", "type": "GOVERNANCE"},
    {"id": "G3", "query": "What is the code of conduct?", "type": "GOVERNANCE"},
    {"id": "G4", "query": "How do I report a security vulnerability?", "type": "GOVERNANCE"},

    # COMMITS intent
    {"id": "C1", "query": "Who are the top 5 most active committers?", "type": "COMMITS"},
    {"id": "C2", "query": "What are the latest 3 commits?", "type": "COMMITS"},
    {"id": "C3", "query": "Which files have been modified most frequently?", "type": "COMMITS"},

    # ISSUES intent
    {"id": "I1", "query": "How many open issues are there?", "type": "ISSUES"},
    {"id": "I2", "query": "What are the 5 most recently created issues?", "type": "ISSUES"},
    {"id": "I3", "query": "Which issues have the most comments?", "type": "ISSUES"},
]

def test_question(question):
    """Test a single question"""
    print(f"\n{'='*80}")
    print(f"{question['id']} ({question['type']}): {question['query']}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        response = requests.post(
            API_URL,
            json={"query": question["query"], "project_id": PROJECT_ID},
            timeout=60
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "")
            metadata = data.get("metadata", {})

            print(f"\n✅ SUCCESS ({elapsed:.1f}s)")
            print(f"\nAnswer ({len(answer)} chars):")
            print(f"{answer[:500]}{'...' if len(answer) > 500 else ''}")

            print(f"\nMetadata:")
            print(f"  - Intent: {metadata.get('intent', 'N/A')}")
            print(f"  - Data Source: {metadata.get('data_source', 'N/A')}")
            print(f"  - Generation Time: {metadata.get('generation_time_ms', 0)/1000:.1f}s")

            # Verify intent matches expectation
            if metadata.get('intent') == question['type']:
                print(f"  ✅ Intent classification correct!")
            else:
                print(f"  ⚠️  Expected {question['type']}, got {metadata.get('intent')}")

            return "PASS"
        else:
            print(f"\n❌ FAILED with status {response.status_code}")
            print(f"Error: {response.text}")
            return "FAIL"

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        return "ERROR"

def main():
    print("\n" + "="*80)
    print("TESTING KERAS-IO PROJECT")
    print("="*80)
    print(f"Project ID: {PROJECT_ID}")
    print(f"Total test questions: {len(QUESTIONS)}")

    results = {}

    for question in QUESTIONS:
        result = test_question(question)
        results[question["id"]] = result
        time.sleep(1)  # Brief pause between requests

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(1 for r in results.values() if r == "PASS")
    failed = sum(1 for r in results.values() if r == "FAIL")
    errors = sum(1 for r in results.values() if r == "ERROR")

    for qid, result in results.items():
        status_emoji = "✅" if result == "PASS" else "❌"
        print(f"{status_emoji} {qid}: {result}")

    print(f"\nTotal: {len(results)} questions")
    print(f"✅ Passed: {passed}/{len(results)} ({passed/len(results)*100:.0f}%)")
    if failed > 0:
        print(f"❌ Failed: {failed}")
    if errors > 0:
        print(f"⚠️  Errors: {errors}")

if __name__ == "__main__":
    main()
