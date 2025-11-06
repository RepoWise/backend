"""
Refined 10-Question Test Suite for ResilientDB
More specific and challenging questions to properly evaluate the system
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"
PROJECT_ID = "apache-incubator-resilientdb"

REFINED_QUESTIONS = [
    # === GOVERNANCE (4) ===
    {
        "num": 1,
        "category": "GOVERNANCE",
        "question": "Who currently maintains the ResilientDB incubator project, and how can contributors contact them?",
        "ground_truth": "Names/emails from MAINTAINERS.md or CONTRIBUTING.md with contact info"
    },
    {
        "num": 2,
        "category": "GOVERNANCE",
        "question": "What are the voting rules for technical decisions in ResilientDB's governance policy?",
        "ground_truth": "Should admit if not documented (likely not in governance docs)"
    },
    {
        "num": 3,
        "category": "GOVERNANCE",
        "question": "Describe the required steps before submitting a substantial code change to ResilientDB.",
        "ground_truth": "Fork, branch, PR process from CONTRIBUTING.md"
    },
    {
        "num": 4,
        "category": "GOVERNANCE",
        "question": "What security reporting process does ResilientDB require if a vulnerability is found?",
        "ground_truth": "Security policy from SECURITY.md or CODE_OF_CONDUCT.md"
    },

    # === COMMITS (3) ===
    {
        "num": 5,
        "category": "COMMITS",
        "question": "List the three most active committers in ResilientDB over the entire dataset and their commit counts.",
        "ground_truth": "1. cjcchen (3,906), 2. junchao (868), 3. Harish (459)"
    },
    {
        "num": 6,
        "category": "COMMITS",
        "question": "Show the five latest commits with author, date, and primary file touched.",
        "ground_truth": "Latest 5 from 2025-11-03 by cjcchen with filenames"
    },
    {
        "num": 7,
        "category": "COMMITS",
        "question": "Which files have the highest total lines added across all commits?",
        "ground_truth": "Aggregated lines_added by filename"
    },

    # === ISSUES (3) ===
    {
        "num": 8,
        "category": "ISSUES",
        "question": "How many ResilientDB issues are currently open versus closed, and who opened the most?",
        "ground_truth": "Total count + open/closed split + top reporter"
    },
    {
        "num": 9,
        "category": "ISSUES",
        "question": "What are the three most recently updated issues, including their states and reporters?",
        "ground_truth": "Latest 3 by updated_at with states"
    },
    {
        "num": 10,
        "category": "ISSUES",
        "question": "Which issue has the highest comment count, and what is its current status?",
        "ground_truth": "Issue with most comments + its state"
    },
]


def test_question(test_case):
    """Test a single refined question"""
    print(f"\n{'='*100}")
    print(f"Q{test_case['num']}: {test_case['category']}")
    print(f"{'='*100}")
    print(f"❓ {test_case['question']}")
    print(f"\n✅ Ground Truth: {test_case['ground_truth']}")

    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/query",
            json={
                "project_id": PROJECT_ID,
                "query": test_case['question'],
                "max_results": 5
            },
            timeout=30
        )
        elapsed = (time.time() - start_time) * 1000

        if response.status_code != 200:
            print(f"\n❌ ERROR {response.status_code}: {response.text}")
            return {"status": "ERROR", "question_num": test_case['num']}

        data = response.json()

        # Extract response details
        intent = data['metadata'].get('intent', 'UNKNOWN')
        confidence = data['metadata'].get('confidence', 0)
        data_source = data['metadata'].get('data_source', 'unknown')
        response_text = data['response']
        sources = data.get('sources', [])
        generation_time = data['metadata'].get('generation_time_ms', 0)

        # Display
        print(f"\n🎯 Intent: {intent} (confidence: {confidence:.2f})")
        print(f"📊 Data Source: {data_source}")
        print(f"\n💬 RESPONSE:")
        print("-" * 100)
        print(response_text)
        print("-" * 100)

        if sources:
            print(f"\n📚 SOURCES ({len(sources)}):")
            for i, src in enumerate(sources[:3]):
                content_preview = src.get('content', 'N/A')
                if content_preview != 'N/A':
                    content_preview = content_preview[:100] + "..."
                print(f"  [{i}] {src.get('file_path', 'N/A')}")
                print(f"      {content_preview}")

        print(f"\n⏱️  Response time: {elapsed:.0f}ms (LLM: {generation_time:.0f}ms)")

        return {
            "question_num": test_case['num'],
            "category": test_case['category'],
            "intent": intent,
            "data_source": data_source,
            "response_length": len(response_text),
            "sources_count": len(sources),
            "response_time_ms": elapsed,
            "llm_time_ms": generation_time,
            "status": "SUCCESS"
        }

    except Exception as e:
        print(f"\n❌ EXCEPTION: {str(e)}")
        return {"status": "ERROR", "question_num": test_case['num'], "error": str(e)}


def main():
    print("\n" + "🔬 " * 40)
    print("REFINED 10-QUESTION TEST SUITE - RESILIENTDB")
    print("🔬 " * 40)
    print(f"\nTarget: {BASE_URL}")
    print(f"Project: {PROJECT_ID}")
    print(f"Questions: {len(REFINED_QUESTIONS)}\n")

    results = []

    for test_case in REFINED_QUESTIONS:
        result = test_question(test_case)
        results.append(result)
        time.sleep(0.5)  # Small delay between requests

    # Summary
    print(f"\n\n{'='*100}")
    print("TEST SUMMARY")
    print('='*100)

    successful = [r for r in results if r.get('status') == 'SUCCESS']
    errors = [r for r in results if r.get('status') == 'ERROR']

    print(f"\n📊 RESULTS:")
    print(f"   Total Questions: {len(results)}")
    print(f"   Successful: {len(successful)}")
    print(f"   Errors: {len(errors)}")

    if successful:
        avg_response_time = sum(r.get('response_time_ms', 0) for r in successful) / len(successful)
        avg_llm_time = sum(r.get('llm_time_ms', 0) for r in successful) / len(successful)
        print(f"\n⏱️  PERFORMANCE:")
        print(f"   Avg Response Time: {avg_response_time:.0f}ms")
        print(f"   Avg LLM Time: {avg_llm_time:.0f}ms")

    print(f"\n📋 BY CATEGORY:")
    for category in ["GOVERNANCE", "COMMITS", "ISSUES"]:
        cat_results = [r for r in successful if r.get('category') == category]
        print(f"   {category:12} {len(cat_results)} successful")

    # Save results
    with open('test_results_refined.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: test_results_refined.json")
    print(f"\n{'='*100}")
    print("MANUAL EVALUATION: Review responses above for accuracy")
    print('='*100)


if __name__ == "__main__":
    main()
