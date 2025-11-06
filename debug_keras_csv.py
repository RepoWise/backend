"""Debug script to check if keras-io CSV data is accessible"""
import requests

API_URL = "http://localhost:8000/api"
PROJECT_ID = "keras-team-keras-io"

print("=" * 80)
print("DEBUGGING KERAS-IO CSV DATA ACCESS")
print("=" * 80)

# Test 1: Check project info
print("\n1. Checking project info...")
response = requests.get(f"{API_URL}/projects/{PROJECT_ID}")
if response.status_code == 200:
    print("✅ Project exists")
    print(f"   {response.json()}")
else:
    print(f"❌ Project not found: {response.status_code}")

# Test 2: Try a simple commits query
print("\n2. Testing commits query...")
response = requests.post(
    f"{API_URL}/query",
    json={
        "query": "Count the total number of commits",
        "project_id": PROJECT_ID
    }
)
if response.status_code == 200:
    data = response.json()
    print(f"✅ Query successful")
    print(f"   Intent: {data.get('metadata', {}).get('intent')}")
    print(f"   Data Source: {data.get('metadata', {}).get('data_source')}")
    print(f"   Response: {data.get('response')[:200]}")
else:
    print(f"❌ Query failed: {response.status_code}")
    print(f"   {response.text}")

# Test 3: Try a simple issues query
print("\n3. Testing issues query...")
response = requests.post(
    f"{API_URL}/query",
    json={
        "query": "How many total issues are in the dataset?",
        "project_id": PROJECT_ID
    }
)
if response.status_code == 200:
    data = response.json()
    print(f"✅ Query successful")
    print(f"   Intent: {data.get('metadata', {}).get('intent')}")
    print(f"   Data Source: {data.get('metadata', {}).get('data_source')}")
    print(f"   Response: {data.get('response')[:200]}")
else:
    print(f"❌ Query failed: {response.status_code}")
    print(f"   {response.text}")

# Test 4: Re-load CSV data
print("\n4. Re-loading CSV data (in case it was cleared)...")
response = requests.post(
    f"{API_URL}/projects/{PROJECT_ID}/load-csv",
    json={
        "commits_csv_path": "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/keras-io/keras-io-commit-file-dev.csv",
        "issues_csv_path": "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/keras-io/keras-io_issues.csv"
    }
)
if response.status_code == 200:
    print(f"✅ CSV data reloaded")
    print(f"   {response.json()}")
else:
    print(f"❌ Failed to reload: {response.status_code}")
