#!/usr/bin/env python3
"""
ChatGPT Test Script with Web Search - 18 Selected Questions
Tests 18 questions with web search enabled for real-time GitHub access.

Usage:
    python3 test_18_questions_chatgpt_websearch.py --repo google/meridian
    python3 test_18_questions_chatgpt_websearch.py --repo netflix/hollow --output results.csv

Note: OpenAI's web search is available through the Responses API (2024+)
"""

from openai import OpenAI
import csv
import argparse
from datetime import datetime
from typing import List, Dict
import time
import os
import json

# API Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
CHATGPT_MODEL = "gpt-4o"  # or "gpt-4o-search-preview" if available

# 18 Selected Questions
TEST_QUESTIONS = [
    # PROJECT_DOC_BASED (8 questions)
    {"number": 1, "question": "How do I contribute to this project?", "category": "PROJECT_DOC_BASED"},
    {"number": 2, "question": "What is the code of conduct?", "category": "PROJECT_DOC_BASED"},
    {"number": 3, "question": "How do I report a security vulnerability?", "category": "PROJECT_DOC_BASED"},
    {"number": 4, "question": "What steps should I follow before opening a pull request?", "category": "PROJECT_DOC_BASED"},
    {"number": 5, "question": "How are major decisions made in this project?", "category": "PROJECT_DOC_BASED"},
    {"number": 6, "question": "What skills or tools do I need to contribute?", "category": "PROJECT_DOC_BASED"},
    {"number": 7, "question": "How do I find a good first issue to work on?", "category": "PROJECT_DOC_BASED"},
    {"number": 8, "question": "Are there any contribution guidelines?", "category": "PROJECT_DOC_BASED"},

    # COMMITS (6 questions)
    {"number": 9, "question": "Who are the top 5 contributors by commit count?", "category": "COMMITS"},
    {"number": 10, "question": "Who are the top 10 contributors in the past 6 months?", "category": "COMMITS"},
    {"number": 11, "question": "Rank top five files have been modified the most?", "category": "COMMITS"},
    {"number": 12, "question": "How many unique contributors are there?", "category": "COMMITS"},
    {"number": 13, "question": "Who are the most active contributors?", "category": "COMMITS"},
    {"number": 14, "question": "Who contributed to the documentation?", "category": "COMMITS"},

    # ISSUES (4 questions)
    {"number": 15, "question": "What are the most commented issues?", "category": "ISSUES"},
    {"number": 16, "question": "Who are the most active issue reporters?", "category": "ISSUES"},
    {"number": 17, "question": "What are the oldest open issues?", "category": "ISSUES"},
    {"number": 18, "question": "How quickly are issues being closed?", "category": "ISSUES"},
]


def query_chatgpt_with_websearch(repo_name: str, question: str, client: OpenAI) -> Dict:
    """Query ChatGPT API with web search enabled."""
    repo_url = f"https://github.com/{repo_name}"

    # Enhanced prompt that encourages web search usage
    user_prompt = f"""For the GitHub repository {repo_name} ({repo_url}), answer this question: "{question}"

Please search the web to find accurate, up-to-date information from the actual GitHub repository.
Look at the repository's README, CONTRIBUTING.md, commit history, issues, and other relevant files."""

    try:
        start_time = time.time()

        # Try using the responses API with web search tool
        # OpenAI's web search is available through the 'web_search' tool
        response = client.responses.create(
            model=CHATGPT_MODEL,
            input=user_prompt,
            tools=[
                {
                    "type": "web_search"
                }
            ],
            temperature=0.0,
            max_output_tokens=4000
        )

        elapsed_time = time.time() - start_time

        # Extract response
        answer = response.output_text if hasattr(response, 'output_text') else str(response)

        # Check if web search was used
        web_search_used = False
        tool_uses_count = 0
        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'type') and item.type == 'web_search_call':
                    web_search_used = True
                    tool_uses_count += 1

        return {
            "answer": answer,
            "response_time": elapsed_time,
            "model": CHATGPT_MODEL,
            "web_search_used": web_search_used,
            "tool_uses_count": tool_uses_count,
            "error": None
        }

    except AttributeError:
        # Fallback: responses API not available, try chat completions with web_search tool
        try:
            start_time = time.time()

            response = client.chat.completions.create(
                model="gpt-4o-search-preview",  # Model with built-in search
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=4000,
                web_search_options={
                    "search_context_size": "medium"
                }
            )

            elapsed_time = time.time() - start_time
            answer = response.choices[0].message.content if response.choices else ""

            return {
                "answer": answer,
                "response_time": elapsed_time,
                "model": "gpt-4o-search-preview",
                "web_search_used": True,
                "tool_uses_count": 1,
                "error": None
            }

        except Exception as e2:
            # Final fallback: regular chat completions (no web search)
            try:
                start_time = time.time()

                response = client.chat.completions.create(
                    model=CHATGPT_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You have access to browse the web. Please search for current information about the GitHub repository mentioned."
                        },
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0,
                    max_tokens=4000
                )

                elapsed_time = time.time() - start_time
                answer = response.choices[0].message.content if response.choices else ""

                return {
                    "answer": answer,
                    "response_time": elapsed_time,
                    "model": CHATGPT_MODEL,
                    "web_search_used": False,
                    "tool_uses_count": 0,
                    "error": f"Web search not available, used training data. Original error: {str(e2)}"
                }

            except Exception as e3:
                return {
                    "answer": f"ERROR: {str(e3)}",
                    "response_time": 0.0,
                    "model": CHATGPT_MODEL,
                    "web_search_used": False,
                    "tool_uses_count": 0,
                    "error": str(e3)
                }

    except Exception as e:
        return {
            "answer": f"ERROR: {str(e)}",
            "response_time": 0.0,
            "model": CHATGPT_MODEL,
            "web_search_used": False,
            "tool_uses_count": 0,
            "error": str(e)
        }


def test_repository(repo_name: str, output_file: str) -> List[Dict]:
    """Test all 18 questions with ChatGPT API + Web Search."""

    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-key-here'")
        return []

    client = OpenAI(api_key=OPENAI_API_KEY)

    print("=" * 80)
    print(f"CHATGPT TEST WITH WEB SEARCH - 18 QUESTIONS")
    print("=" * 80)
    print(f"Repository:      {repo_name}")
    print(f"ChatGPT Model:   {CHATGPT_MODEL}")
    print(f"Web Search:      ENABLED")
    print(f"Total Questions: {len(TEST_QUESTIONS)}")
    print(f"Output File:     {output_file}")
    print("=" * 80)
    print()

    results = []

    for i, test_case in enumerate(TEST_QUESTIONS, 1):
        question_num = test_case["number"]
        question = test_case["question"]
        category = test_case["category"]

        print(f"[{i:2d}/{len(TEST_QUESTIONS)}] Q{question_num:2d} ({category}): {question[:50]}")

        response = query_chatgpt_with_websearch(repo_name, question, client)

        answer = response["answer"]
        response_time = response["response_time"]
        error = response["error"]
        web_search_used = response["web_search_used"]
        tool_uses_count = response["tool_uses_count"]

        status = "✅" if not error or "not available" in str(error) else "❌"
        web_status = "🔍" if web_search_used else "📚"
        print(f"         {status} {web_status} Time: {response_time:.1f}s | Web searches: {tool_uses_count} | Answer: {len(answer)} chars")

        result = {
            "timestamp": datetime.now().isoformat(),
            "repo_name": repo_name,
            "question_number": question_num,
            "category": category,
            "question": question,
            "answer": answer,
            "response_time_seconds": round(response_time, 2),
            "answer_length_chars": len(answer),
            "model": response["model"],
            "web_search_enabled": True,
            "web_search_used": web_search_used,
            "tool_uses_count": tool_uses_count,
            "error": error if error else ""
        }
        results.append(result)

        # Rate limiting
        time.sleep(1.0)
        print()

    # Save to CSV
    save_results_to_csv(results, output_file)
    print_summary(results, repo_name)

    return results


def save_results_to_csv(results: List[Dict], output_file: str):
    """Save test results to CSV file."""
    if not results:
        return

    fieldnames = [
        "timestamp", "repo_name", "question_number", "category", "question",
        "response_time_seconds", "answer_length_chars", "model",
        "web_search_enabled", "web_search_used", "tool_uses_count",
        "error", "answer"
    ]

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"✅ Results saved to: {output_file}")
    print()


def print_summary(results: List[Dict], repo_name: str):
    """Print test summary."""
    total = len(results)
    if total == 0:
        return

    errors = sum(1 for r in results if r["error"] and "not available" not in str(r["error"]))
    successful = total - errors
    web_search_used_count = sum(1 for r in results if r["web_search_used"])
    avg_response_time = sum(r["response_time_seconds"] for r in results) / total
    avg_answer_length = sum(r["answer_length_chars"] for r in results) / total
    total_tool_uses = sum(r["tool_uses_count"] for r in results)

    print("=" * 80)
    print(f"SUMMARY: {repo_name}")
    print("=" * 80)
    print(f"Total Questions:        {total}")
    print(f"Successful:             {successful} / {total}")
    print(f"Web Search Used:        {web_search_used_count} / {total} questions")
    print(f"Total Web Searches:     {total_tool_uses}")
    print(f"Average Response Time:  {avg_response_time:.2f}s")
    print(f"Average Answer Length:  {avg_answer_length:.0f} chars")

    # Per-category breakdown
    print()
    print("Per-Category Breakdown:")
    for cat in ["PROJECT_DOC_BASED", "COMMITS", "ISSUES"]:
        cat_results = [r for r in results if r["category"] == cat]
        if cat_results:
            cat_avg_time = sum(r["response_time_seconds"] for r in cat_results) / len(cat_results)
            cat_avg_len = sum(r["answer_length_chars"] for r in cat_results) / len(cat_results)
            cat_web_used = sum(1 for r in cat_results if r["web_search_used"])
            print(f"  {cat}: {len(cat_results)} questions | Web: {cat_web_used}/{len(cat_results)} | Avg time: {cat_avg_time:.1f}s | Avg length: {cat_avg_len:.0f} chars")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Test ChatGPT with web search on 18 selected questions")

    parser.add_argument("--repo", type=str, required=True, help="Repository to test (e.g., google/meridian)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV file path")

    args = parser.parse_args()

    if args.output is None:
        safe_repo_name = args.repo.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"test_results/chatgpt_websearch_18q_{safe_repo_name}_{timestamp}.csv"

    test_repository(args.repo, args.output)
    return 0


if __name__ == "__main__":
    exit(main())
