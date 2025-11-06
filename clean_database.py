#!/usr/bin/env python3
"""
Clean database script - Removes all test data to start fresh
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.rag.rag_engine import RAGEngine
from loguru import logger

def main():
    """Clean all indexed data"""
    logger.info("🧹 Starting database cleanup...")

    # Initialize RAG engine
    rag = RAGEngine()

    # Get current stats
    stats = rag.get_collection_stats()
    logger.info(f"Current database has {stats['total_chunks']} chunks from {stats['projects_indexed']} projects:")
    for project, count in stats['project_distribution'].items():
        logger.info(f"  - {project}: {count} chunks")

    # Confirm
    response = input("\n⚠️  This will DELETE ALL indexed documents. Continue? (yes/no): ")

    if response.lower() != 'yes':
        logger.info("❌ Cleanup cancelled")
        return

    # Reset collection
    logger.info("Deleting all documents...")
    success = rag.reset_collection()

    if success:
        logger.success("✅ Database cleaned successfully!")
        logger.info("You can now add projects with clean data")
    else:
        logger.error("❌ Failed to clean database")

if __name__ == "__main__":
    main()
