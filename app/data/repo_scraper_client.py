"""
Repository Scraper API Client
Fetches commits and issues data from external scraping API
"""
import requests
from typing import Dict, Optional, Tuple
from loguru import logger
import time


class RepoScraperClient:
    """
    Client for interacting with the repository scraping API

    Handles:
    - API requests with retry logic
    - Error handling and validation
    - Data normalization
    """

    def __init__(self, api_url: str = "https://ossprey.ngrok.app/api/scrape_repository"):
        """
        Initialize the scraper client

        Args:
            api_url: Base URL for the scraping API
        """
        self.api_url = api_url
        self.timeout = 300  # 5 minutes timeout for scraping operations
        self.max_retries = 3

        logger.info(f"🌐 RepoScraperClient initialized: {self.api_url}")

    def scrape_repository(self, github_url: str) -> Tuple[bool, Dict]:
        """
        Scrape repository data from the external API

        Args:
            github_url: Full GitHub repository URL (https://github.com/owner/repo)

        Returns:
            Tuple of (success: bool, data: dict)

            On success, data contains:
            {
                "fetch_github_issues": [...],
                "commit_devs_files": [...],
                "metadata": {
                    "fetched_at": timestamp,
                    "github_url": url,
                    "commits_count": int,
                    "issues_count": int
                }
            }

            On failure, data contains:
            {
                "error": str,
                "details": str
            }
        """
        logger.info(f"📡 Fetching data for {github_url} from scraping API...")

        for attempt in range(1, self.max_retries + 1):
            try:
                # Make API request
                response = requests.post(
                    self.api_url,
                    json={"github_link": github_url},
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )

                # Handle successful response
                if response.status_code == 200:
                    data = response.json()

                    # Validate response structure
                    if not self._validate_response(data):
                        return False, {
                            "error": "Invalid API response structure",
                            "details": "Response missing required fields: fetch_github_issues or commit_devs_files"
                        }

                    # Add metadata
                    commits_count = len(data.get("commit_devs_files", []))
                    issues_count = len(data.get("fetch_github_issues", []))

                    data["metadata"] = {
                        "fetched_at": time.time(),
                        "github_url": github_url,
                        "commits_count": commits_count,
                        "issues_count": issues_count,
                        "source": "api"
                    }

                    logger.info(f"✅ Successfully fetched {commits_count} commits and {issues_count} issues")
                    return True, data

                # Handle error responses
                elif response.status_code >= 400:
                    error_msg = f"API error: HTTP {response.status_code}"
                    try:
                        error_detail = response.json().get("detail", response.text)
                    except:
                        error_detail = response.text[:500]  # Truncate long error messages

                    logger.warning(f"❌ {error_msg} - {error_detail} (attempt {attempt}/{self.max_retries})")

                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return False, {
                            "error": error_msg,
                            "details": error_detail
                        }

                    # Retry on server errors (5xx)
                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        return False, {
                            "error": error_msg,
                            "details": error_detail
                        }

            except requests.Timeout:
                logger.warning(f"⏱️  Request timeout (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return False, {
                        "error": "Request timeout",
                        "details": f"API did not respond within {self.timeout} seconds"
                    }

            except requests.RequestException as e:
                logger.error(f"🔥 Request failed: {e} (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return False, {
                        "error": "Network error",
                        "details": str(e)
                    }

            except Exception as e:
                logger.error(f"🔥 Unexpected error: {e}")
                return False, {
                    "error": "Unexpected error",
                    "details": str(e)
                }

        # Should not reach here, but just in case
        return False, {
            "error": "Max retries exceeded",
            "details": f"Failed after {self.max_retries} attempts"
        }

    def _validate_response(self, data: Dict) -> bool:
        """
        Validate API response structure

        Args:
            data: API response data

        Returns:
            True if valid, False otherwise
        """
        # Check for required fields
        has_issues = "fetch_github_issues" in data
        has_commits = "commit_devs_files" in data

        if not (has_issues or has_commits):
            logger.warning("⚠️  API response missing both 'fetch_github_issues' and 'commit_devs_files'")
            return False

        # Validate that fields are lists
        if has_issues and not isinstance(data["fetch_github_issues"], list):
            logger.warning("⚠️  'fetch_github_issues' is not a list")
            return False

        if has_commits and not isinstance(data["commit_devs_files"], list):
            logger.warning("⚠️  'commit_devs_files' is not a list")
            return False

        return True

    def check_health(self) -> bool:
        """
        Check if the scraping API is available

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Try a lightweight request (assuming health endpoint exists)
            # If not, this will timeout quickly and return False
            response = requests.get(
                self.api_url.replace("/scrape_repository", "/health"),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
