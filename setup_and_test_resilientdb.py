"""
Setup and Test Script for ResilientDB Single-Project Demo
Tests all 10 refined questions (4 governance + 3 commits + 3 issues)
"""
import requests
import json
import time
from typing import Dict, List

API_BASE = "http://localhost:8000"
PROJECT_ID = "resilientdb-incubator-resilientdb"

# CSV file paths
COMMITS_CSV = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv"
ISSUES_CSV = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/issues.csv"

# 10 Test Questions
TEST_QUESTIONS = [
    # Governance (4)
    {
        "id": "Q1",
        "type": "GOVERNANCE",
        "question": "Who currently maintains the ResilientDB incubator project, and how can contributors contact them?",
        "expected_keywords": ["maintain", "contact", "contributor"]
    },
    {
        "id": "Q2",
        "type": "GOVERNANCE",
        "question": "What are the voting rules for technical decisions in ResilientDB's governance policy?",
        "expected_keywords": ["voting", "decision", "consensus"]
    },
    {
        "id": "Q3",
        "type": "GOVERNANCE",
        "question": "Describe the required steps before submitting a substantial code change to ResilientDB.",
        "expected_keywords": ["submit", "code", "change", "pull request"]
    },
    {
        "id": "Q4",
        "type": "GOVERNANCE",
        "question": "What security reporting process does ResilientDB require if a vulnerability is found?",
        "expected_keywords": ["security", "vulnerability", "report"]
    },
    # Commits (3)
    {
        "id": "Q5",
        "type": "COMMITS",
        "question": "List the three most active committers in ResilientDB over the entire dataset and their commit counts.",
        "expected_keywords": ["cjcchen", "junchao", "commits"]
    },
    {
        "id": "Q6",
        "type": "COMMITS",
        "question": "Show the five latest commits with author, date, and primary file touched.",
        "expected_keywords": ["commit", "author", "date", "file"]
    },
    {
        "id": "Q7",
        "type": "COMMITS",
        "question": "Which files have the highest total lines added across all commits?",
        "expected_keywords": ["file", "lines", "added"]
    },
    # Issues (3)
    {
        "id": "Q8",
        "type": "ISSUES",
        "question": "How many ResilientDB issues are currently open versus closed, and who opened the most?",
        "expected_keywords": ["open", "closed", "issues"]
    },
    {
        "id": "Q9",
        "type": "ISSUES",
        "question": "What are the three most recently updated issues, including their states and reporters?",
        "expected_keywords": ["issue", "state", "reporter"]
    },
    {
        "id": "Q10",
        "type": "ISSUES",
        "question": "Which issue has the highest comment count, and what is its current status?",
        "expected_keywords": ["comment", "issue", "status"]
    }
]


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def check_backend_health():
    """Check if backend is running"""
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend not accessible: {e}")
        return False


def check_project_status():
    """Check ResilientDB project status"""
    try:
        response = requests.get(f"{API_BASE}/api/projects/{PROJECT_ID}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Project: {data.get('name')}")
            print(f"   - Indexed: {data.get('indexed')}")
            print(f"   - Chunks: {data.get('chunk_count', 0)}")
            return True
        else:
            print(f"❌ Project not found")
            return False
    except Exception as e:
        print(f"❌ Error checking project: {e}")
        return False


def load_csv_data():
    """Load CSV data for ResilientDB"""
    print_section("Loading CSV Data")

    try:
        response = requests.post(
            f"{API_BASE}/api/projects/{PROJECT_ID}/load-csv",
            json={
                "commits_csv_path": COMMITS_CSV,
                "issues_csv_path": ISSUES_CSV
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ CSV Data Loaded:")
            print(f"   - Commits: {data.get('commits_loaded', False)}")
            print(f"   - Issues: {data.get('issues_loaded', False)}")
            return True
        else:
            print(f"❌ Failed to load CSV: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return False


def test_query(question_data: Dict) -> Dict:
    """Test a single query"""
    qid = question_data["id"]
    question = question_data["question"]

    print(f"\n{qid}: {question}")
    print("-" * 80)

    try:
        response = requests.post(
            f"{API_BASE}/api/query",
            json={
                "project_id": PROJECT_ID,
                "query": question,
                "max_results": 5
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "")
            sources = data.get("sources", [])
            intent = data.get("intent", "UNKNOWN")

            print(f"Intent: {intent}")
            print(f"\nAnswer:\n{answer[:500]}..." if len(answer) > 500 else f"\nAnswer:\n{answer}")
            print(f"\nSources: {len(sources)} documents")

            # Check if expected keywords are present
            answer_lower = answer.lower()
            keywords_found = [kw for kw in question_data["expected_keywords"] if kw.lower() in answer_lower]

            result = {
                "id": qid,
                "status": "✅ PASS" if keywords_found else "⚠️  PARTIAL",
                "intent": intent,
                "answer_length": len(answer),
                "sources_count": len(sources),
                "keywords_found": keywords_found
            }

            print(f"\nResult: {result['status']} (Keywords: {', '.join(keywords_found)})")
            return result

        else:
            print(f"❌ Query failed: {response.status_code}")
            return {
                "id": qid,
                "status": "❌ FAIL",
                "error": response.text
            }

    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            "id": qid,
            "status": "❌ ERROR",
            "error": str(e)
        }


def run_all_tests():
    """Run all 10 test questions"""
    print_section("Testing All 10 Questions")

    results = []

    for q in TEST_QUESTIONS:
        result = test_query(q)
        results.append(result)
        time.sleep(1)  # Small delay between queries

    return results


def print_summary(results: List[Dict]):
    """Print test summary"""
    print_section("Test Summary")

    passed = sum(1 for r in results if "✅" in r["status"])
    partial = sum(1 for r in results if "⚠️" in r["status"])
    failed = sum(1 for r in results if "❌" in r["status"])

    print(f"\nTotal Questions: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"⚠️  Partial: {partial}")
    print(f"❌ Failed: {failed}")
    print(f"\nSuccess Rate: {(passed / len(results)) * 100:.1f}%")

    # Breakdown by type
    print("\n" + "-" * 80)
    print("Breakdown by Type:")

    for qtype in ["GOVERNANCE", "COMMITS", "ISSUES"]:
        type_results = [r for r in results if any(q["id"] == r["id"] and q["type"] == qtype for q in TEST_QUESTIONS)]
        type_passed = sum(1 for r in type_results if "✅" in r["status"])
        print(f"  {qtype}: {type_passed}/{len(type_results)} passed")

    # Detailed results
    print("\n" + "-" * 80)
    print("Detailed Results:")
    for r in results:
        print(f"  {r['id']}: {r['status']}")


def main():
    """Main execution"""
    print_section("ResilientDB Single-Project Demo - Setup & Test")

    # Step 1: Check backend health
    print_section("Step 1: Backend Health Check")
    if not check_backend_health():
        print("\n❌ Backend is not running. Please start the backend first.")
        return

    # Step 2: Check project status
    print_section("Step 2: Project Status")
    if not check_project_status():
        print("\n❌ Project not found or not indexed.")
        return

    # Step 3: Load CSV data
    if not load_csv_data():
        print("\n❌ Failed to load CSV data.")
        return

    # Step 4: Run all tests
    results = run_all_tests()

    # Step 5: Print summary
    print_summary(results)

    print("\n" + "=" * 80)
    print("✅ Testing complete! You can now use the frontend at http://localhost:3000/")
    print("=" * 80)


if __name__ == "__main__":
    main()
