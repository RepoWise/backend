"""
Quick test script to add a project and verify scraper integration
"""
import asyncio
import httpx
import json
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

async def test_add_project():
    """Test adding a small project"""

    # Use a small project for faster testing
    project_url = "https://github.com/resilientdb/resilientdb"

    logger.info(f"Adding project: {project_url}")
    logger.info("This may take 1-3 minutes to scrape issues, PRs, and commits...")

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/projects/add",
                json={"github_url": project_url}
            )

            if response.status_code == 200:
                result = response.json()

                logger.success(f"✓ Project added successfully!")
                logger.info(f"Status: {result.get('status')}")

                # Check indexing results
                indexing = result.get('indexing', {})

                # Governance
                gov_indexed = indexing.get('governance', {}).get('indexed', 0)
                logger.info(f"Governance docs indexed: {gov_indexed}")

                # Socio-technical data
                socio_tech = indexing.get('socio_technical', {})
                issues = socio_tech.get('issues_indexed', 0)
                prs = socio_tech.get('prs_indexed', 0)
                commits = socio_tech.get('commits_indexed', 0)

                logger.info(f"Issues indexed: {issues}")
                logger.info(f"PRs indexed: {prs}")
                logger.info(f"Commits indexed: {commits}")

                # Graph
                graph_loaded = indexing.get('graph_loaded', False)
                logger.info(f"Graph RAG loaded: {graph_loaded}")

                # Total
                total = indexing.get('total_indexed', 0)
                logger.success(f"✓ Total documents indexed: {total}")

                # Save full result
                with open('/tmp/project_add_full_result.json', 'w') as f:
                    json.dump(result, f, indent=2)
                logger.info("Full result saved to /tmp/project_add_full_result.json")

                return True
            else:
                logger.error(f"✗ Failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False

        except Exception as e:
            logger.error(f"✗ Error: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_add_project())
    sys.exit(0 if success else 1)
