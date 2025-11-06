"""Quick test of keras-io after CSV reload"""
import requests
import time

API_URL = "http://localhost:8000/api/query"
PROJECT_ID = "keras-team-keras-io"

tests = [
    {"name": "Top committers", "query": "Who are the top 3 most active committers?"},
    {"name": "Latest commits", "query": "What are the 2 latest commits?"},
    {"name": "Open issues count", "query": "How many open issues are there?"},
    {"name": "Recent issues", "query": "What are the 3 most recently created issues?"},
]

print("=" * 80)
print("KERAS-IO QUICK TEST (After CSV Reload)")
print("=" * 80)

for test in tests:
    print(f"\n{test['name']}: {test['query']}")
    response = requests.post(
        API_URL,
        json={"query": test["query"], "project_id": PROJECT_ID},
        timeout=30
    )

    if response.status_code == 200:
        data = response.json()
        answer = data.get("response", "")
        intent = data.get("metadata", {}).get("intent", "N/A")
        print(f"  Intent: {intent}")
        print(f"  Answer: {answer[:200]}")
    else:
        print(f"  ❌ Error: {response.status_code}")

    time.sleep(1)

print("\n" + "=" * 80)
print("✅ Test complete!")
