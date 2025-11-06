"""Add keras-io project and load CSV data"""
import requests
import time

API_URL = "http://localhost:8000/api"

print("=" * 80)
print("ADDING KERAS-IO PROJECT")
print("=" * 80)

# Step 1: Add the project (scrapes governance docs)
print("\n1. Adding keras-io project...")
response = requests.post(
    f"{API_URL}/projects/add",
    json={"github_url": "https://github.com/keras-team/keras-io"}
)

if response.status_code == 200:
    data = response.json()
    print(f"✅ Project added successfully!")
    print(f"   Project ID: {data.get('project', {}).get('id')}")
    project_id = data.get('project', {}).get('id')
else:
    print(f"❌ Failed to add project: {response.status_code}")
    print(response.text)
    exit(1)

# Wait for scraping to complete
print("\n⏳ Waiting for governance document scraping to complete...")
time.sleep(5)

# Step 2: Load CSV data
print("\n2. Loading CSV data...")
csv_response = requests.post(
    f"{API_URL}/projects/{project_id}/load-csv",
    json={
        "commits_csv_path": "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/keras-io/keras-io-commit-file-dev.csv",
        "issues_csv_path": "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/keras-io/keras-io_issues.csv"
    }
)

if csv_response.status_code == 200:
    csv_data = csv_response.json()
    print(f"✅ CSV data loaded successfully!")
    print(f"   Commits: {csv_data.get('loaded', {}).get('commits_loaded')}")
    print(f"   Issues: {csv_data.get('loaded', {}).get('issues_loaded')}")
else:
    print(f"❌ Failed to load CSV data: {csv_response.status_code}")
    print(csv_response.text)
    exit(1)

print("\n" + "=" * 80)
print("✅ KERAS-IO PROJECT SETUP COMPLETE")
print("=" * 80)
print(f"\nProject ID: {project_id}")
print("You can now query governance, commits, and issues for keras-io!")
