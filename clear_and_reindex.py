#!/usr/bin/env python3
"""
Clear database and re-index all projects with improved chunking
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.rag_engine import RAGEngine
from app.crawler.governance_extractor import GovernanceExtractor
from loguru import logger

# Projects to re-index (from cache)
PROJECTS = [
    {"id": "dicedb-dice", "owner": "DiceDB", "repo": "dice"},
    {"id": "resilientdb-incubator-resilientdb", "owner": "resilientdb", "repo": "incubator-resilientdb"},
]

def main():
    """Clear database and re-index with new chunking"""

    logger.info("="*70)
    logger.info("🔄 DATABASE CLEANUP AND RE-INDEXING WITH IMPROVED CHUNKING")
    logger.info("="*70)

    # Initialize
    rag = RAGEngine()
    extractor = GovernanceExtractor()

    # Get current stats
    old_stats = rag.get_collection_stats()
    logger.info(f"\n📊 OLD DATABASE:")
    logger.info(f"   Total chunks: {old_stats['total_chunks']}")
    logger.info(f"   Projects: {old_stats['projects_indexed']}")
    for project_id, count in old_stats['project_distribution'].items():
        logger.info(f"   - {project_id}: {count} chunks")

    # Clear database
    logger.info(f"\n🗑️  Clearing database...")
    success = rag.reset_collection()
    if not success:
        logger.error("Failed to reset collection!")
        return

    logger.success("✅ Database cleared")

    # Re-index projects
    total_chunks = 0
    logger.info(f"\n📦 Re-indexing {len(PROJECTS)} projects with new chunking...")
    logger.info("   (Using cached documents - fast)")

    for i, project in enumerate(PROJECTS, 1):
        logger.info(f"\n[{i}/{len(PROJECTS)}] Processing {project['id']}...")

        try:
            start = time.time()

            # Extract from cache
            gov_data = extractor.extract_governance_documents(
                project["owner"],
                project["repo"],
                use_cache=True
            )

            if "error" in gov_data:
                logger.error(f"   ❌ Extraction failed: {gov_data['error']}")
                continue

            # Index with new chunking
            result = rag.index_governance_documents(project["id"], gov_data)

            elapsed = time.time() - start
            old_count = old_stats['project_distribution'].get(project['id'], 0)
            new_count = result.get("indexed", 0)
            reduction = ((old_count - new_count) / old_count * 100) if old_count > 0 else 0

            logger.success(
                f"   ✅ {project['id']}: "
                f"{new_count} chunks (was {old_count}, -{reduction:.0f}%) "
                f"in {elapsed:.1f}s"
            )

            total_chunks += new_count

        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            continue

    # Final stats
    new_stats = rag.get_collection_stats()
    logger.info("\n" + "="*70)
    logger.success("✅ RE-INDEXING COMPLETE!")
    logger.info("="*70)
    logger.info(f"\n📊 RESULTS:")
    logger.info(f"   Old total: {old_stats['total_chunks']:,} chunks")
    logger.info(f"   New total: {new_stats['total_chunks']:,} chunks")
    reduction_pct = ((old_stats['total_chunks'] - new_stats['total_chunks']) / old_stats['total_chunks'] * 100)
    logger.info(f"   Reduction: {old_stats['total_chunks'] - new_stats['total_chunks']:,} chunks ({reduction_pct:.1f}%)")
    logger.info(f"\n💡 Chunk quality: Larger, context-rich chunks with better semantic boundaries")
    logger.info("="*70)

if __name__ == "__main__":
    main()
