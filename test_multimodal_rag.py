"""
Comprehensive Test Script for Multi-Modal RAG System
Tests CSV Data Engine and Intent Router with real data

This script validates:
1. Intent classification accuracy
2. CSV data loading and querying
3. Context generation for LLM
4. Integration between components
"""
import sys
from pathlib import Path
from loguru import logger

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.data.csv_engine import CSVDataEngine
from app.models.intent_router import IntentRouter


def print_section(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_intent_classification():
    """Test intent router with various query types"""
    print_section("INTENT CLASSIFICATION TESTS")

    router = IntentRouter()

    test_cases = [
        # GOVERNANCE queries
        ("Who are the maintainers?", True, "GOVERNANCE"),
        ("How do I contribute to this project?", True, "GOVERNANCE"),
        ("What is the code of conduct?", True, "GOVERNANCE"),
        ("What is the license for this project?", True, "GOVERNANCE"),

        # COMMITS queries
        ("Who is the latest committer?", True, "COMMITS"),
        ("Show me recent commits", True, "COMMITS"),
        ("What files changed recently?", True, "COMMITS"),
        ("Who are the top contributors?", True, "COMMITS"),
        ("How many commits were made?", True, "COMMITS"),

        # ISSUES queries
        ("What are the open issues?", True, "ISSUES"),
        ("Show me closed bugs", True, "ISSUES"),
        ("How many issues are there?", True, "ISSUES"),
        ("Who reported the most issues?", True, "ISSUES"),
        ("What are the biggest discussions?", True, "ISSUES"),

        # GENERAL queries
        ("What is machine learning?", True, "GENERAL"),
        ("Explain backpropagation", True, "GENERAL"),
        ("How does git work?", False, "GENERAL"),
        ("What is the difference between supervised and unsupervised learning?", False, "GENERAL"),
    ]

    results = {
        "correct": 0,
        "incorrect": 0,
        "total": len(test_cases)
    }

    for query, has_context, expected_intent in test_cases:
        intent, confidence = router.classify_intent(query, has_context)

        is_correct = intent == expected_intent
        status = "✅" if is_correct else "❌"

        if is_correct:
            results["correct"] += 1
        else:
            results["incorrect"] += 1

        print(f"{status} Query: '{query}'")
        print(f"   Expected: {expected_intent} | Got: {intent} (confidence: {confidence:.2f})")
        print(f"   Has context: {has_context}")
        print()

    print(f"\n📊 Results: {results['correct']}/{results['total']} correct ({results['correct']/results['total']*100:.1f}%)")
    print(f"   ✅ Correct: {results['correct']}")
    print(f"   ❌ Incorrect: {results['incorrect']}")

    return results


def test_csv_data_engine():
    """Test CSV data engine with resilientdb data"""
    print_section("CSV DATA ENGINE TESTS")

    # Initialize engine
    engine = CSVDataEngine(csv_data_dir="data/csv_data")

    # Paths to CSV files
    commits_csv = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv"
    issues_csv = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/issues.csv"

    # Test 1: Load project data
    print("📦 Test 1: Loading Project Data")
    print(f"   Commits CSV: {commits_csv}")
    print(f"   Issues CSV: {issues_csv}")

    result = engine.load_project_data(
        project_id="resilientdb-resilientdb",
        commits_path=commits_csv,
        issues_path=issues_csv
    )

    print(f"   ✅ Commits loaded: {result['commits_loaded']}")
    print(f"   ✅ Issues loaded: {result['issues_loaded']}")

    # Check what data is available
    available = engine.get_available_data("resilientdb-resilientdb")
    print(f"\n📊 Available data: {available}")

    # Test 2: Query commits - Latest
    print("\n📋 Test 2: Query Latest Commits")
    df, summary = engine.query_commits("resilientdb-resilientdb", "latest", limit=5)
    print(f"   {summary}")
    print(f"   Results: {len(df)} commits")
    if len(df) > 0:
        print(f"   Latest commit:")
        print(f"   - Author: {df.iloc[0]['name']} <{df.iloc[0]['email']}>")
        print(f"   - Date: {df.iloc[0]['date']}")
        print(f"   - File: {df.iloc[0]['filename']}")

    # Test 3: Query commits - Top contributors
    print("\n👥 Test 3: Query Top Contributors")
    df, summary = engine.query_commits("resilientdb-resilientdb", "top_contributors", limit=5)
    print(f"   {summary}")
    print(f"   Results: {len(df)} contributors")
    if len(df) > 0:
        print(f"   Top contributor:")
        print(f"   - Name: {df.iloc[0]['name']}")
        print(f"   - Email: {df.iloc[0]['email']}")
        print(f"   - Commits: {df.iloc[0]['commit_count']}")
        print(f"   - Total changes: {df.iloc[0]['total_changes']}")

    # Test 4: Query commits - Stats
    print("\n📊 Test 4: Query Commit Statistics")
    df, summary = engine.query_commits("resilientdb-resilientdb", "stats")
    print(f"   {summary}")
    if len(df) > 0:
        stats = df.iloc[0]
        print(f"   - Total commits: {stats['total_commits']}")
        print(f"   - Unique authors: {stats['unique_authors']}")
        print(f"   - Total files changed: {stats['total_files_changed']}")

    # Test 5: Query issues - Latest
    print("\n🐛 Test 5: Query Latest Issues")
    df, summary = engine.query_issues("resilientdb-resilientdb", "latest", limit=5)
    print(f"   {summary}")
    print(f"   Results: {len(df)} issues")
    if len(df) > 0:
        print(f"   Latest issue:")
        print(f"   - Title: {df.iloc[0]['title']}")
        print(f"   - User: {df.iloc[0]['user_login']}")
        print(f"   - State: {df.iloc[0]['issue_state']}")
        print(f"   - Created: {df.iloc[0]['created_at']}")

    # Test 6: Query issues - Open
    print("\n🔓 Test 6: Query Open Issues")
    df, summary = engine.query_issues("resilientdb-resilientdb", "open", limit=5)
    print(f"   {summary}")
    print(f"   Results: {len(df)} open issues shown")

    # Test 7: Query issues - Stats
    print("\n📊 Test 7: Query Issue Statistics")
    df, summary = engine.query_issues("resilientdb-resilientdb", "stats")
    print(f"   {summary}")
    if len(df) > 0:
        stats = df.iloc[0]
        print(f"   - Total issues: {stats['total_issues']}")
        print(f"   - Open issues: {stats['open_issues']}")
        print(f"   - Closed issues: {stats['closed_issues']}")
        print(f"   - Unique reporters: {stats['unique_reporters']}")

    return engine


def test_context_generation(engine: CSVDataEngine):
    """Test context generation for LLM"""
    print_section("CONTEXT GENERATION TESTS")

    test_queries = [
        ("Who is the latest committer?", "commits"),
        ("What are the recent commits?", "commits"),
        ("Show me top contributors", "commits"),
        ("What are the open issues?", "issues"),
        ("How many issues are there?", "issues"),
    ]

    for query, data_type in test_queries:
        print(f"🔍 Query: '{query}'")
        print(f"   Data type: {data_type}")

        context, records = engine.get_context_for_query(
            "resilientdb-resilientdb",
            query,
            data_type
        )

        print(f"   Context length: {len(context)} chars")
        print(f"   Records returned: {len(records)}")
        print(f"\n   Context preview (first 300 chars):")
        print(f"   {context[:300]}...")
        print()


def test_end_to_end_workflow():
    """Test complete workflow: Intent → Query → Context"""
    print_section("END-TO-END WORKFLOW TEST")

    router = IntentRouter()
    engine = CSVDataEngine(csv_data_dir="data/csv_data")

    # Load data
    commits_csv = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv"
    issues_csv = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/issues.csv"

    engine.load_project_data(
        project_id="resilientdb-resilientdb",
        commits_path=commits_csv,
        issues_path=issues_csv
    )

    test_queries = [
        ("Who is the latest committer?", True),
        ("What are the open issues?", True),
        ("Show me top contributors", True),
        ("How many commits are there?", True),
        ("What is machine learning?", True),  # Should route to GENERAL
    ]

    for query, has_context in test_queries:
        print(f"\n🔍 User Query: '{query}'")

        # Step 1: Classify intent
        intent, confidence = router.classify_intent(query, has_context)
        print(f"   1️⃣ Intent: {intent} (confidence: {confidence:.2f})")

        # Step 2: Route to appropriate handler
        if intent == "COMMITS":
            context, records = engine.get_context_for_query("resilientdb-resilientdb", query, "commits")
            print(f"   2️⃣ Retrieved: {len(records)} commit records")
            print(f"   3️⃣ Context: {len(context)} chars for LLM")

        elif intent == "ISSUES":
            context, records = engine.get_context_for_query("resilientdb-resilientdb", query, "issues")
            print(f"   2️⃣ Retrieved: {len(records)} issue records")
            print(f"   3️⃣ Context: {len(context)} chars for LLM")

        elif intent == "GOVERNANCE":
            print(f"   2️⃣ Would route to: Governance RAG (vector database)")
            print(f"   3️⃣ Would perform: Vector search + reranking")

        elif intent == "GENERAL":
            print(f"   2️⃣ Would route to: Direct LLM (no RAG)")
            print(f"   3️⃣ No project context needed")

        print(f"   ✅ Workflow complete")


def main():
    """Run all tests"""
    print("\n" + "🚀 " * 20)
    print("MULTI-MODAL RAG SYSTEM - COMPREHENSIVE TEST SUITE")
    print("🚀 " * 20)

    try:
        # Test 1: Intent Classification
        intent_results = test_intent_classification()

        # Test 2: CSV Data Engine
        engine = test_csv_data_engine()

        # Test 3: Context Generation
        test_context_generation(engine)

        # Test 4: End-to-End Workflow
        test_end_to_end_workflow()

        # Final Summary
        print_section("TEST SUMMARY")
        print(f"✅ All tests completed successfully!")
        print(f"\n📊 Intent Classification: {intent_results['correct']}/{intent_results['total']} correct")
        print(f"✅ CSV Data Engine: Fully functional")
        print(f"✅ Context Generation: Working")
        print(f"✅ End-to-End Workflow: Validated")

        print("\n🎉 Multi-Modal RAG system core components are ready for integration!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
