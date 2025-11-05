"""
End-to-End Integration Test for OSS Scraper + RAG System

Tests:
1. Intent routing accuracy
2. Project scraping and indexing
3. Query handling for issues, PRs, commits, and graph data
"""
import asyncio
import httpx
import sys
from typing import Dict, List
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

BASE_URL = "http://localhost:8000"

# Test queries with expected intents
INTENT_TEST_CASES = [
    ("How do I contribute to this project?", "governance"),
    ("What are the pull request guidelines?", "governance"),
    ("Who worked on the authentication module?", "code_collaboration"),
    ("Show me the most active developers", "code_collaboration"),
    ("What is the project's sustainability forecast?", "sustainability"),
    ("List open issues for bug fixes", "governance"),  # Issues are indexed in governance context
    ("Who collaborated with Edward on Matrix.java?", "code_collaboration"),
    ("What files did developer X commit recently?", "code_collaboration"),
    ("Recommend best practices for contributing", "recommendations"),
]

# Small test repo (use a repo with few issues/PRs for quick testing)
TEST_REPO = {
    "github_url": "https://github.com/resilientdb/resilientdb",
    "expected_project_id": "resilientdb-resilientdb"
}

# Query test cases after scraping
QUERY_TEST_CASES = [
    {
        "query": "What issues are open for bug fixes?",
        "expected_type": "issue",
        "description": "Test issue retrieval from RAG"
    },
    {
        "query": "Who worked on the consensus module?",
        "expected_type": "code_collaboration",
        "description": "Test Graph RAG developer queries"
    },
    {
        "query": "Show me recent pull requests",
        "expected_type": "pull_request",
        "description": "Test PR retrieval from RAG"
    }
]


async def test_intent_routing():
    """Test 1: Verify intent routing accuracy"""
    logger.info("=" * 60)
    logger.info("TEST 1: Intent Routing Accuracy")
    logger.info("=" * 60)

    correct = 0
    total = len(INTENT_TEST_CASES)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for query, expected_intent in INTENT_TEST_CASES:
            try:
                # Note: This assumes there's an intent endpoint. If not, we test through /api/query
                response = await client.post(
                    f"{BASE_URL}/api/query",
                    json={"query": query, "project_id": "demo"}
                )

                if response.status_code == 200:
                    result = response.json()
                    # Check if intent is in metadata
                    actual_intent = result.get("metadata", {}).get("intent", "unknown")

                    if expected_intent in actual_intent or actual_intent in expected_intent:
                        logger.success(f"✓ '{query[:50]}...' → {actual_intent}")
                        correct += 1
                    else:
                        logger.warning(f"✗ '{query[:50]}...' → Expected: {expected_intent}, Got: {actual_intent}")
                else:
                    logger.error(f"✗ '{query[:50]}...' → HTTP {response.status_code}")

            except Exception as e:
                logger.error(f"✗ '{query[:50]}...' → Error: {e}")

    accuracy = (correct / total) * 100
    logger.info(f"\nIntent Routing Accuracy: {accuracy:.1f}% ({correct}/{total})")

    if accuracy >= 80:
        logger.success(f"✓ PASSED: Accuracy >= 80% target")
    else:
        logger.warning(f"⚠ FAILED: Accuracy {accuracy:.1f}% < 80% target")

    return accuracy >= 80


async def test_project_scraping():
    """Test 2: Add project and verify scraping/indexing"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Project Scraping & Indexing")
    logger.info("=" * 60)

    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 min timeout for scraping
        try:
            logger.info(f"Adding project: {TEST_REPO['github_url']}")
            logger.info("This may take 1-3 minutes...")

            response = await client.post(
                f"{BASE_URL}/api/projects/add",
                json={"github_url": TEST_REPO["github_url"]}
            )

            if response.status_code == 200:
                result = response.json()

                # Verify response structure
                if result.get("status") == "success":
                    logger.success(f"✓ Project added successfully")

                    # Check indexing results
                    indexing = result.get("indexing", {})

                    gov_indexed = indexing.get("governance", {}).get("indexed", 0)
                    logger.info(f"  - Governance docs indexed: {gov_indexed}")

                    socio_tech = indexing.get("socio_technical", {})
                    issues_indexed = socio_tech.get("issues_indexed", 0)
                    prs_indexed = socio_tech.get("prs_indexed", 0)
                    commits_indexed = socio_tech.get("commits_indexed", 0)

                    logger.info(f"  - Issues indexed: {issues_indexed}")
                    logger.info(f"  - PRs indexed: {prs_indexed}")
                    logger.info(f"  - Commits indexed: {commits_indexed}")

                    graph_loaded = indexing.get("graph_loaded", False)
                    logger.info(f"  - Graph RAG loaded: {graph_loaded}")

                    # Verify at least some data was indexed
                    total_indexed = gov_indexed + issues_indexed + prs_indexed + commits_indexed

                    if total_indexed > 0:
                        logger.success(f"✓ PASSED: {total_indexed} total documents indexed")
                        return True, result
                    else:
                        logger.error(f"✗ FAILED: No documents indexed")
                        return False, result
                else:
                    logger.error(f"✗ FAILED: {result.get('message', 'Unknown error')}")
                    return False, result
            else:
                logger.error(f"✗ FAILED: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False, None

        except Exception as e:
            logger.error(f"✗ FAILED: {e}")
            return False, None


async def test_querying():
    """Test 3: Query indexed data"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Querying Indexed Data")
    logger.info("=" * 60)

    passed = 0
    total = len(QUERY_TEST_CASES)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in QUERY_TEST_CASES:
            query = test_case["query"]
            expected_type = test_case["expected_type"]
            description = test_case["description"]

            try:
                logger.info(f"\n{description}")
                logger.info(f"Query: '{query}'")

                response = await client.post(
                    f"{BASE_URL}/api/query",
                    json={
                        "query": query,
                        "project_id": TEST_REPO["expected_project_id"]
                    }
                )

                if response.status_code == 200:
                    result = response.json()

                    # Check if response contains relevant data
                    has_response = len(result.get("response", "")) > 50
                    has_sources = len(result.get("sources", [])) > 0

                    if has_response and has_sources:
                        logger.success(f"✓ Got response with {len(result.get('sources', []))} sources")
                        logger.info(f"  Preview: {result['response'][:100]}...")
                        passed += 1
                    elif has_response:
                        logger.warning(f"⚠ Got response but no sources")
                        logger.info(f"  Preview: {result['response'][:100]}...")
                    else:
                        logger.warning(f"✗ Empty or invalid response")
                else:
                    logger.error(f"✗ HTTP {response.status_code}")

            except Exception as e:
                logger.error(f"✗ Error: {e}")

    logger.info(f"\nQuery Tests: {passed}/{total} passed")
    return passed >= (total * 0.7)  # 70% pass rate


async def run_all_tests():
    """Run all integration tests"""
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 10 + "OSSPREY INTEGRATION TEST SUITE" + " " * 17 + "║")
    logger.info("╚" + "═" * 58 + "╝")

    results = {
        "intent_routing": False,
        "project_scraping": False,
        "querying": False
    }

    # Test 1: Intent Routing
    try:
        results["intent_routing"] = await test_intent_routing()
    except Exception as e:
        logger.error(f"Intent routing test failed: {e}")

    # Test 2: Project Scraping (may take a while)
    try:
        success, data = await test_project_scraping()
        results["project_scraping"] = success
    except Exception as e:
        logger.error(f"Project scraping test failed: {e}")

    # Test 3: Querying (only if scraping succeeded)
    if results["project_scraping"]:
        try:
            results["querying"] = await test_querying()
        except Exception as e:
            logger.error(f"Querying test failed: {e}")
    else:
        logger.warning("Skipping query tests (scraping failed)")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")

    total_passed = sum(results.values())
    total_tests = len(results)

    logger.info(f"\nOverall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        logger.success("\n🎉 ALL TESTS PASSED! Integration is complete.")
    elif total_passed >= 2:
        logger.warning(f"\n⚠ {total_passed}/{total_tests} tests passed. Review failures above.")
    else:
        logger.error("\n❌ INTEGRATION FAILED. Please review errors above.")

    return total_passed == total_tests


if __name__ == "__main__":
    # Check if backend is running
    try:
        import httpx
        response = httpx.get(f"{BASE_URL}/", timeout=5.0)
        if response.status_code != 200:
            logger.error(f"Backend check failed: {response.status_code}")
            logger.error("Please ensure the backend is running on http://localhost:8000")
            sys.exit(1)
        logger.info(f"Backend is running: {response.json().get('service', 'OSSPREY')}")
    except Exception as e:
        logger.error(f"Cannot connect to backend at {BASE_URL}")
        logger.error(f"Error: {e}")
        logger.error("\nPlease start the backend with:")
        logger.error("  cd backend && source venv/bin/activate && uvicorn app.main:app --reload")
        sys.exit(1)

    # Run tests
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
