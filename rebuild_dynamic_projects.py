#!/usr/bin/env python3
"""
Rebuild dynamic_projects.json from indexed data in the vector database
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.rag_engine import RAGEngine
from app.core.config import FLAGSHIP_PROJECTS
from loguru import logger

DYNAMIC_PROJECTS_FILE = Path("data/dynamic_projects.json")


def main():
    """Rebuild dynamic projects from vector database"""

    logger.info("="*70)
    logger.info("🔄 REBUILDING DYNAMIC PROJECTS FROM DATABASE")
    logger.info("="*70)

    rag = RAGEngine()

    # Get all indexed projects
    stats = rag.get_collection_stats()
    indexed_projects = stats.get("project_distribution", {})

    logger.info(f"\nFound {len(indexed_projects)} projects in database:")
    for project_id, count in indexed_projects.items():
        logger.info(f"  - {project_id}: {count} chunks")

    # Get flagship project IDs
    flagship_ids = {p["id"] for p in FLAGSHIP_PROJECTS}
    logger.info(f"\nFlagship projects: {len(flagship_ids)}")
    for fid in sorted(flagship_ids):
        logger.info(f"  - {fid}")

    # Find dynamic (non-flagship) projects
    dynamic_project_ids = [
        pid for pid in indexed_projects.keys()
        if pid not in flagship_ids
    ]

    logger.info(f"\n🔍 Dynamic projects to rebuild: {len(dynamic_project_ids)}")
    for pid in sorted(dynamic_project_ids):
        logger.info(f"  - {pid}")

    if not dynamic_project_ids:
        logger.info("\n✅ No dynamic projects to rebuild")
        return

    # Reconstruct project objects
    dynamic_projects = {}
    for project_id in dynamic_project_ids:
        # Parse project_id (format: "owner-repo")
        parts = project_id.rsplit("-", 1)
        if len(parts) == 2:
            owner, repo = parts
        else:
            # Handle complex names like keras-team-keras
            # Try to extract from actual metadata
            logger.warning(f"Complex project_id: {project_id}, trying to extract from metadata")

            # Get a sample chunk to see metadata
            all_data = rag.vector_store.get()
            sample_meta = next(
                (m for m in all_data['metadatas'] if m.get('project_id') == project_id),
                None
            )

            if sample_meta and 'owner' in sample_meta and 'repo' in sample_meta:
                owner = sample_meta['owner']
                repo = sample_meta['repo']
                logger.info(f"  Extracted from metadata: {owner}/{repo}")
            else:
                # Best guess: split on first hyphen
                parts = project_id.split("-", 1)
                owner = parts[0] if len(parts) > 0 else "unknown"
                repo = parts[1] if len(parts) > 1 else project_id
                logger.warning(f"  Guessing: {owner}/{repo}")

        project = {
            "id": project_id,
            "name": repo.replace("-", " ").title(),
            "owner": owner,
            "repo": repo,
            "description": f"Custom repository: {owner}/{repo}",
            "foundation": "Custom",
            "governance_url": f"https://github.com/{owner}/{repo}",
        }

        dynamic_projects[project_id] = project
        logger.success(f"  ✅ Rebuilt: {project_id} → {owner}/{repo}")

    # Save to file
    logger.info(f"\n💾 Saving {len(dynamic_projects)} projects to {DYNAMIC_PROJECTS_FILE}")
    DYNAMIC_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DYNAMIC_PROJECTS_FILE, "w") as f:
        json.dump(dynamic_projects, f, indent=2)

    logger.success(f"\n✅ Successfully rebuilt dynamic_projects.json")
    logger.info("="*70)

    # Show contents
    logger.info("\n📄 Contents of dynamic_projects.json:")
    for pid, proj in dynamic_projects.items():
        logger.info(f"  {pid}:")
        logger.info(f"    Owner: {proj['owner']}")
        logger.info(f"    Repo: {proj['repo']}")
        logger.info(f"    URL: {proj['governance_url']}")


if __name__ == "__main__":
    main()
