"""
Quick test to index ResilientDB and see detailed output
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.crawler.governance_extractor import GovernanceExtractor
from app.rag.rag_engine import RAGEngine
from loguru import logger

def main():
    logger.info("Starting ResilientDB indexing test...")

    # Initialize components
    logger.info("Initializing GovernanceExtractor...")
    extractor = GovernanceExtractor()

    logger.info("Initializing RAG Engine...")
    rag_engine = RAGEngine()

    # Extract governance
    logger.info("Extracting governance for apache/incubator-resilientdb...")
    result = extractor.extract_governance_documents("apache", "incubator-resilientdb")

    logger.info(f"Extraction result: {len(result.get('files', {}))} files")
    for file_type in result.get('files', {}).keys():
        logger.info(f"  - {file_type}")

    # Index
    logger.info("Starting indexing...")
    index_result = rag_engine.index_governance_documents("resilientdb", result)

    logger.success(f"Indexing complete! Result: {index_result}")

    # Check stats
    stats = rag_engine.get_collection_stats()
    logger.info(f"Collection stats: {stats}")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
