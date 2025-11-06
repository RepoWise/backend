"""
Automated test script for ResilientDB - No interactive input required
Runs all 10 test questions and displays results for manual evaluation
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"
PROJECT_ID = "apache-incubator-resilientdb"

TEST_QUESTIONS = [
    # === GOVERNANCE (4) ===
    {
        "num": 1,
        "category": "GOVERNANCE",
        "question": "Who are the current maintainers of the ResilientDB project?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "Names/emails from MAINTAINERS.md or CONTRIBUTING.md"
    },
    {
        "num": 2,
        "category": "GOVERNANCE",
        "question": "How do I contribute code changes to ResilientDB?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "Step-by-step from CONTRIBUTING.md"
    },
    {
        "num": 3,
        "category": "GOVERNANCE",
        "question": "What is the license for ResilientDB?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "Apache 2.0"
    },
    {
        "num": 4,
        "category": "GOVERNANCE",
        "question": "What are the voting rules for ResilientDB technical decisions?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "May not be documented - should say 'not found' if missing"
    },

    # === COMMITS (3) ===
    {
        "num": 5,
        "category": "COMMITS",
        "question": "Who are the top 3 contributors by commit count?",
        "expected_intent": "COMMITS",
        "ground_truth": "1. cjcchen (3,906), 2. junchao (868), 3. Harish (459)"
    },
    {
        "num": 6,
        "category": "COMMITS",
        "question": "Show me the 5 most recent commits with author and date.",
        "expected_intent": "COMMITS",
        "ground_truth": "Latest from 2025-11-03 by cjcchen"
    },
    {
        "num": 7,
        "category": "COMMITS",
        "question": "Which files have been modified the most across all commits?",
        "expected_intent": "COMMITS",
        "ground_truth": "Aggregated filename modification counts"
    },

    # === ISSUES (3) ===
    {
        "num": 8,
        "category": "ISSUES",
        "question": "How many issues are currently open in ResilientDB?",
        "expected_intent": "ISSUES",
        "ground_truth": "53 total issues"
    },
    {
        "num": 9,
        "category": "ISSUES",
        "question": "What are the 3 most recent issues with their titles and reporters?",
        "expected_intent": "ISSUES",
        "ground_truth": "#193 (hammerface), #191 (cjcchen), #190 (DakaiKang)"
    },
    {
        "num": 10,
        "category": "ISSUES",
        "question": "Which user has opened the most issues?",
        "expected_intent": "ISSUES",
        "ground_truth": "Count by user_login from issues CSV"
    },
]


def test_all_questions():
    """Test all 10 questions and display results"""
    print("\n" + "="*100)
    print("AUTOMATED RESILIENTDB TEST - 10 QUESTIONS")
    print("="*100)

    results = []

    for test_case in TEST_QUESTIONS:
        print(f"\n{'='*100}")
        print(f"QUESTION {test_case['num']}/10: {test_case['category']}")
        print(f"{'='*100}")
        print(f"❓ {test_case['question']}")
        print(f"\n📋 Expected Intent: {test_case['expected_intent']}")
        print(f"✅ Ground Truth: {test_case['ground_truth']}")

        try:
            response = requests.post(
                f"{BASE_URL}/query",
                json={
                    "project_id": PROJECT_ID,
                    "query": test_case['question'],
                    "max_results": 5
                },
                timeout=30
            )

            if response.status_code != 200:
                print(f"\n❌ ERROR {response.status_code}: {response.text}")
                results.append({
                    "question_num": test_case['num'],
                    "category": test_case['category'],
                    "status": "ERROR",
                    "error": f"HTTP {response.status_code}"
                })
                continue

            data = response.json()

            # Extract response details
            intent = data['metadata'].get('intent', 'UNKNOWN')
            confidence = data['metadata'].get('confidence', 0)
            data_source = data['metadata'].get('data_source', 'unknown')
            response_text = data['response']
            sources = data.get('sources', [])
            generation_time = data['metadata'].get('generation_time_ms', 0)

            # Display response
            print(f"\n🎯 Actual Intent: {intent} (confidence: {confidence:.2f})")
            intent_match = "✅" if intent == test_case['expected_intent'] else "❌"
            print(f"   Intent Match: {intent_match}")
            print(f"📊 Data Source: {data_source}")
            print(f"\n💬 RESPONSE:")
            print("-" * 100)
            print(response_text)
            print("-" * 100)
            print(f"\n📚 SOURCES ({len(sources)}):")
            for i, src in enumerate(sources[:3]):
                print(f"  [{i}] {src.get('file_path', 'N/A')}")
                print(f"      {src.get('content', 'N/A')[:100]}...")
            print(f"\n⏱️  Generation time: {generation_time:.0f}ms")

            results.append({
                "question_num": test_case['num'],
                "category": test_case['category'],
                "question": test_case['question'],
                "expected_intent": test_case['expected_intent'],
                "actual_intent": intent,
                "intent_match": intent == test_case['expected_intent'],
                "confidence": confidence,
                "data_source": data_source,
                "response_preview": response_text[:200],
                "sources_count": len(sources),
                "generation_time_ms": generation_time,
                "status": "SUCCESS"
            })

        except Exception as e:
            print(f"\n❌ EXCEPTION: {str(e)}")
            results.append({
                "question_num": test_case['num'],
                "category": test_case['category'],
                "status": "ERROR",
                "error": str(e)
            })

    # Summary
    print(f"\n\n{'='*100}")
    print("TEST SUMMARY")
    print('='*100)

    total = len(results)
    intent_correct = sum(1 for r in results if r.get('intent_match', False))
    errors = sum(1 for r in results if r.get('status') == 'ERROR')

    print(f"\n📊 RESULTS:")
    print(f"   Total Questions: {total}")
    print(f"   Intent Matches: {intent_correct}/{total} ({intent_correct/total*100:.1f}%)")
    print(f"   Errors: {errors}")

    print(f"\n📋 BY CATEGORY:")
    for category in ["GOVERNANCE", "COMMITS", "ISSUES"]:
        cat_results = [r for r in results if r.get('category') == category]
        cat_correct = sum(1 for r in cat_results if r.get('intent_match', False))
        print(f"   {category:12} {cat_correct}/{len(cat_results)} intent matches")

    # Save results
    with open('test_results_automated.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: test_results_automated.json")

    print(f"\n{'='*100}")
    print("NEXT STEP: Review responses above and manually evaluate quality")
    print("="*100)


if __name__ == "__main__":
    test_all_questions()
