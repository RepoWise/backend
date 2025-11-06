"""
ResilientDB 10-Question Test Suite
Tests governance, commits, and issues queries with ground truth validation
"""
import requests
import json
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8000/api"
PROJECT_ID = "apache-incubator-resilientdb"

# Test questions with expected ground truth
TEST_QUESTIONS = [
    # === GOVERNANCE (4) ===
    {
        "category": "GOVERNANCE",
        "question": "Who are the current maintainers of the ResilientDB project?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "Should extract names/emails from MAINTAINERS.md or CONTRIBUTING.md",
        "evaluation_criteria": [
            "All names must appear verbatim in governance docs",
            "No hallucinated names",
            "Includes contact information if available"
        ]
    },
    {
        "category": "GOVERNANCE",
        "question": "How do I contribute code changes to ResilientDB?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "Step-by-step process from CONTRIBUTING.md",
        "evaluation_criteria": [
            "Mentions fork/branch workflow",
            "Describes PR process",
            "Cites CONTRIBUTING.md"
        ]
    },
    {
        "category": "GOVERNANCE",
        "question": "What is the license for ResilientDB?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "Apache 2.0",
        "evaluation_criteria": [
            "Correct license type",
            "References LICENSE file"
        ]
    },
    {
        "category": "GOVERNANCE",
        "question": "What are the voting rules for ResilientDB technical decisions?",
        "expected_intent": "GOVERNANCE",
        "ground_truth": "May not be documented - should say 'not found' if missing",
        "evaluation_criteria": [
            "Admits if information not available",
            "Doesn't invent governance rules"
        ]
    },

    # === COMMITS (3) ===
    {
        "category": "COMMITS",
        "question": "Who are the top 3 contributors by commit count?",
        "expected_intent": "COMMITS",
        "ground_truth": "1. cjcchen (3,906), 2. junchao (868), 3. Harish (459)",
        "evaluation_criteria": [
            "Exact names match CSV",
            "Commit counts are accurate",
            "Ranked in correct order"
        ]
    },
    {
        "category": "COMMITS",
        "question": "Show me the 5 most recent commits with author and date.",
        "expected_intent": "COMMITS",
        "ground_truth": "Latest from 2025-11-03 by cjcchen",
        "evaluation_criteria": [
            "Correct chronological order",
            "Dates match CSV (2025-11-03)",
            "Author names correct",
            "Includes commit SHA or filename"
        ]
    },
    {
        "category": "COMMITS",
        "question": "Which files have been modified the most across all commits?",
        "expected_intent": "COMMITS",
        "ground_truth": "Aggregated filename modification counts",
        "evaluation_criteria": [
            "Lists actual filenames from CSV",
            "Ranked by frequency",
            "No invented files"
        ]
    },

    # === ISSUES (3) ===
    {
        "category": "ISSUES",
        "question": "How many issues are currently open in ResilientDB?",
        "expected_intent": "ISSUES",
        "ground_truth": "53 total issues (check state distribution)",
        "evaluation_criteria": [
            "Total count is 53",
            "Distinguishes open vs closed if possible",
            "Admits if state data unavailable"
        ]
    },
    {
        "category": "ISSUES",
        "question": "What are the 3 most recent issues with their titles and reporters?",
        "expected_intent": "ISSUES",
        "ground_truth": "#193 (hammerface), #191 (cjcchen), #190 (DakaiKang)",
        "evaluation_criteria": [
            "Correct issue numbers",
            "Accurate titles",
            "Correct reporters",
            "Most recent first"
        ]
    },
    {
        "category": "ISSUES",
        "question": "Which user has opened the most issues?",
        "expected_intent": "ISSUES",
        "ground_truth": "Count by user_login from issues CSV",
        "evaluation_criteria": [
            "Identifies top reporter",
            "Provides count",
            "Based on CSV data"
        ]
    },
]


def test_query(test_case: Dict, question_num: int) -> Dict:
    """
    Test a single query and evaluate response

    Returns:
        Result dict with scores and evaluation
    """
    print(f"\n{'='*100}")
    print(f"QUESTION {question_num}/10: {test_case['category']}")
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
            return {
                "question_num": question_num,
                "category": test_case['category'],
                "question": test_case['question'],
                "status": "ERROR",
                "score": 0,
                "notes": f"HTTP {response.status_code}"
            }

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
        print(f"📊 Data Source: {data_source}")
        print(f"\n💬 RESPONSE:")
        print("-" * 100)
        print(response_text)
        print("-" * 100)
        print(f"\n📚 SOURCES ({len(sources)}):")
        for i, src in enumerate(sources[:5]):
            print(f"  [{i}] {src.get('file_path', 'N/A')}")
            print(f"      {src.get('content', 'N/A')[:120]}")
        print(f"\n⏱️  Generation time: {generation_time:.0f}ms")

        # Manual evaluation
        print(f"\n🔍 EVALUATION CRITERIA:")
        for i, criterion in enumerate(test_case['evaluation_criteria'], 1):
            print(f"  {i}. {criterion}")

        print(f"\n{'='*100}")
        print("MANUAL SCORING (0-5 points)")
        print("  5 = Perfect (intent correct, answer accurate, well-cited)")
        print("  4 = Good (minor issues)")
        print("  3 = Fair (some inaccuracies)")
        print("  2 = Poor (wrong intent or major errors)")
        print("  1 = Very Poor (hallucinations)")
        print("  0 = Failure (error or completely wrong)")
        print("="*100)

        while True:
            try:
                score_input = input("\n👉 Enter score (0-5): ").strip()
                score = int(score_input)
                if 0 <= score <= 5:
                    break
                print("   ⚠️  Please enter a number between 0 and 5")
            except ValueError:
                print("   ⚠️  Please enter a valid number")

        notes = input("📝 Notes (optional, press Enter to skip): ").strip()

        result = {
            "question_num": question_num,
            "category": test_case['category'],
            "question": test_case['question'],
            "expected_intent": test_case['expected_intent'],
            "actual_intent": intent,
            "confidence": confidence,
            "data_source": data_source,
            "response_preview": response_text[:200],
            "sources_count": len(sources),
            "generation_time_ms": generation_time,
            "score": score,
            "status": "PASS" if score >= 4 else "REVIEW" if score >= 2 else "FAIL",
            "notes": notes or ""
        }

        return result

    except requests.exceptions.Timeout:
        print(f"\n⏱️  TIMEOUT: Query took longer than 30 seconds")
        return {
            "question_num": question_num,
            "category": test_case['category'],
            "question": test_case['question'],
            "status": "TIMEOUT",
            "score": 0,
            "notes": "Request timeout"
        }
    except Exception as e:
        print(f"\n❌ EXCEPTION: {str(e)}")
        return {
            "question_num": question_num,
            "category": test_case['category'],
            "question": test_case['question'],
            "status": "ERROR",
            "score": 0,
            "notes": str(e)
        }


def print_summary(results: List[Dict]):
    """Print comprehensive test summary"""
    print(f"\n\n{'='*100}")
    print("FINAL TEST SUMMARY")
    print('='*100)

    # Overall statistics
    total = len(results)
    total_score = sum(r['score'] for r in results)
    max_score = total * 5
    avg_score = total_score / total if total > 0 else 0
    percentage = (total_score / max_score * 100) if max_score > 0 else 0

    passed = sum(1 for r in results if r['status'] == 'PASS')
    needs_review = sum(1 for r in results if r['status'] == 'REVIEW')
    failed = sum(1 for r in results if r['status'] == 'FAIL')

    print(f"\n📊 OVERALL RESULTS:")
    print(f"   Total Score: {total_score}/{max_score} ({percentage:.1f}%)")
    print(f"   Average Score: {avg_score:.2f}/5")
    print(f"   ✅ Passed (4-5): {passed}/{total}")
    print(f"   ⚠️  Needs Review (2-3): {needs_review}/{total}")
    print(f"   ❌ Failed (0-1): {failed}/{total}")

    # By category
    print(f"\n📋 BY CATEGORY:")
    for category in ["GOVERNANCE", "COMMITS", "ISSUES"]:
        cat_results = [r for r in results if r.get('category') == category]
        if cat_results:
            cat_score = sum(r['score'] for r in cat_results)
            cat_max = len(cat_results) * 5
            cat_pct = (cat_score / cat_max * 100) if cat_max > 0 else 0
            print(f"   {category:12} {cat_score:2}/{cat_max} ({cat_pct:5.1f}%)")

    # Detailed results
    print(f"\n📝 DETAILED RESULTS:")
    print(f"{'#':<3} {'Category':<12} {'Score':<7} {'Status':<10} {'Intent':<12} {'Question':<50}")
    print("-" * 100)
    for r in results:
        status_icon = "✅" if r['status'] == 'PASS' else "⚠️" if r['status'] == 'REVIEW' else "❌"
        intent_match = "✓" if r.get('actual_intent') == r.get('expected_intent') else "✗"
        print(f"{r['question_num']:<3} {r['category']:<12} {r['score']}/5    "
              f"{status_icon} {r['status']:<7} {intent_match} {r.get('actual_intent', 'N/A'):<10} "
              f"{r['question'][:47]}")

    # Notes
    print(f"\n💬 NOTES:")
    for r in results:
        if r.get('notes'):
            print(f"   Q{r['question_num']}: {r['notes']}")

    # Recommendation
    print(f"\n{'='*100}")
    if percentage >= 80:
        print("🎉 EXCELLENT! System is ready for multi-project scaling.")
    elif percentage >= 60:
        print("✅ GOOD! Minor improvements needed. Review failed questions.")
    elif percentage >= 40:
        print("⚠️  FAIR. Significant prompt or model tuning required.")
    else:
        print("❌ NEEDS WORK. Consider switching LLM or major prompt overhaul.")
    print('='*100)

    # Save results
    with open('test_results_resilientdb.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: test_results_resilientdb.json")


def main():
    print("\n" + "🚀 " * 40)
    print("ResilientDB 10-Question Test Suite")
    print("🚀 " * 40)
    print(f"\nTarget API: {BASE_URL}")
    print(f"Project: {PROJECT_ID}")
    print(f"Questions: {len(TEST_QUESTIONS)}")
    print("\nThis will test governance, commits, and issues queries.")
    print("You'll manually score each response 0-5 based on accuracy.")
    print("\nPress Ctrl+C to abort at any time.\n")

    input("Press Enter to start testing...")

    results = []

    for i, test_case in enumerate(TEST_QUESTIONS, 1):
        result = test_query(test_case, i)
        results.append(result)

        if i < len(TEST_QUESTIONS):
            continue_test = input(f"\n[{i}/{len(TEST_QUESTIONS)} complete] Continue? (Y/n): ").strip().lower()
            if continue_test == 'n':
                print("\n⚠️  Testing aborted by user.")
                break

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
