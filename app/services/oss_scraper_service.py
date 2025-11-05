"""
Python-based OSS Scraper Service
Extracts issues, PRs, commits, and comments from GitHub repositories
Alternative to Rust-based OSSPREY-OSS-Scraper-Tool with better integration
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

from github import Github, GithubException
from github.Repository import Repository

from app.core.config import settings


class OSSScraperService:
    """
    Python-based scraper for GitHub socio-technical data

    Extracts:
    - Issues (open + closed)
    - Pull Requests
    - Commits with file changes
    - Comments on issues and PRs
    - Developer collaboration data
    """

    def __init__(self, github_token: str = None):
        """Initialize scraper with GitHub authentication"""
        token = github_token or settings.github_token
        self.github = Github(token, per_page=100)
        self.output_base = Path("../data/scraped")
        self.output_base.mkdir(parents=True, exist_ok=True)

        logger.info(f"OSSScraperService initialized")

    def scrape_project(
        self,
        owner: str,
        repo: str,
        max_issues: int = 500,
        max_prs: int = 500,
        max_commits: int = 1000
    ) -> Dict[str, str]:
        """
        Scrape complete project data

        Args:
            owner: Repository owner
            repo: Repository name
            max_issues: Maximum issues to fetch
            max_prs: Maximum PRs to fetch
            max_commits: Maximum commits to fetch

        Returns:
            Dict with paths to generated CSV files
        """
        project_id = f"{owner}-{repo}"
        output_dir = self.output_base / project_id
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Scraping project: {owner}/{repo}")

        try:
            repository = self.github.get_repo(f"{owner}/{repo}")

            # Scrape issues
            issues_csv = self._scrape_issues(repository, output_dir, max_issues)

            # Scrape pull requests
            prs_csv = self._scrape_pull_requests(repository, output_dir, max_prs)

            # Scrape commits with file changes (for Graph RAG)
            commits_csv = self._scrape_commits(repository, output_dir, max_commits)

            logger.success(f"Scraping complete for {owner}/{repo}")

            return {
                "project_id": project_id,
                "issues_csv": str(issues_csv),
                "prs_csv": str(prs_csv),
                "commits_csv": str(commits_csv),
                "commit_file_dev_csv": str(commits_csv),  # Alias for Graph RAG
                "status": "success"
            }

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return {"status": "error", "error": str(e)}

    def _scrape_issues(
        self,
        repository: Repository,
        output_dir: Path,
        max_issues: int
    ) -> Path:
        """
        Scrape all issues (open + closed) with metadata and comments

        CSV Columns:
        - number, title, state, author, created_at, updated_at, closed_at
        - body, labels, assignees, comments_count
        """
        issues_csv = output_dir / "issues.csv"

        logger.info(f"Scraping issues (max={max_issues})...")

        with open(issues_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'number', 'title', 'state', 'author', 'author_association',
                'created_at', 'updated_at', 'closed_at', 'body',
                'labels', 'assignees', 'comments_count', 'url'
            ])

            # Fetch issues (both open and closed)
            count = 0
            for issue in repository.get_issues(state='all'):
                # Skip pull requests (they're included in issues API)
                if issue.pull_request:
                    continue

                writer.writerow([
                    issue.number,
                    issue.title,
                    issue.state,
                    issue.user.login if issue.user else '',
                    issue.author_association if hasattr(issue, 'author_association') else '',
                    issue.created_at.isoformat() if issue.created_at else '',
                    issue.updated_at.isoformat() if issue.updated_at else '',
                    issue.closed_at.isoformat() if issue.closed_at else '',
                    (issue.body or '')[:5000],  # Limit body length
                    ','.join([label.name for label in issue.labels]),
                    ','.join([a.login for a in issue.assignees]) if issue.assignees else '',
                    issue.comments,
                    issue.html_url
                ])

                count += 1
                if count >= max_issues:
                    break

                if count % 100 == 0:
                    logger.info(f"Scraped {count} issues...")

        logger.success(f"Scraped {count} issues → {issues_csv}")
        return issues_csv

    def _scrape_pull_requests(
        self,
        repository: Repository,
        output_dir: Path,
        max_prs: int
    ) -> Path:
        """
        Scrape all pull requests with metadata

        CSV Columns:
        - number, title, state, author, created_at, updated_at, merged_at
        - body, labels, reviewers, comments_count, additions, deletions
        """
        prs_csv = output_dir / "pull_requests.csv"

        logger.info(f"Scraping pull requests (max={max_prs})...")

        with open(prs_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'number', 'title', 'state', 'author', 'created_at', 'updated_at',
                'merged_at', 'closed_at', 'body', 'labels', 'comments_count',
                'additions', 'deletions', 'changed_files', 'url'
            ])

            count = 0
            for pr in repository.get_pulls(state='all'):
                writer.writerow([
                    pr.number,
                    pr.title,
                    pr.state,
                    pr.user.login if pr.user else '',
                    pr.created_at.isoformat() if pr.created_at else '',
                    pr.updated_at.isoformat() if pr.updated_at else '',
                    pr.merged_at.isoformat() if pr.merged_at else '',
                    pr.closed_at.isoformat() if pr.closed_at else '',
                    (pr.body or '')[:5000],
                    ','.join([label.name for label in pr.labels]),
                    pr.comments,
                    pr.additions or 0,
                    pr.deletions or 0,
                    pr.changed_files or 0,
                    pr.html_url
                ])

                count += 1
                if count >= max_prs:
                    break

                if count % 50 == 0:
                    logger.info(f"Scraped {count} PRs...")

        logger.success(f"Scraped {count} pull requests → {prs_csv}")
        return prs_csv

    def _scrape_commits(
        self,
        repository: Repository,
        output_dir: Path,
        max_commits: int
    ) -> Path:
        """
        Scrape commits with file changes for Graph RAG

        CSV Columns (compatible with OSSPREY-OSS-Scraper-Tool format):
        - project_name, commit_number, commit_hash, author_email, author_name
        - commit_date, commit_timestamp, file_path, change_type
        - lines_added, lines_deleted

        This format matches the Hama-commit-file-dev.csv structure
        """
        commits_csv = output_dir / "commit-file-dev.csv"

        logger.info(f"Scraping commits with file changes (max={max_commits})...")

        project_name = repository.full_name

        with open(commits_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # NO HEADER - matches OSSPREY scraper format
            # Columns: project_name, incubation_start, incubation_end, status,
            #          commit_number, commit_hash, author_email, author_name,
            #          commit_date, commit_timestamp, file_path, change_type,
            #          lines_added, lines_deleted

            count = 0
            commit_number = 0

            for commit in repository.get_commits():
                commit_number += 1

                # Get commit details
                commit_hash = commit.sha
                author_name = commit.commit.author.name if commit.commit.author else ''
                author_email = commit.commit.author.email if commit.commit.author else ''
                commit_date = commit.commit.author.date.strftime('%Y-%m-%d') if commit.commit.author else ''
                commit_timestamp = commit.commit.author.date.isoformat() if commit.commit.author else ''

                # Get files changed in this commit
                try:
                    files = commit.files or []

                    if not files:
                        # If no files, still record the commit with empty file
                        writer.writerow([
                            project_name,  # project_name
                            '',  # incubation_start (empty for non-incubator projects)
                            '',  # incubation_end
                            '',  # status
                            commit_number,  # commit_number
                            commit_hash,  # commit_hash
                            author_email,  # author_email
                            author_name,  # author_name
                            commit_date,  # commit_date
                            commit_timestamp,  # commit_timestamp
                            '',  # file_path
                            '',  # change_type
                            0,  # lines_added
                            0   # lines_deleted
                        ])
                    else:
                        # One row per file changed
                        for file in files:
                            writer.writerow([
                                project_name,
                                '',  # incubation_start
                                '',  # incubation_end
                                '',  # status
                                commit_number,
                                commit_hash,
                                author_email,
                                author_name,
                                commit_date,
                                commit_timestamp,
                                file.filename,  # file_path
                                file.status,  # change_type (added/modified/removed)
                                file.additions or 0,  # lines_added
                                file.deletions or 0   # lines_deleted
                            ])

                except Exception as e:
                    logger.warning(f"Error processing commit {commit_hash}: {e}")
                    continue

                count += 1
                if count >= max_commits:
                    break

                if count % 100 == 0:
                    logger.info(f"Scraped {count} commits...")

        logger.success(f"Scraped {count} commits → {commits_csv}")
        return commits_csv

    def get_scraper_stats(self, owner: str, repo: str) -> Dict:
        """Get statistics about scraped data"""
        project_id = f"{owner}-{repo}"
        output_dir = self.output_base / project_id

        if not output_dir.exists():
            return {"status": "not_scraped"}

        stats = {"project_id": project_id}

        # Count issues
        issues_csv = output_dir / "issues.csv"
        if issues_csv.exists():
            with open(issues_csv, 'r') as f:
                stats["issues_count"] = sum(1 for _ in f) - 1  # Subtract header

        # Count PRs
        prs_csv = output_dir / "pull_requests.csv"
        if prs_csv.exists():
            with open(prs_csv, 'r') as f:
                stats["prs_count"] = sum(1 for _ in f) - 1

        # Count commits
        commits_csv = output_dir / "commit-file-dev.csv"
        if commits_csv.exists():
            with open(commits_csv, 'r') as f:
                stats["commit_records"] = sum(1 for _ in f)  # No header

        return stats


# Singleton instance
_scraper_instance: Optional[OSSScraperService] = None


def get_oss_scraper() -> OSSScraperService:
    """Get or create singleton scraper instance"""
    global _scraper_instance

    if _scraper_instance is None:
        _scraper_instance = OSSScraperService()

    return _scraper_instance
