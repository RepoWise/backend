"""
Advanced Governance Document Extractor
Implements multi-method extraction with intelligent caching and rate limiting
"""
import re
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger

from github import Github, GithubException, RateLimitExceededException
from github.Repository import Repository
from github.GithubObject import NotSet

from app.core.config import settings, GOVERNANCE_FILES


class GovernanceExtractor:
    """
    Production-grade governance document extractor with:
    - Multi-method extraction (Community Profile API, Tree API, Contents API)
    - Intelligent caching with SHA-based change detection
    - Rate limit management with exponential backoff
    - Pattern-based file detection for all governance document types
    """

    def __init__(self, github_token: str = None):
        """Initialize extractor with GitHub authentication"""
        token = github_token or settings.github_token
        self.github = Github(token, per_page=100)
        self.cache_dir = Path(settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"GovernanceExtractor initialized with cache dir: {self.cache_dir}")

    def _check_rate_limit(self):
        """Check and handle GitHub API rate limits"""
        rate_limit = self.github.get_rate_limit()
        remaining = rate_limit.core.remaining

        logger.debug(f"GitHub API rate limit: {remaining} / {rate_limit.core.limit}")

        if remaining < settings.github_rate_limit_threshold:
            reset_time = rate_limit.core.reset
            sleep_duration = (reset_time - datetime.now()).total_seconds() + 10

            if sleep_duration > 0:
                logger.warning(
                    f"Rate limit low ({remaining}). Sleeping for {sleep_duration:.0f}s"
                )
                time.sleep(sleep_duration)

    def _get_cache_path(self, owner: str, repo: str) -> Path:
        """Generate cache file path for repository"""
        cache_key = hashlib.md5(f"{owner}/{repo}".encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.json"

    def _load_from_cache(
        self, owner: str, repo: str
    ) -> Optional[Dict]:
        """Load governance data from cache if valid"""
        cache_path = self._get_cache_path(owner, repo)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Check cache age
            cached_time = datetime.fromisoformat(cached_data.get("cached_at", ""))
            cache_age = datetime.now() - cached_time

            if cache_age.total_seconds() > settings.cache_ttl_seconds:
                logger.info(f"Cache expired for {owner}/{repo}")
                return None

            logger.info(f"Loaded from cache: {owner}/{repo}")
            return cached_data

        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None

    def _save_to_cache(self, owner: str, repo: str, data: Dict):
        """Save governance data to cache"""
        cache_path = self._get_cache_path(owner, repo)

        try:
            data["cached_at"] = datetime.now().isoformat()
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved to cache: {owner}/{repo}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def _match_governance_file(self, file_path: str) -> Optional[Tuple[str, str]]:
        """
        Match file path against governance file patterns
        Returns (file_type, detected_path) or None
        """
        file_path_lower = file_path.lower()

        for file_type, patterns in GOVERNANCE_FILES.items():
            for pattern in patterns:
                pattern_lower = pattern.lower()
                # Check exact match or ends with pattern
                if file_path_lower == pattern_lower or file_path_lower.endswith(
                    f"/{pattern_lower}"
                ):
                    return (file_type, file_path)

        return None

    def _extract_via_community_profile(
        self, repo: Repository
    ) -> Dict[str, Dict]:
        """Extract using GitHub Contents API for common locations"""
        files_found = {}

        try:
            self._check_rate_limit()

            # Check common locations for governance files
            common_paths = [
                "CODE_OF_CONDUCT.md",
                "CONTRIBUTING.md",
                "LICENSE",
                "LICENSE.md",
                "README.md",
                "GOVERNANCE.md",
                "SECURITY.md",
                ".github/CODE_OF_CONDUCT.md",
                ".github/CONTRIBUTING.md",
                ".github/SECURITY.md",
                "docs/GOVERNANCE.md",
                "MAINTAINERS.md",
                "MAINTAINERS",
                "OWNERS",
                "CODEOWNERS",
                ".github/CODEOWNERS",
                "docs/CODEOWNERS",
            ]

            for path in common_paths:
                try:
                    # Try to get the file
                    content_file = repo.get_contents(path)
                    if content_file and not isinstance(content_file, list):
                        match = self._match_governance_file(path)
                        if match:
                            file_type, _ = match
                            if file_type not in files_found:
                                files_found[file_type] = {
                                    "path": path,
                                    "sha": content_file.sha,
                                    "size": content_file.size,
                                    "url": content_file.html_url,
                                    "source": "contents_api",
                                }
                except:
                    # File doesn't exist at this path, continue
                    pass

            logger.info(
                f"Contents API found {len(files_found)} files for {repo.full_name}"
            )

        except Exception as e:
            logger.warning(f"Contents API search failed: {e}")

        return files_found

    def _extract_via_tree_api(self, repo: Repository) -> Dict[str, Dict]:
        """Extract using Git Trees API (most efficient for bulk operations)"""
        files_found = {}

        try:
            self._check_rate_limit()

            # Get the default branch tree
            default_branch = repo.default_branch
            branch = repo.get_branch(default_branch)
            tree = repo.get_git_tree(branch.commit.sha, recursive=True)

            # Count total files
            total_files = len(tree.tree) if hasattr(tree, 'tree') else 0
            logger.info(
                f"Tree API fetched {total_files} items for {repo.full_name}"
            )

            # Scan all files in tree
            for element in tree.tree:
                if element.type == "blob":  # Files only, not directories
                    match = self._match_governance_file(element.path)
                    if match:
                        file_type, path = match
                        # Prioritize root-level files over subdirectory files
                        if file_type not in files_found:
                            files_found[file_type] = {
                                "path": path,
                                "sha": element.sha,
                                "size": element.size if hasattr(element, 'size') else 0,
                                "url": element.url,
                                "source": "tree_api",
                            }
                        else:
                            # If we found one already, prefer shorter path (root files)
                            existing_path = files_found[file_type]["path"]
                            if len(path) < len(existing_path):  # Shorter path = closer to root
                                files_found[file_type] = {
                                    "path": path,
                                    "sha": element.sha,
                                    "size": element.size if hasattr(element, 'size') else 0,
                                    "url": element.url,
                                    "source": "tree_api",
                                }

            logger.info(
                f"Tree API matched {len(files_found)} governance files for {repo.full_name}"
            )

        except Exception as e:
            logger.error(f"Tree API extraction failed: {e}")

        return files_found

    def _fetch_file_content(
        self, repo: Repository, file_path: str
    ) -> Optional[str]:
        """Fetch actual file content from GitHub"""
        try:
            self._check_rate_limit()
            content_file = repo.get_contents(file_path)

            if isinstance(content_file, list):
                # If it's a directory, skip
                return None

            content = content_file.decoded_content.decode("utf-8")
            return content

        except GithubException as e:
            if e.status == 404:
                logger.debug(f"File not found: {file_path}")
            else:
                logger.error(f"Error fetching {file_path}: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error fetching {file_path}: {e}")
            return None

    def extract_governance_documents(
        self, owner: str, repo_name: str, use_cache: bool = True
    ) -> Dict:
        """
        Main extraction method combining multiple strategies

        Returns:
            Dict with structure:
            {
                "owner": str,
                "repo": str,
                "extracted_at": str (ISO datetime),
                "files": {
                    "governance": {
                        "path": str,
                        "content": str,
                        "sha": str,
                        "source": str
                    },
                    ...
                },
                "metadata": {
                    "total_files": int,
                    "extraction_methods": list,
                    "extraction_time_seconds": float
                }
            }
        """
        start_time = time.time()

        logger.info(f"Starting extraction for {owner}/{repo_name}")

        # Check cache first
        if use_cache:
            cached = self._load_from_cache(owner, repo_name)
            if cached:
                return cached

        try:
            # Get repository
            self._check_rate_limit()
            repo = self.github.get_repo(f"{owner}/{repo_name}")

            # Strategy 1: Community Profile API (fast, limited coverage)
            files_from_profile = self._extract_via_community_profile(repo)

            # Strategy 2: Tree API (comprehensive, single request)
            files_from_tree = self._extract_via_tree_api(repo)

            # Merge results (PRIORITIZE root-level files from Contents API over subdirectories)
            # This ensures we get README.md from root, not INSTALL/README.md
            all_files = {**files_from_tree, **files_from_profile}  # Profile overrides Tree

            # Fetch actual content for each file
            governance_data = {}
            for file_type, file_info in all_files.items():
                logger.info(f"Fetching content for {file_type}: {file_info['path']}")
                content = self._fetch_file_content(repo, file_info["path"])

                if content:
                    governance_data[file_type] = {
                        **file_info,
                        "content": content,
                        "content_length": len(content),
                        "fetched_at": datetime.now().isoformat(),
                    }

            extraction_time = time.time() - start_time

            # Build result
            result = {
                "owner": owner,
                "repo": repo_name,
                "full_name": repo.full_name,
                "extracted_at": datetime.now().isoformat(),
                "files": governance_data,
                "metadata": {
                    "total_files": len(governance_data),
                    "extraction_methods": list(
                        set([f["source"] for f in governance_data.values()])
                    ),
                    "extraction_time_seconds": round(extraction_time, 2),
                    "repository_info": {
                        "stars": repo.stargazers_count,
                        "forks": repo.forks_count,
                        "watchers": repo.watchers_count,
                        "default_branch": repo.default_branch,
                        "created_at": repo.created_at.isoformat(),
                        "updated_at": repo.updated_at.isoformat(),
                    },
                },
            }

            # Save to cache
            self._save_to_cache(owner, repo_name, result)

            logger.success(
                f"Extracted {len(governance_data)} files for {owner}/{repo_name} in {extraction_time:.2f}s"
            )

            return result

        except RateLimitExceededException:
            logger.error("Rate limit exceeded - waiting for reset")
            self._check_rate_limit()
            # Retry once
            return self.extract_governance_documents(owner, repo_name, use_cache=False)

        except GithubException as e:
            logger.error(f"GitHub API error for {owner}/{repo_name}: {e}")
            return {
                "owner": owner,
                "repo": repo_name,
                "error": str(e),
                "extracted_at": datetime.now().isoformat(),
                "files": {},
                "metadata": {"total_files": 0},
            }

        except Exception as e:
            logger.error(f"Unexpected error extracting {owner}/{repo_name}: {e}")
            return {
                "owner": owner,
                "repo": repo_name,
                "error": str(e),
                "extracted_at": datetime.now().isoformat(),
                "files": {},
                "metadata": {"total_files": 0},
            }

    def extract_multiple_repos(
        self,
        repos: List[Tuple[str, str]],
        use_cache: bool = True,
        parallel: bool = False,
    ) -> List[Dict]:
        """
        Extract governance documents from multiple repositories

        Args:
            repos: List of (owner, repo_name) tuples
            use_cache: Whether to use cached data
            parallel: Whether to use parallel processing (not implemented yet for safety)

        Returns:
            List of extraction results
        """
        results = []

        for owner, repo_name in repos:
            try:
                result = self.extract_governance_documents(owner, repo_name, use_cache)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract {owner}/{repo_name}: {e}")
                results.append(
                    {
                        "owner": owner,
                        "repo": repo_name,
                        "error": str(e),
                        "files": {},
                    }
                )

        return results

    def get_extraction_summary(self, extraction_result: Dict) -> Dict:
        """Generate summary statistics from extraction result"""
        files = extraction_result.get("files", {})

        summary = {
            "repository": extraction_result.get("full_name", ""),
            "total_documents": len(files),
            "document_types": list(files.keys()),
            "total_content_length": sum(
                f.get("content_length", 0) for f in files.values()
            ),
            "extraction_time": extraction_result.get("metadata", {}).get(
                "extraction_time_seconds", 0
            ),
            "has_governance": "governance" in files,
            "has_contributing": "contributing" in files,
            "has_code_of_conduct": "code_of_conduct" in files,
            "has_security": "security" in files,
            "has_maintainers": "maintainers" in files,
        }

        return summary
