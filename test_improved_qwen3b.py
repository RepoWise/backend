"""
Test suite for improved qwen2.5:3b model with anti-hallucination prompting
"""
import requests
import json
import time

API_URL = "http://localhost:8000/api/query"
PROJECT_ID = "resilientdb-incubator-resilientdb"

# Test questions covering governance, commits, and issues
QUESTIONS = [
    {"id": "Q1", "query": "Who currently maintains this project?", "type": "GOVERNANCE"},
    {"id": "Q2", "query": "What are the voting rules for changes?", "type": "GOVERNANCE"},
    {"id": "Q3", "query": "What are the required steps before submitting a pull request?", "type": "GOVERNANCE"},
    {"id": "Q4", "query": "How do I report a security vulnerability?", "type": "GOVERNANCE"},
    {"id": "Q5", "query": "Who are the three most active committers?", "type": "COMMITS"},
    {"id": "Q6", "query": "What are the five latest commits?", "type": "COMMITS"},
    {"id": "Q7", "query": "Which files have the highest total lines added across all commits?", "type": "COMMITS"},
    {"id": "Q8", "query": "How many open vs closed issues are there?", "type": "ISSUES"},
    {"id": "Q9", "query": "What are the three most recently updated issues?", "type": "ISSUES"},
    {"id": "Q10", "query": "Which issue has the highest comment count?", "type": "ISSUES"},
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
            print(f"{answer}")

            print(f"\nMetadata:")
            print(f"  - Model: {metadata.get('llm_model', 'N/A')}")
            print(f"  - Intent: {metadata.get('intent', 'N/A')}")
            print(f"  - Data Source: {metadata.get('data_source', 'N/A')}")
            print(f"  - Generation Time: {metadata.get('generation_time_ms', 0)/1000:.1f}s")

            # Check for hallucination indicators
            hallucination_indicators = [
                ("typically", "hedging word"),
                ("usually", "hedging word"),
                ("commonly", "hedging word"),
                ("based on general", "general knowledge"),
                ("it's likely", "speculation"),
                ("may involve", "speculation"),
            ]

            found_indicators = []
            answer_lower = answer.lower()
            for indicator, reason in hallucination_indicators:
                if indicator in answer_lower:
                    found_indicators.append(f"{indicator} ({reason})")

            if found_indicators:
                print(f"\n⚠️  Potential hallucination indicators found:")
                for ind in found_indicators:
                    print(f"     - {ind}")

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
    print("TESTING IMPROVED qwen2.5:3b MODEL WITH ANTI-HALLUCINATION PROMPTING")
    print("="*80)

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
