"""
Quick script to reload graph for resilientdb-resilientdb
"""
import sys
import asyncio
sys.path.insert(0, "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/backend")

from app.services.graph_loader import load_project_graph
from loguru import logger

# CSV path for ResilientDB
csv_path = "/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/ossprey-gov-poc/data/scraped/resilientdb-resilientdb/commit-file-dev.csv"

logger.info("Reloading graph for resilientdb-resilientdb...")

try:
    loader = load_project_graph("resilientdb-resilientdb", csv_path)
    stats = loader.get_network_stats()
    logger.success(f"Graph loaded successfully!")
    logger.info(f"Developers: {stats['total_developers']}")
    logger.info(f"Files: {stats['total_files']}")
    logger.info(f"Commits: {stats['total_commits']}")
except Exception as e:
    logger.error(f"Failed to load graph: {e}")
    sys.exit(1)
