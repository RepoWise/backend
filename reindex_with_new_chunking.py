#!/usr/bin/env python3
"""
Re-index all projects with improved chunking algorithm
"""
import sys
from pathlib import Path
import asyncio

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.rag_engine import RAGEngine
from app.crawler.governance_extractor import GovernanceExtractor
from loguru import logger


async def main():
    """Re-index all projects with new chunking"""

    # Initialize components
    logger.info("🔄 Starting re-indexing with improved chunking...")
    rag = RAGEngine()
    extractor = GovernanceExtractor()

    # Get current stats
    old_stats = rag.get_collection_stats()
    logger.info(f"Current: {old_stats['total_chunks']} chunks from {old_stats['projects_indexed']} projects")

    # Confirm reset
    response = input("\n⚠️  Reset database and re-index all projects? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("❌ Cancelled")
        return

    # Reset collection
    logger.info("Resetting collection...")
    rag.reset_collection()

    # Test projects to re-index (start with smallest for testing)
    test_projects = [
        {"id": "dicedb-dice", "owner": "DiceDB", "repo": "dice"},
        {"id": "resilientdb-incubator-resilientdb", "owner": "resilientdb", "repo": "incubator-resilientdb"},
    ]

    total_indexed = 0

    for project in test_projects:
        logger.info(f"\n📦 Processing {project['id']}...")

        try:
            # Extract governance documents (use cache)
            gov_data = extractor.extract_governance_documents(
                project["owner"],
                project["repo"],
                use_cache=True
            )

            if "error" in gov_data:
                logger.error(f"Failed to extract: {gov_data['error']}")
                continue

            # Index with new chunking
            logger.info(f"Indexing {project['id']} with improved chunking...")
            result = rag.index_governance_documents(project["id"], gov_data)

            if result.get("indexed", 0) > 0:
                logger.success(
                    f"✅ {project['id']}: {result['indexed']} chunks "
                    f"(was {old_stats['project_distribution'].get(project['id'], 0)})"
                )
                total_indexed += result["indexed"]
            else:
                logger.warning(f"⚠️  {project['id']}: No chunks created")

        except Exception as e:
            logger.error(f"Error indexing {project['id']}: {e}")
            continue

    # Final stats
    new_stats = rag.get_collection_stats()
    logger.info("\n" + "="*60)
    logger.success(f"✅ Re-indexing complete!")
    logger.info(f"Old total: {old_stats['total_chunks']} chunks")
    logger.info(f"New total: {new_stats['total_chunks']} chunks")
    logger.info(f"Reduction: {old_stats['total_chunks'] - new_stats['total_chunks']} chunks")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
