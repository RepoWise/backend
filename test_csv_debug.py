"""
Debug script to test CSV engine issues queries
"""
import sys
sys.path.insert(0, '/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/backend')

from app.data.csv_engine import CSVDataEngine

# Initialize engine
engine = CSVDataEngine()

# Load data
project_id = "apache-incubator-resilientdb"
commits_path = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv"
issues_path = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/issues.csv"

print("Loading CSV data...")
result = engine.load_project_data(project_id, commits_path, issues_path)
print(f"Load result: {result}")

# Check what data is available
print(f"\nData cache keys: {engine.data_cache.keys()}")
if project_id in engine.data_cache:
    print(f"Project data keys: {engine.data_cache[project_id].keys()}")

    if "issues" in engine.data_cache[project_id]:
        issues_df = engine.data_cache[project_id]["issues"]
        print(f"\nIssues DataFrame shape: {issues_df.shape}")
        print(f"Issues DataFrame columns: {list(issues_df.columns)}")
        print(f"First 5 rows:")
        print(issues_df.head())

        # Check type column
        if 'type' in issues_df.columns:
            print(f"\nType value counts:")
            print(issues_df['type'].value_counts())

# Test the query
print("\n" + "="*80)
print("Testing query: 'What are the three most recently updated issues'")
print("="*80)

query = "What are the three most recently updated issues, including their states and reporters?"
context, records = engine.get_context_for_query(project_id, query, "issues")

print(f"\nContext returned:")
print(context)
print(f"\nNumber of records: {len(records)}")
print(f"\nRecords:")
for i, record in enumerate(records):
    print(f"  {i+1}. {record}")
