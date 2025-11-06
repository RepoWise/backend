"""Re-index keras-io governance documents with ChromaDB"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.rag.rag_engine import RAGEngine
from app.crawler.governance_extractor import GovernanceExtractor
from loguru import logger

def main():
    """Re-index keras-io with ChromaDB"""
    logger.info("=" * 80)
    logger.info("RE-INDEXING KERAS-IO WITH CHROMADB")
    logger.info("=" * 80)

    # Initialize components
    logger.info("Initializing RAG Engine with ChromaDB...")
    rag_engine = RAGEngine()

    logger.info("Initializing Governance Extractor...")
    gov_extractor = GovernanceExtractor()

    # Extract governance documents (will use cache)
    project_id = "keras-team-keras-io"
    owner = "keras-team"
    repo = "keras-io"

    logger.info(f"Extracting governance documents for {owner}/{repo}...")
    gov_data = gov_extractor.extract_governance_documents(owner, repo, use_cache=True)

    if "error" in gov_data:
        logger.error(f"Error extracting governance: {gov_data['error']}")
        return False

    logger.info(f"Found {len(gov_data.get('files', {}))} governance files")

    # Index in ChromaDB
    logger.info(f"Indexing governance documents in ChromaDB...")
    result = rag_engine.index_governance_documents(project_id, gov_data)

    logger.success("✅ Re-indexing complete!")
    logger.info(f"Indexing result: {result}")

    # Get collection stats
    stats = rag_engine.vector_store.get_collection_stats(project_id)
    logger.success(f"ChromaDB collection stats for {project_id}:")
    logger.info(f"  - Document count: {stats.get('count', 0)}")
    logger.info(f"  - Collection name: {stats.get('name', 'N/A')}")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
