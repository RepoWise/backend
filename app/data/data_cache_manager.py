"""
Data Cache Manager
Manages caching of API-fetched repository data with metadata tracking
Prevents data mismatch issues in deployment
"""
import json
import hashlib
from typing import Dict, Optional, Tuple
from pathlib import Path
from loguru import logger
import time


class DataCacheManager:
    """
    Manages caching of repository data fetched from scraping API

    Features:
    - Stores data with metadata (timestamp, source, hash)
    - Validates cache freshness
    - Prevents data mismatch with hash verification
    - Supports cache invalidation and refresh
    """

    def __init__(self, cache_dir: str = "data/api_cache"):
        """
        Initialize cache manager

        Args:
            cache_dir: Directory to store cached data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Default cache TTL: 24 hours (86400 seconds)
        # Can be overridden per-project if needed
        self.default_cache_ttl = 86400

        logger.info(f"💾 DataCacheManager initialized: {self.cache_dir}")

    def get_cache_paths(self, project_id: str) -> Tuple[Path, Path]:
        """
        Get cache file paths for a project

        Args:
            project_id: Project identifier

        Returns:
            Tuple of (data_file_path, metadata_file_path)
        """
        data_file = self.cache_dir / f"{project_id}_data.json"
        meta_file = self.cache_dir / f"{project_id}_meta.json"
        return data_file, meta_file

    def save_to_cache(self, project_id: str, github_url: str, api_data: Dict) -> bool:
        """
        Save API data to cache with metadata

        Args:
            project_id: Project identifier
            github_url: GitHub repository URL
            api_data: Data from scraping API

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            data_file, meta_file = self.get_cache_paths(project_id)

            # Calculate data hash for integrity verification
            data_hash = self._calculate_hash(api_data)

            # Create metadata
            metadata = {
                "project_id": project_id,
                "github_url": github_url,
                "cached_at": time.time(),
                "data_hash": data_hash,
                "source": "api",
                "commits_count": len(api_data.get("commit_devs_files", [])),
                "issues_count": len(api_data.get("fetch_github_issues", []))
            }

            # Save data
            with open(data_file, 'w') as f:
                json.dump(api_data, f, indent=2)

            # Save metadata
            with open(meta_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"💾 Cached data for {project_id}: {metadata['commits_count']} commits, {metadata['issues_count']} issues")
            return True

        except Exception as e:
            logger.error(f"❌ Error saving cache for {project_id}: {e}")
            return False

    def load_from_cache(self, project_id: str, validate: bool = True) -> Tuple[bool, Optional[Dict], Optional[Dict]]:
        """
        Load data from cache with validation

        Args:
            project_id: Project identifier
            validate: Whether to validate cache integrity

        Returns:
            Tuple of (success, data, metadata)
            - success: True if data loaded and valid
            - data: Cached data dict or None
            - metadata: Cache metadata or None
        """
        try:
            data_file, meta_file = self.get_cache_paths(project_id)

            # Check if cache exists
            if not data_file.exists() or not meta_file.exists():
                logger.debug(f"📭 No cache found for {project_id}")
                return False, None, None

            # Load metadata
            with open(meta_file, 'r') as f:
                metadata = json.load(f)

            # Load data
            with open(data_file, 'r') as f:
                data = json.load(f)

            # Validate if requested
            if validate:
                # Check data integrity
                current_hash = self._calculate_hash(data)
                stored_hash = metadata.get("data_hash", "")

                if current_hash != stored_hash:
                    logger.warning(f"⚠️  Cache integrity check failed for {project_id}: hash mismatch")
                    return False, None, None

                logger.debug(f"✅ Cache integrity verified for {project_id}")

            logger.info(f"📦 Loaded cached data for {project_id}: {metadata.get('commits_count', 0)} commits, {metadata.get('issues_count', 0)} issues")
            return True, data, metadata

        except Exception as e:
            logger.error(f"❌ Error loading cache for {project_id}: {e}")
            return False, None, None

    def is_cache_fresh(self, project_id: str, max_age_seconds: Optional[int] = None) -> bool:
        """
        Check if cached data is still fresh

        Args:
            project_id: Project identifier
            max_age_seconds: Maximum cache age in seconds (uses default if None)

        Returns:
            True if cache exists and is fresh, False otherwise
        """
        try:
            _, meta_file = self.get_cache_paths(project_id)

            if not meta_file.exists():
                return False

            with open(meta_file, 'r') as f:
                metadata = json.load(f)

            cached_at = metadata.get("cached_at", 0)
            current_time = time.time()
            age_seconds = current_time - cached_at

            ttl = max_age_seconds if max_age_seconds is not None else self.default_cache_ttl

            is_fresh = age_seconds < ttl

            if is_fresh:
                hours_old = age_seconds / 3600
                logger.debug(f"📅 Cache for {project_id} is fresh ({hours_old:.1f} hours old)")
            else:
                hours_old = age_seconds / 3600
                logger.debug(f"📅 Cache for {project_id} is stale ({hours_old:.1f} hours old)")

            return is_fresh

        except Exception as e:
            logger.error(f"❌ Error checking cache freshness for {project_id}: {e}")
            return False

    def get_cache_info(self, project_id: str) -> Optional[Dict]:
        """
        Get cache metadata without loading full data

        Args:
            project_id: Project identifier

        Returns:
            Cache metadata dict or None
        """
        try:
            _, meta_file = self.get_cache_paths(project_id)

            if not meta_file.exists():
                return None

            with open(meta_file, 'r') as f:
                metadata = json.load(f)

            # Add calculated fields
            cached_at = metadata.get("cached_at", 0)
            age_seconds = time.time() - cached_at
            metadata["age_hours"] = age_seconds / 3600
            metadata["is_fresh"] = age_seconds < self.default_cache_ttl

            return metadata

        except Exception as e:
            logger.error(f"❌ Error getting cache info for {project_id}: {e}")
            return None

    def invalidate_cache(self, project_id: str) -> bool:
        """
        Invalidate (delete) cached data for a project

        Args:
            project_id: Project identifier

        Returns:
            True if cache was deleted, False otherwise
        """
        try:
            data_file, meta_file = self.get_cache_paths(project_id)

            deleted = False
            if data_file.exists():
                data_file.unlink()
                deleted = True
            if meta_file.exists():
                meta_file.unlink()
                deleted = True

            if deleted:
                logger.info(f"🗑️  Invalidated cache for {project_id}")
            else:
                logger.debug(f"📭 No cache to invalidate for {project_id}")

            return deleted

        except Exception as e:
            logger.error(f"❌ Error invalidating cache for {project_id}: {e}")
            return False

    def _calculate_hash(self, data: Dict) -> str:
        """
        Calculate hash of data for integrity verification

        Args:
            data: Data to hash

        Returns:
            SHA256 hash string
        """
        # Convert to JSON string with sorted keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def list_cached_projects(self) -> list:
        """
        List all projects that have cached data

        Returns:
            List of project IDs
        """
        try:
            cached_projects = []
            for meta_file in self.cache_dir.glob("*_meta.json"):
                project_id = meta_file.stem.replace("_meta", "")
                cached_projects.append(project_id)

            return sorted(cached_projects)

        except Exception as e:
            logger.error(f"❌ Error listing cached projects: {e}")
            return []

    def get_cache_stats(self) -> Dict:
        """
        Get overall cache statistics

        Returns:
            Dictionary with cache statistics
        """
        try:
            cached_projects = self.list_cached_projects()
            total_projects = len(cached_projects)

            fresh_count = 0
            stale_count = 0
            total_commits = 0
            total_issues = 0

            for project_id in cached_projects:
                info = self.get_cache_info(project_id)
                if info:
                    if info.get("is_fresh"):
                        fresh_count += 1
                    else:
                        stale_count += 1

                    total_commits += info.get("commits_count", 0)
                    total_issues += info.get("issues_count", 0)

            return {
                "total_projects": total_projects,
                "fresh_caches": fresh_count,
                "stale_caches": stale_count,
                "total_commits_cached": total_commits,
                "total_issues_cached": total_issues,
                "cache_directory": str(self.cache_dir)
            }

        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {}
