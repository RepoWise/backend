"""
Directly load graph for resilientdb-resilientdb from existing CSV
"""
import sys
sys.path.insert(0, "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/backend")

from app.services.graph_loader import load_project_graph
from loguru import logger

csv_path = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv"

logger.info("Loading graph from existing CSV...")

try:
    loader = load_project_graph("resilientdb-resilientdb", csv_path)
    stats = loader.get_network_stats()

    logger.success("Graph loaded successfully!")
    logger.info(f"Total developers: {stats['total_developers']}")
    logger.info(f"Total files: {stats['total_files']}")
    logger.info(f"Total commits: {stats['total_commits']}")
    logger.info(f"Network edges: {stats['developer_network']['edges']}")

    print("\n✅ Graph RAG is now loaded and ready!")
    print(f"   - {stats['total_developers']} developers")
    print(f"   - {stats['total_files']} files")
    print(f"   - {stats['total_commits']} commits")

except Exception as e:
    logger.error(f"Failed to load graph: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
