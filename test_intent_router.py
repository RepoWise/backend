"""
Test the improved hierarchical intent router with real queries
"""
from app.models.intent_router import IntentRouter
from app.models.llm_client import LLMClient
from app.core.config import settings
from loguru import logger

# Initialize router with LLM client for fallback testing
llm_client = LLMClient()  # Uses settings.ollama_model and settings.ollama_host
router = IntentRouter(llm_client=llm_client)

# Test cases with expected intents
test_cases = [
    # GOVERNANCE cases (procedure questions)
    ("How do I report a bug?", "GOVERNANCE"),
    ("Who currently maintains this project?", "GOVERNANCE"),
    ("What are the voting rules for changes?", "GOVERNANCE"),
    ("What are the required steps before submitting a pull request?", "GOVERNANCE"),
    ("How do I report a security vulnerability?", "GOVERNANCE"),

    # COMMITS cases (statistical + commits context)
    ("Who are the three most active committers?", "COMMITS"),
    ("What are the five latest commits?", "COMMITS"),
    ("Which files have the highest total lines added across all commits?", "COMMITS"),
    ("Show me recent code changes", "COMMITS"),

    # ISSUES cases (statistical + issues context)
    ("How many open vs closed issues are there?", "ISSUES"),
    ("What are the three most recently updated issues?", "ISSUES"),
    ("Which issue has the highest comment count?", "ISSUES"),

    # GENERAL cases
    ("What is machine learning?", "GENERAL"),
    ("Explain backpropagation", "GENERAL"),
]

print("=" * 80)
print("INTENT ROUTER TEST - Hierarchical Classification with LLM Fallback")
print("=" * 80)

results = {"pass": 0, "fail": 0}

for query, expected_intent in test_cases:
    intent, confidence = router.classify_intent(query, has_project_context=True)

    status = "✅ PASS" if intent == expected_intent else "❌ FAIL"
    if intent == expected_intent:
        results["pass"] += 1
    else:
        results["fail"] += 1

    print(f"\n{status}")
    print(f"Query: '{query}'")
    print(f"Expected: {expected_intent} | Got: {intent} (confidence: {confidence:.2f})")

print("\n" + "=" * 80)
print(f"RESULTS: {results['pass']}/{len(test_cases)} passed ({results['pass']/len(test_cases)*100:.0f}%)")
print("=" * 80)

# Detailed explanation for the critical test case
print("\n" + "=" * 80)
print("DETAILED ROUTING EXPLANATION FOR: 'How do I report a bug?'")
print("=" * 80)
print(router.explain_routing("How do I report a bug?", has_project_context=True))
