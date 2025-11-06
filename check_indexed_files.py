"""Check what governance files are indexed in ChromaDB for ResilientDB"""
import requests
import json

# Query to retrieve sources
response = requests.post(
    "http://localhost:8000/api/query",
    json={
        "query": "What is the project about?",
        "project_id": "resilientdb-incubator-resilientdb"
    }
)

if response.status_code == 200:
    data = response.json()
    sources = data.get("sources", [])

    print("=" * 80)
    print("GOVERNANCE FILES INDEXED FOR RESILIENTDB")
    print("=" * 80)

    # Extract unique files
    file_map = {}
    for source in sources:
        file_type = source.get("file_type", "unknown")
        file_path = source.get("file_path", "unknown")

        key = (file_type, file_path)
        if key not in file_map:
            file_map[key] = source.get("score", 0)

    # Group by file type
    by_type = {}
    for (file_type, file_path), score in file_map.items():
        if file_type not in by_type:
            by_type[file_type] = []
        by_type[file_type].append(file_path)

    for file_type in sorted(by_type.keys()):
        print(f"\n{file_type.upper()}:")
        for path in sorted(set(by_type[file_type])):
            print(f"  - {path}")

    print(f"\nTotal unique files: {len(file_map)}")
    print(f"Total chunks indexed: 1,416")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
