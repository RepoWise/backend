"""
CSV Data Engine for Commits and Issues
Handles structured queries on CSV data with LLM-powered query generation
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
from pathlib import Path
from loguru import logger
import json
import re
from datetime import datetime
from app.core.config import settings


class CSVDataEngine:
    """
    Engine for querying commits and issues CSV data

    Supports:
    - Loading and caching CSV data per project
    - Natural language to DataFrame query translation
    - Statistical aggregations
    - Time-series analysis
    - Contributor analysis
    """

    def __init__(self, llm_client=None):
        """Initialize CSV data engine with in-memory storage"""
        # In-memory cache: {project_id: {"commits": df, "issues": df}}
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}

        # Track fetch status: {project_id: {"commits": {"status": "fetching"|"ready"|"failed", "started_at": datetime, "error": str}, "issues": {...}}}
        self.data_fetching_status: Dict[str, Dict[str, Dict]] = {}

        # LLM client for dynamic query generation
        self.llm_client = llm_client

        # Store last generated pandas code for retrieval
        self.last_generated_code = ""

        logger.info("CSV Data Engine initialized (in-memory storage)")

    def mark_fetch_started(self, project_id: str, data_type: str):
        """Mark that data fetching has started for a project"""
        if project_id not in self.data_fetching_status:
            self.data_fetching_status[project_id] = {}

        self.data_fetching_status[project_id][data_type] = {
            "status": "fetching",
            "started_at": datetime.now(),
            "error": None
        }
        logger.info(f"⏳ Marked {data_type} fetch as STARTED for {project_id}")

    def mark_fetch_complete(self, project_id: str, data_type: str):
        """Mark that data fetching has completed successfully"""
        if project_id in self.data_fetching_status and data_type in self.data_fetching_status[project_id]:
            self.data_fetching_status[project_id][data_type]["status"] = "ready"
            logger.info(f"✅ Marked {data_type} fetch as COMPLETE for {project_id}")

    def mark_fetch_failed(self, project_id: str, data_type: str, error: str):
        """Mark that data fetching has failed"""
        if project_id not in self.data_fetching_status:
            self.data_fetching_status[project_id] = {}

        self.data_fetching_status[project_id][data_type] = {
            "status": "failed",
            "started_at": self.data_fetching_status.get(project_id, {}).get(data_type, {}).get("started_at", datetime.now()),
            "error": error
        }
        logger.error(f"❌ Marked {data_type} fetch as FAILED for {project_id}: {error}")

    def get_fetch_status(self, project_id: str, data_type: str) -> Optional[Dict]:
        """Get the current fetch status for a data type"""
        return self.data_fetching_status.get(project_id, {}).get(data_type)

    def get_elapsed_time(self, project_id: str, data_type: str) -> Optional[int]:
        """Get elapsed time in seconds since fetch started"""
        status = self.get_fetch_status(project_id, data_type)
        if status and status.get("started_at"):
            elapsed = (datetime.now() - status["started_at"]).total_seconds()
            return int(elapsed)
        return None

    def load_project_data(self, project_id: str, commits_path: Optional[str] = None,
                         issues_path: Optional[str] = None) -> Dict[str, bool]:
        """
        Load commits and issues CSV data for a project

        Args:
            project_id: Project identifier
            commits_path: Path to commits CSV file
            issues_path: Path to issues CSV file

        Returns:
            Status dict with loading results
        """
        result = {"commits_loaded": False, "issues_loaded": False}

        if project_id not in self.data_cache:
            self.data_cache[project_id] = {}

        # Load commits CSV
        if commits_path and Path(commits_path).exists():
            try:
                # Read CSV with actual headers
                df = pd.read_csv(commits_path)

                # Convert date columns to datetime
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], utc=True, errors='coerce')
                if 'date_time' in df.columns:
                    df['date_time'] = pd.to_datetime(df['date_time'], utc=True, errors='coerce')

                # timestamp might already exist in CSV, otherwise create alias
                if 'timestamp' not in df.columns and 'date_time' in df.columns:
                    df['timestamp'] = df['date_time']

                self.data_cache[project_id]["commits"] = df
                result["commits_loaded"] = True
                logger.info(f"✅ Loaded {len(df)} commits for {project_id}")
            except Exception as e:
                logger.error(f"Error loading commits CSV: {e}")

        # Load issues CSV
        if issues_path and Path(issues_path).exists():
            try:
                df = pd.read_csv(issues_path)

                # Normalize column names for compatibility
                column_mapping = {
                    'number': 'issue_num',
                    'state': 'issue_state',
                    'author': 'user_login',
                }
                df = df.rename(columns=column_mapping)

                # Convert date columns
                if 'created_at' in df.columns:
                    df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                if 'updated_at' in df.columns:
                    df['updated_at'] = pd.to_datetime(df['updated_at'], utc=True, errors='coerce')

                # Add type column if missing (assume all are issues if not specified)
                if 'type' not in df.columns:
                    df['type'] = 'issue'

                self.data_cache[project_id]["issues"] = df
                result["issues_loaded"] = True
                logger.info(f"✅ Loaded {len(df)} issues for {project_id}")
            except Exception as e:
                logger.error(f"Error loading issues CSV: {e}")

        return result

    def load_from_api_data(self, project_id: str, api_data: Dict) -> Dict:
        """
        Load commits and issues data from API response (JSON format)

        Args:
            project_id: Project identifier
            api_data: Data from scraping API containing:
                - commit_devs_files: List of commit records
                - fetch_github_issues: List of issue records

        Returns:
            Status dict with loading results and counts
        """
        result = {
            "commits_loaded": False,
            "issues_loaded": False,
            "commits_count": 0,
            "issues_count": 0
        }

        if project_id not in self.data_cache:
            self.data_cache[project_id] = {}

        # Load commits from API data
        commits_data = api_data.get("commit_devs_files", [])
        if commits_data:
            try:
                # Convert list of dicts to DataFrame
                df = pd.DataFrame(commits_data)

                # Normalize column names to match CSV format
                # Expected columns: commit_sha, name, email, date/timestamp, message, filename, lines_added, lines_deleted
                column_mapping = {
                    "commit_hash": "commit_sha",
                    "author_name": "name",
                    "author_email": "email",
                    "commit_date": "date",
                    "commit_message": "message",
                    "file_path": "filename",
                    # Keep other columns as-is
                }
                df = df.rename(columns=column_mapping)

                # Convert date columns to datetime
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], utc=True, errors='coerce')
                if 'date_time' in df.columns:
                    df['date_time'] = pd.to_datetime(df['date_time'], utc=True, errors='coerce')
                elif 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')

                # Create timestamp alias if not exists
                if 'timestamp' not in df.columns and 'date' in df.columns:
                    df['timestamp'] = df['date']
                elif 'timestamp' not in df.columns and 'date_time' in df.columns:
                    df['timestamp'] = df['date_time']

                # Ensure required columns exist with default values
                if 'lines_added' not in df.columns:
                    df['lines_added'] = 0
                if 'lines_deleted' not in df.columns:
                    df['lines_deleted'] = 0

                self.data_cache[project_id]["commits"] = df
                result["commits_loaded"] = True
                result["commits_count"] = len(df)
                logger.info(f"✅ Loaded {len(df)} commits from API data for {project_id}")
            except Exception as e:
                logger.error(f"Error loading commits from API data: {e}")

        # Load issues from API data
        issues_data = api_data.get("fetch_github_issues", [])
        if issues_data:
            try:
                # Convert list of dicts to DataFrame
                df = pd.DataFrame(issues_data)

                # Normalize column names for compatibility
                column_mapping = {
                    'number': 'issue_num',
                    'state': 'issue_state',
                    'author': 'user_login',
                    'reporter': 'user_login',
                    'comments': 'comment_count',
                    'comments_count': 'comment_count',
                }
                df = df.rename(columns=column_mapping)

                # Convert date columns
                if 'created_at' in df.columns:
                    df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                if 'updated_at' in df.columns:
                    df['updated_at'] = pd.to_datetime(df['updated_at'], utc=True, errors='coerce')

                # Add type column if missing (assume all are issues if not specified)
                if 'type' not in df.columns:
                    df['type'] = 'issue'

                # Ensure issue_num exists
                if 'issue_num' not in df.columns and 'number' in df.columns:
                    df['issue_num'] = df['number']

                self.data_cache[project_id]["issues"] = df
                result["issues_loaded"] = True
                result["issues_count"] = len(df)
                logger.info(f"✅ Loaded {len(df)} issues from API data for {project_id}")
            except Exception as e:
                logger.error(f"Error loading issues from API data: {e}")

        return result

    def query_with_llm(self, project_id: str, query: str, data_type: str = "commits",
                       limit: int = 10) -> Tuple[pd.DataFrame, str]:
        """
        Use LLM to generate and execute pandas code for custom queries

        Args:
            project_id: Project to query
            query: Natural language query
            data_type: "commits" or "issues"
            limit: Maximum results to return

        Returns:
            (results_df, summary_text)

        Note: The generated pandas code is stored in self.last_generated_code
        """
        # Initialize last generated code
        self.last_generated_code = ""
        if not self.llm_client:
            logger.warning("LLM client not available, falling back to default query")
            return pd.DataFrame(), "LLM query generation not available"

        # Get the DataFrame
        if project_id not in self.data_cache or data_type not in self.data_cache[project_id]:
            return pd.DataFrame(), f"No {data_type} data available for {project_id}"

        df = self.data_cache[project_id][data_type]

        # Get DataFrame schema
        schema_info = {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "row_count": len(df)
        }

        # Create comprehensive prompt for LLM to generate pandas code
        # Add data-type-specific column hints with COMPLETE schema
        if data_type == "commits":
            schema_hint = """
COMMITS DATA SCHEMA - ALL COLUMNS (use these EXACT column names):
| Column          | Type    | Description                                           |
|-----------------|---------|-------------------------------------------------------|
| commit_sha      | string  | Unique commit identifier (use for deduplication)      |
| name            | string  | Contributor name - USE THIS for "who" questions       |
| email           | string  | Contributor email address                             |
| date            | datetime| Commit timestamp (already parsed as datetime)         |
| timestamp       | int     | Unix timestamp of commit                              |
| filename        | string  | File path modified - USE THIS, NOT 'filepath'         |
| change_type     | string  | 'A' (added), 'M' (modified), 'D' (deleted)           |
| lines_added     | int     | Number of lines added in this file                    |
| lines_deleted   | int     | Number of lines deleted in this file                  |
| commit_message  | string  | Full commit message text                              |
| commit_url      | string  | GitHub URL to the commit                              |
| project         | string  | Project name                                          |

CRITICAL RULES FOR COMMITS:
1. ONE ROW PER FILE MODIFIED, not one row per commit
2. To count COMMITS: df.drop_duplicates(subset=['commit_sha'])
3. To count FILE MODIFICATIONS: use df directly (no dedup)
4. Use 'name' for contributor names, NOT 'user_login'
5. Use 'filename' for file paths, NOT 'filepath'
6. Use 'commit_message' for message text, NOT 'message'"""
        else:  # issues
            schema_hint = """
ISSUES DATA SCHEMA - ALL COLUMNS (use these EXACT column names):
| Column          | Type    | Description                                           |
|-----------------|---------|-------------------------------------------------------|
| type            | string  | 'issue' or 'comment' - FILTER BY THIS                 |
| issue_num       | int     | Issue number (e.g., 123 for issue #123)              |
| title           | string  | Issue title (only for type='issue')                   |
| user_login      | string  | GitHub username - USE THIS for "who" questions        |
| user_name       | string  | Display name of user                                  |
| user_email      | string  | Email of user                                         |
| user_id         | int     | GitHub user ID                                        |
| issue_state     | string  | 'OPEN' or 'CLOSED' (uppercase, use .str.lower())     |
| created_at      | datetime| When issue/comment was created                        |
| updated_at      | datetime| When issue/comment was last updated                   |
| body            | string  | Issue/comment content text                            |
| reactions       | string  | JSON string with reaction counts                      |
| issue_url       | string  | API URL to the issue                                  |
| comment_url     | string  | API URL to the comment (if type='comment')           |
| repo_name       | string  | Repository name                                       |

CRITICAL RULES FOR ISSUES:
1. Dataset has BOTH issues AND comments (check 'type' column)
2. To count ISSUES: df[df['type'] == 'issue']
3. To count ISSUE REPORTERS: df[df['type'] == 'issue'].groupby('user_login')
4. Use 'user_login' for reporter names, NOT 'name'
5. issue_state is UPPERCASE ('OPEN'/'CLOSED'), use .str.lower() for comparison
6. Comments have issue_state=NaN, so filtering by state excludes comments"""

        prompt = f"""You are a pandas expert. Generate ONLY executable pandas code (no markdown, no explanations).

Query: {query}
Data type: {data_type}

{schema_hint}

═══════════════════════════════════════════════════════════════════════════════
                         MANDATORY RULES - READ FIRST
═══════════════════════════════════════════════════════════════════════════════

FOR COMMITS DATA - THESE 3 RULES ARE NON-NEGOTIABLE:
1. ALWAYS use drop_duplicates(subset=['commit_sha']) when counting commits
2. ALWAYS use 'name' column for contributor names (NEVER 'user_login')
3. ALWAYS use 'filename' column for file paths (NEVER 'filepath')

FOR ISSUES DATA:
1. ALWAYS filter df[df['type'] == 'issue'] when counting issues or reporters
2. ALWAYS use 'user_login' column for reporter names (NEVER 'name')
3. ALWAYS use .str.lower() when comparing issue_state ('OPEN'/'CLOSED')

═══════════════════════════════════════════════════════════════════════════════
                      EXACT QUERY → CODE MAPPINGS
═══════════════════════════════════════════════════════════════════════════════

Match your query to these patterns and USE THE EXACT CODE:

┌─ COMMITS QUERIES ────────────────────────────────────────────────────────────
│
│ "top 5 contributors by commit count" OR "top contributors":
│ result = df.drop_duplicates(subset=['commit_sha']).groupby('name').size().sort_values(ascending=False).head(5).reset_index(name='commit_count')
│
│ "most active contributors":
│ result = df.drop_duplicates(subset=['commit_sha']).groupby('name').size().sort_values(ascending=False).head({limit}).reset_index(name='commit_count')
│
│ "top 10 contributors in the past 6 months" OR "last 6 months":
│ result = df[df['date'] >= pd.Timestamp.now(tz='UTC') - pd.DateOffset(months=6)].drop_duplicates(subset=['commit_sha']).groupby('name').size().sort_values(ascending=False).head(10).reset_index(name='commit_count')
│
│ "contributed to documentation" OR "documentation contributors":
│ result = df[df['filename'].str.contains(r'README|\.md$|^docs/|CONTRIBUTING|CHANGELOG|LICENSE', case=False, na=False, regex=True)].drop_duplicates(subset=['commit_sha']).groupby('name').size().sort_values(ascending=False).head({limit}).reset_index(name='doc_commits')
│
│ "top five files modified the most" OR "most modified files":
│ result = df['filename'].value_counts().head(5).reset_index(name='modification_count')
│
│ "unique contributors" OR "how many contributors":
│ result = pd.DataFrame({{'unique_contributors': [df['name'].nunique()]}})
│
└──────────────────────────────────────────────────────────────────────────────

┌─ ISSUES QUERIES ─────────────────────────────────────────────────────────────
│
│ "most active issue reporters" OR "who raises most issues":
│ result = df[df['type'] == 'issue'].groupby('user_login').size().sort_values(ascending=False).head({limit}).reset_index(name='issues_reported')
│
│ "oldest open issues":
│ result = df[(df['type'] == 'issue') & (df['issue_state'].str.lower() == 'open')].sort_values('created_at', ascending=True).head({limit})[['issue_num', 'title', 'user_login', 'created_at']]
│
│ "most commented issues":
│ result = df[df['type'] == 'issue'].nlargest({limit}, 'comment_count')[['issue_num', 'title', 'comment_count', 'issue_state', 'user_login']]
│
│ "how quickly issues being closed" OR "average time to close":
│ closed_issues = df[(df['type'] == 'issue') & (df['issue_state'].str.lower() == 'closed')].copy()
│ closed_issues['time_to_close'] = (pd.to_datetime(closed_issues['updated_at']) - pd.to_datetime(closed_issues['created_at'])).dt.days
│ result = pd.DataFrame({{'avg_days_to_close': [closed_issues['time_to_close'].mean()]}})
│
└──────────────────────────────────────────────────────────────────────────────

DataFrame info: {len(schema_info['columns'])} columns, {schema_info['row_count']} rows
Columns: {', '.join(schema_info['columns'])}

CODE REQUIREMENTS:
1. Assign final result to 'result' variable
2. Use .head({limit}) to limit results
3. No imports (pd is available)

ADDITIONAL EXAMPLES (use these patterns):

# COMMITS - Always use drop_duplicates and 'name' column:
"Which files have the most lines added?"
result = df.groupby('filename')['lines_added'].sum().sort_values(ascending=False).head({limit}).reset_index()

"Bug fix commits per contributor?"
result = df[df['commit_message'].str.contains('fix|bug', case=False, na=False)].drop_duplicates(subset=['commit_sha']).groupby('name').size().sort_values(ascending=False).head({limit}).reset_index(name='bug_fixes')

"Commits per month?"
result = df.drop_duplicates(subset=['commit_sha']).groupby(df['date'].dt.to_period('M')).size().reset_index(name='commits')

"Which commit modified most files?"
result = df.groupby('commit_sha').agg({{'filename': 'count', 'name': 'first', 'commit_message': 'first'}}).sort_values('filename', ascending=False).head({limit}).reset_index()

# ISSUES - Always filter type='issue' and use 'user_login':
"Bug reports by user?"
result = df[(df['type'] == 'issue') & (df['title'].str.contains('bug', case=False, na=False))].groupby('user_login').size().sort_values(ascending=False).head({limit}).reset_index(name='bug_reports')

"Stale issues (open >6 months)?"
result = df[(df['type'] == 'issue') & (df['issue_state'].str.lower() == 'open') & (pd.to_datetime(df['created_at']) < pd.Timestamp.now(tz='UTC') - pd.DateOffset(months=6))].head({limit})[['issue_num', 'title', 'user_login', 'created_at']]

"Issue closure rate?"
issues_only = df[df['type'] == 'issue']
total = len(issues_only)
closed = len(issues_only[issues_only['issue_state'].str.lower() == 'closed'])
result = pd.DataFrame({{'total_issues': [total], 'closed_issues': [closed], 'closure_rate_pct': [(closed/total)*100 if total > 0 else 0]}})

Now generate pandas code for: "{query}"
Return ONLY executable code:"""

        try:
            # Call LLM to generate code using configured model
            generated_code = self.llm_client.generate_simple(
                prompt,
                max_tokens=500,
                temperature=0.0  # Deterministic for code generation
            ).strip()

            # Extract code from markdown blocks if present
            if "```python" in generated_code:
                match = re.search(r'```python\n(.*?)```', generated_code, re.DOTALL)
                if match:
                    generated_code = match.group(1).strip()
            elif "```" in generated_code:
                match = re.search(r'```\n(.*?)```', generated_code, re.DOTALL)
                if match:
                    generated_code = match.group(1).strip()

            logger.info(f"Generated pandas code:\n{generated_code}")

            # Store the generated code for retrieval
            self.last_generated_code = generated_code

            # Safety check: validate the code
            if not self._is_safe_pandas_code(generated_code):
                logger.error("Generated code failed safety check")
                return pd.DataFrame(), "Generated query code failed safety validation"

            # Execute the generated code
            local_vars = {'df': df, 'pd': pd, 'result': None}
            exec(generated_code, {"__builtins__": {}}, local_vars)

            result = local_vars.get('result')

            if result is None:
                logger.error("Execution did not produce any result")
                return pd.DataFrame(), "Query execution failed to produce results"

            # Auto-wrap scalar results in a DataFrame (LLM sometimes forgets to wrap)
            if not isinstance(result, pd.DataFrame):
                if isinstance(result, pd.Series):
                    # Convert Series to DataFrame
                    result = result.to_frame()
                    logger.info(f"Auto-converted Series to DataFrame")
                elif isinstance(result, (int, float, str, bool)):
                    # Wrap scalar value in a DataFrame
                    result = pd.DataFrame([{'value': result}])
                    logger.info(f"Auto-wrapped scalar {type(result).__name__} in DataFrame")
                elif isinstance(result, (list, tuple)):
                    # Wrap list/tuple in a DataFrame
                    result = pd.DataFrame([{'value': val} for val in result])
                    logger.info(f"Auto-wrapped {type(result).__name__} in DataFrame")
                elif isinstance(result, dict):
                    # Wrap dict in a DataFrame
                    result = pd.DataFrame([result])
                    logger.info(f"Auto-wrapped dict in DataFrame")
                else:
                    logger.error(f"Execution produced unsupported type: {type(result)}")
                    return pd.DataFrame(), f"Query execution produced unsupported type: {type(result).__name__}"

            summary = f"LLM-generated query returned {len(result)} results"
            logger.info(f"✅ {summary}")

            return result, summary

        except Exception as e:
            logger.error(f"Error in LLM query generation: {e}")
            return pd.DataFrame(), f"Query execution failed: {str(e)}"

    def _is_safe_pandas_code(self, code: str) -> bool:
        """
        Validate that generated code is safe to execute

        Args:
            code: Generated pandas code

        Returns:
            True if code passes safety checks
        """
        # Blacklist of dangerous operations
        dangerous_patterns = [
            r'\bexec\b', r'\beval\b', r'\b__import__\b',
            r'\bopen\b', r'\bfile\b', r'\bos\.', r'\bsys\.',
            r'\bsubprocess\b', r'\bshutil\b', r'\bpickle\b',
            r'\bimport\b', r'\bfrom\s+\w+\s+import\b',
            r'__.*__',  # Dunder methods
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return False

        # Code must create 'result' variable
        if 'result' not in code:
            logger.warning("Code does not assign to 'result' variable")
            return False

        return True

    def query_commits(self, project_id: str, query_type: str,
                     limit: int = 10, **kwargs) -> Tuple[pd.DataFrame, str]:
        """
        Query commits data

        Query types:
        - "latest": Most recent commits
        - "by_author": Commits by specific author
        - "by_file": Commits affecting specific file
        - "stats": Aggregate statistics
        - "top_contributors": Most active contributors

        Args:
            project_id: Project to query
            query_type: Type of query
            limit: Maximum results
            **kwargs: Additional query parameters

        Returns:
            (results_df, summary_text)
        """
        if project_id not in self.data_cache or "commits" not in self.data_cache[project_id]:
            return pd.DataFrame(), f"No commits data available for {project_id}"

        df = self.data_cache[project_id]["commits"]

        if query_type == "latest":
            # Most recent DISTINCT commits (deduplicate by commit_sha)
            # First get unique commits by timestamp, then take top N
            unique_commits = df.drop_duplicates(subset=['commit_sha'], keep='first')
            result = unique_commits.nlargest(limit, 'timestamp')[
                ['commit_sha', 'name', 'email', 'date', 'timestamp']
            ].sort_values('timestamp', ascending=False).drop(columns=['timestamp'])
            summary = f"Latest {len(result)} distinct commits"

        elif query_type == "by_author":
            author = kwargs.get('author', '')
            result = df[df['name'].str.contains(author, case=False, na=False)].head(limit)
            summary = f"Commits by {author}: {len(result)} found"

        elif query_type == "by_file":
            filename = kwargs.get('filename', '')
            result = df[df['filename'].str.contains(filename, case=False, na=False)].head(limit)
            summary = f"Commits affecting {filename}: {len(result)} found"

        elif query_type == "top_contributors":
            # Top contributors by commit count
            # IMPORTANT: Use nunique() to count unique commits, not rows (which are per-file)
            contributors = df.groupby(['name', 'email']).agg({
                'commit_sha': 'nunique',  # Count unique commits, not file changes
                'lines_added': 'sum',
                'lines_deleted': 'sum'
            }).rename(columns={'commit_sha': 'commit_count'})

            contributors['total_changes'] = contributors['lines_added'] + contributors['lines_deleted']
            result = contributors.nlargest(limit, 'commit_count').sort_values('commit_count', ascending=False).reset_index()
            summary = f"Top {len(result)} contributors by commit count"

        elif query_type == "stats":
            # Overall statistics
            # IMPORTANT: Count unique commits, not rows (which are per-file)
            total_commits = df['commit_sha'].nunique()
            unique_authors = df['email'].nunique()
            total_files = df['filename'].nunique()
            date_range = f"{df['date'].min()} to {df['date'].max()}"

            stats = {
                'total_commits': total_commits,
                'unique_authors': unique_authors,
                'total_files_changed': total_files,
                'date_range': date_range
            }
            result = pd.DataFrame([stats])
            summary = f"Project statistics: {total_commits} commits by {unique_authors} authors"

        elif query_type == "unique_contributors":
            # Count unique contributors (by name or email)
            unique_by_name = df['name'].nunique()
            unique_by_email = df['email'].nunique()

            result = pd.DataFrame([{
                'unique_contributors_by_name': unique_by_name,
                'unique_contributors_by_email': unique_by_email,
                'unique_contributors': unique_by_name  # Primary metric
            }])
            summary = f"Unique contributors: {unique_by_name} (by name), {unique_by_email} (by email)"

        else:
            result = df.head(limit)
            summary = f"Default query: {len(result)} commits"

        return result, summary

    def query_issues(self, project_id: str, query_type: str,
                    limit: int = 10, **kwargs) -> Tuple[pd.DataFrame, str]:
        """
        Query issues data

        Query types:
        - "latest": Most recent issues
        - "open": Open issues
        - "closed": Closed issues
        - "by_user": Issues by specific user
        - "most_commented": Issues with most comments
        - "stats": Aggregate statistics

        Args:
            project_id: Project to query
            query_type: Type of query
            limit: Maximum results
            **kwargs: Additional query parameters

        Returns:
            (results_df, summary_text)
        """
        if project_id not in self.data_cache or "issues" not in self.data_cache[project_id]:
            return pd.DataFrame(), f"No issues data available for {project_id}"

        # Filter for actual issues (not comments)
        df = self.data_cache[project_id]["issues"]
        issues_df = df[df['type'] == 'issue'].copy()

        if query_type == "latest":
            result = issues_df.nlargest(limit, 'created_at')[
                ['issue_num', 'title', 'user_login', 'issue_state', 'created_at']
            ].sort_values('created_at', ascending=False)
            summary = f"Latest {len(result)} issues"

        elif query_type == "open":
            # Use case-insensitive comparison (CSV has lowercase "open")
            open_issues = issues_df[issues_df['issue_state'].str.lower() == 'open']
            result = open_issues.nlargest(limit, 'created_at')[
                ['issue_num', 'title', 'user_login', 'created_at']
            ].sort_values('created_at', ascending=False)
            summary = f"Open issues: {len(result)} shown (total: {len(open_issues)})"

        elif query_type == "closed":
            # Use case-insensitive comparison (CSV has lowercase "closed")
            closed_issues = issues_df[issues_df['issue_state'].str.lower() == 'closed']
            result = closed_issues.nlargest(limit, 'updated_at')[
                ['issue_num', 'title', 'user_login', 'created_at', 'updated_at']
            ].sort_values('updated_at', ascending=False)
            summary = f"Closed issues: {len(result)} shown (total: {len(closed_issues)})"

        elif query_type == "by_user":
            user = kwargs.get('user', '')
            result = issues_df[issues_df['user_login'].str.contains(user, case=False, na=False)].head(limit)
            summary = f"Issues by {user}: {len(result)} found"

        elif query_type == "most_commented":
            # Count comments per issue
            all_df = df.copy()
            comment_counts = all_df[all_df['type'] == 'comment'].groupby('issue_num').size()
            issues_df['comment_count'] = issues_df['issue_num'].map(comment_counts).fillna(0)

            result = issues_df.nlargest(limit, 'comment_count')[
                ['issue_num', 'title', 'user_login', 'comment_count', 'issue_state']
            ].sort_values('comment_count', ascending=False)
            summary = f"Most commented issues: {len(result)} shown"

        elif query_type == "stats":
            total_issues = len(issues_df)
            # Use case-insensitive comparison for state (CSV has lowercase "open"/"closed")
            open_count = len(issues_df[issues_df['issue_state'].str.lower() == 'open'])
            closed_count = len(issues_df[issues_df['issue_state'].str.lower() == 'closed'])
            unique_reporters = issues_df['user_login'].nunique()

            stats = {
                'total_issues': total_issues,
                'open_issues': open_count,
                'closed_issues': closed_count,
                'unique_reporters': unique_reporters
            }
            result = pd.DataFrame([stats])
            summary = f"Issue statistics: {total_issues} total ({open_count} open, {closed_count} closed)"

        else:
            result = issues_df.head(limit)
            summary = f"Default query: {len(result)} issues"

        return result, summary

    def get_context_for_query(self, project_id: str, query: str,
                             data_type: str = "commits") -> Tuple[str, List[Dict]]:
        """
        Get formatted context for LLM based on natural language query

        This analyzes the query and retrieves relevant data

        Args:
            project_id: Project to query
            query: Natural language query
            data_type: "commits" or "issues"

        Returns:
            (formatted_context, source_records)
        """
        query_lower = query.lower()

        # Determine query type from natural language (expanded keyword matching)
        if data_type == "commits":
            # SIMPLE QUERIES - These can work with predefined methods on sample data
            # Unique contributors (must be checked BEFORE aggregation queries)
            if any(kw in query_lower for kw in ["unique contributor", "distinct contributor", "how many contributor", "number of contributor", "count contributor"]):
                df, summary = self.query_commits(project_id, "unique_contributors")
            # Latest commits (exclude ranking queries like "top", "most" to prevent misrouting)
            # Also handle "commit history" as latest commits
            elif (any(kw in query_lower for kw in ["latest", "recent", "newest", "last", "commit history"]) and
                  not any(kw in query_lower for kw in ["average", "trend", "pattern", "all", "every", "top", "most", "highest", "largest", "biggest", "contributor", "week", "month", "quarter", "year"])):
                # Detect singular vs plural to determine limit
                # Singular: "latest commit", "last commit", "recent commit" → limit=1
                # Plural: "latest commits", "recent commits" → limit=5 (default)
                is_singular = any(phrase in query_lower for phrase in [
                    "latest commit ", "latest commit?", "latest commit.",
                    "recent commit ", "recent commit?", "recent commit.",
                    "last commit ", "last commit?", "last commit.",
                    "newest commit ", "newest commit?", "newest commit.",
                    "show me the commit", "what is the commit", "what's the commit"
                ])
                limit = 1 if is_singular else 5
                df, summary = self.query_commits(project_id, "latest", limit=limit)
            # Basic stats (uses predefined aggregation)
            # Also handle "contributor statistics" and "development activity"
            elif (query_lower in ["stats", "statistics", "summary", "contributor statistics"] or
                  any(kw in query_lower for kw in ["how many total", "total commits", "total authors", "development activity", "how active"]) and "average" not in query_lower):
                df, summary = self.query_commits(project_id, "stats")

            # COMPLEX QUERIES - These need full dataset access via LLM pandas generation

            # Temporal queries (must check BEFORE aggregation to catch "commits from last month", "pull requests from last week")
            elif any(kw in query_lower for kw in ["last month", "last week", "past month", "past week", "past year", "this quarter", "this month", "this year", "past 6 months", "past 3 months"]):
                logger.info(f"Detected temporal query requiring date filtering, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

            # Core developer queries (top contributors by commit count)
            # Handle singular vs plural for appropriate result limit
            elif any(kw in query_lower for kw in ["core developer", "key developer", "main developer", "active developer"]):
                # Detect singular vs plural to determine limit
                # Singular: "who is the core developer" → limit=1 (top contributor)
                # Plural: "who are the core developers" → limit=5 (top 5 contributors)
                #
                # IMPORTANT: Check for PLURAL first since "developer" is substring of "developers"
                is_plural = any(phrase in query_lower for phrase in [
                    "core developers", "key developers", "main developers", "active developers"
                ])
                # If not explicitly plural, check for singular patterns
                is_singular = not is_plural and any(phrase in query_lower for phrase in [
                    "core developer", "key developer", "main developer", "active developer",
                    "is the core", "is the key", "is the main", "is the active"
                ])
                limit = 1 if is_singular else 5
                logger.info(f"Detected core developer query ({'singular' if is_singular else 'plural'}), returning top {limit} contributors")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=limit)

            # Aggregation queries (average, sum, patterns, trends, comparisons, unique counts)
            # Added: commit frequency, code churn, lines added
            elif any(kw in query_lower for kw in ["average", "mean", "median", "sum", "total lines", "pattern", "trend", "trending", "compare", "ratio", "percentage", "unique", "distinct", "nunique", "frequency", "churn", "lines added", "lines deleted", "code changes"]):
                logger.info(f"Detected aggregation query requiring full dataset, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

            # Filtered queries (who did X, what files with Y, etc.)
            # Note: "core developer" now handled separately above with singular/plural detection
            elif any(kw in query_lower for kw in ["documentation", "doc", "readme", "test", "bug", "feature", "fix", "focus on", "responsible for", "added or removed", "pull request", "pr "]):
                logger.info(f"Detected filtered query requiring full dataset, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

            # Top/most queries (top contributors, most lines, etc.)
            # Added: most active, which developer
            elif any(kw in query_lower for kw in ["top", "most", "highest", "largest", "biggest", "least", "smallest", "most active", "which developer"]):
                logger.info(f"Detected ranking query requiring full dataset, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

            # File queries
            elif any(kw in query_lower for kw in ["file", "files", "modified", "changed this file"]):
                logger.info(f"Detected file query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

            # Default: use LLM for any unclassified query to ensure correctness
            else:
                logger.info(f"Unclassified query, using LLM-powered pandas generation for safety")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

        else:  # issues
            # EXPANDED ISSUES HANDLING

            # Who raises/filed most queries (reporter ranking) - CHECK FIRST before comment queries
            if any(kw in query_lower for kw in ["who raise", "who file", "who opened", "who reported", "most active reporter", "most active issue reporter", "who are the most active issue reporters"]):
                logger.info(f"Detected reporter ranking query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "issues", limit=100)

            # Who commented queries (comment author analysis)
            elif any(kw in query_lower for kw in ["who comment", "who has commented"]):
                logger.info(f"Detected comment author query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "issues", limit=100)

            # Most commented (specific queries take priority over stats)
            elif any(kw in query_lower for kw in ["comment count", "most comment", "highest comment", "discussion"]):
                df, summary = self.query_issues(project_id, "most_commented", limit=5)

            # Stats (aggregation queries)
            # Handle "how many bugs", "feature requests", "versus", etc.
            elif (any(kw in query_lower for kw in ["stat", "statistics", "how many", "total", "versus", "vs", "ratio"]) and
                  "comment" not in query_lower and "raise" not in query_lower and "file" not in query_lower):
                df, summary = self.query_issues(project_id, "stats")

            # Temporal queries (created this week, closed last month, etc.)
            elif any(kw in query_lower for kw in ["last month", "last week", "this week", "this month", "created", "closed last"]):
                logger.info(f"Detected temporal issues query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "issues", limit=100)

            # Closure/response time queries (need time calculations)
            elif any(kw in query_lower for kw in ["how quickly", "closure rate", "response time", "time to close"]):
                logger.info(f"Detected time-based analysis query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "issues", limit=100)

            # Filtered queries (label, priority, stale, need attention)
            elif any(kw in query_lower for kw in ["label", "priority", "high-priority", "stale", "need attention", "need help", "oldest"]):
                logger.info(f"Detected filtered issues query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "issues", limit=100)

            # Assigned queries
            elif any(kw in query_lower for kw in ["assigned", "assignee", "who assigned"]):
                logger.info(f"Detected assignee query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "issues", limit=100)

            # Recently updated
            elif any(kw in query_lower for kw in ["updated", "recently updated", "most recent"]):
                # Detect singular vs plural for issues
                is_singular = any(phrase in query_lower for phrase in [
                    "latest issue ", "latest issue?", "latest issue.",
                    "recent issue ", "recent issue?", "recent issue.",
                    "newest issue ", "newest issue?", "newest issue.",
                    "show me the issue", "what is the issue", "what's the issue"
                ])
                limit = 1 if is_singular else 5
                df, summary = self.query_issues(project_id, "latest", limit=limit)

            # Open issues
            elif "open" in query_lower and "closed" not in query_lower and "vs" not in query_lower and "versus" not in query_lower:
                is_singular = any(phrase in query_lower for phrase in [
                    "open issue ", "open issue?", "open issue.",
                    "show me the open issue", "what is the open issue"
                ])
                limit = 1 if is_singular else 5
                df, summary = self.query_issues(project_id, "open", limit=limit)

            # Closed issues
            elif "closed" in query_lower and "open" not in query_lower and "vs" not in query_lower and "versus" not in query_lower:
                is_singular = any(phrase in query_lower for phrase in [
                    "closed issue ", "closed issue?", "closed issue.",
                    "show me the closed issue", "what is the closed issue"
                ])
                limit = 1 if is_singular else 5
                df, summary = self.query_issues(project_id, "closed", limit=limit)

            # Default fallback
            else:
                logger.info(f"Unclassified issues query, using latest issues")
                is_singular = any(phrase in query_lower for phrase in [
                    "latest issue ", "latest issue?", "latest issue.",
                    "show me the issue", "what is the issue"
                ])
                limit = 1 if is_singular else 5
                df, summary = self.query_issues(project_id, "latest", limit=limit)

        # Format as context for LLM
        if df.empty:
            return summary, []

        # Convert DataFrame to readable text
        # For LLM-generated queries, include more rows (up to 50)
        # For predefined queries, limit to 20
        max_rows = 50 if len(df) > 20 else len(df)
        context = f"{summary}\n\n"
        context += df.to_string(index=False, max_rows=max_rows)

        # Also return as records for citations (limit to reasonable size)
        records = df.head(max_rows).to_dict('records')

        return context, records

    def get_available_data(self, project_id: str) -> Dict[str, bool]:
        """Check what data is available for a project"""
        if project_id not in self.data_cache:
            return {"commits": False, "issues": False}

        return {
            "commits": "commits" in self.data_cache[project_id],
            "issues": "issues" in self.data_cache[project_id]
        }

    def has_project_data(self, project_id: str) -> bool:
        """
        Check if project has commits or issues data loaded in cache

        Args:
            project_id: Project identifier to check

        Returns:
            True if project has any data (commits or issues), False otherwise
        """
        if project_id not in self.data_cache:
            return False

        project_data = self.data_cache[project_id]
        has_commits = "commits" in project_data and not project_data["commits"].empty
        has_issues = "issues" in project_data and not project_data["issues"].empty

        return has_commits or has_issues

    def get_stats(self) -> Dict:
        """Get overall statistics"""
        stats = {
            "projects_loaded": len(self.data_cache),
            "projects": {}
        }

        for project_id, data in self.data_cache.items():
            # Count commits
            commits_count = len(data.get("commits", []))

            # Count issues (filter for type='issue' if column exists)
            issues_count = 0
            if "issues" in data and not data["issues"].empty:
                issues_df = data["issues"]
                if "type" in issues_df.columns:
                    issues_count = len(issues_df[issues_df["type"] == "issue"])
                else:
                    issues_count = len(issues_df)

            stats["projects"][project_id] = {
                "commits": commits_count,
                "issues": issues_count
            }

        return stats
