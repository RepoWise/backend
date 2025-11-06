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

    def __init__(self, csv_data_dir: str = "data/csv_data", llm_client=None):
        """Initialize CSV data engine"""
        self.csv_data_dir = Path(csv_data_dir)
        self.csv_data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache: {project_id: {"commits": df, "issues": df}}
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}

        # LLM client for dynamic query generation
        self.llm_client = llm_client

        logger.info(f"CSV Data Engine initialized: {self.csv_data_dir}")

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
        """
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
        # Add data-type-specific column hints
        if data_type == "commits":
            common_cols_hint = "Common columns: commit_sha, name, email, date, message, filename, lines_added, lines_deleted"
        else:  # issues
            common_cols_hint = "Common columns: issue_num, title, issue_state (open/closed), user_login, created_at, updated_at, comment_count"

        prompt = f"""You are a pandas expert analyzing OSS project data. Generate ONLY the pandas code to answer this query.

Query: {query}
Data type: {data_type}

DataFrame name: df
DataFrame schema:
- Columns: {', '.join(schema_info['columns'])}
- Row count: {schema_info['row_count']}
- Data types: {schema_info['dtypes']}
{common_cols_hint}

CRITICAL RULES:
1. Return ONLY executable pandas code, NO explanations or markdown
2. The code must assign the final result to a variable called 'result'
3. Use .head({limit}) to limit results appropriately
4. For aggregations, use groupby() and agg() methods
5. Always reset_index() after groupby if needed
6. DO NOT use exec(), eval(), or any dangerous operations
7. DO NOT import anything - pandas is already imported as pd
8. Handle NaN/missing values gracefully with dropna() or fillna()
9. For string filtering, use .str.contains() with case=False, na=False
10. For time-based queries, ensure datetime columns are parsed

EXAMPLES BY QUERY TYPE:

# Category A: Ranking (top/most/highest)
"Who are the top 5 contributors by commit count?"
result = df.groupby(['name', 'email']).size().sort_values(ascending=False).head({limit}).reset_index(name='commit_count')

"Which files have the most lines added?"
result = df.groupby('filename')['lines_added'].sum().sort_values(ascending=False).head({limit}).reset_index()

# Category B: Filtered Aggregation (content-based filtering)
"Who contributed to documentation?"
result = df[df['message'].str.contains('doc|documentation|readme', case=False, na=False)].groupby('name').size().sort_values(ascending=False).head({limit}).reset_index(name='doc_commits')

"How many bug fix commits per contributor?"
result = df[df['message'].str.contains('fix|bug', case=False, na=False)].groupby('name').size().sort_values(ascending=False).head({limit}).reset_index(name='bug_fixes')

# Category C: Statistical Analysis (averages, medians, ratios)
"What is the average commit size?"
result = df[['lines_added', 'lines_deleted']].sum().to_frame(name='total').T
result['avg_commit_size'] = (result['total'].sum()) / len(df)
result = result[['avg_commit_size']]

"What is the ratio of lines added to deleted?"
total_added = df['lines_added'].sum()
total_deleted = df['lines_deleted'].sum()
result = pd.DataFrame({{'lines_added': [total_added], 'lines_deleted': [total_deleted], 'ratio': [total_added / total_deleted if total_deleted > 0 else 0]}})

# Category D: Temporal Analysis (time-based grouping)
"Commits per month in last year?"
result = df[df['date'] >= pd.Timestamp.now() - pd.DateOffset(months=12)].groupby(df['date'].dt.to_period('M')).size().reset_index(name='commits')

"Which day of week has most commits?"
result = df.groupby(df['date'].dt.day_name()).size().sort_values(ascending=False).reset_index(name='commits')

# Category E: Pattern Detection (file co-modification, outliers)
"Which commit modified the most files?"
result = df.groupby('commit_sha').agg({{'filename': 'count', 'name': 'first', 'message': 'first'}}).sort_values('filename', ascending=False).head({limit}).reset_index()

"Most frequently modified files?"
result = df.groupby('filename').size().sort_values(ascending=False).head({limit}).reset_index(name='modification_count')

# Category F: Issues-specific
"Issues with highest comment count?"
result = df.nlargest({limit}, 'comment_count')[['issue_num', 'title', 'comment_count', 'issue_state', 'user_login']]

"Average time to close issues?"
closed_issues = df[df['issue_state'] == 'closed'].copy()
closed_issues['time_to_close'] = (pd.to_datetime(closed_issues['updated_at']) - pd.to_datetime(closed_issues['created_at'])).dt.days
result = pd.DataFrame({{'avg_days_to_close': [closed_issues['time_to_close'].mean()]}})

Now generate pandas code for the query "{query}". Return ONLY the code, nothing else:"""

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

            # Safety check: validate the code
            if not self._is_safe_pandas_code(generated_code):
                logger.error("Generated code failed safety check")
                return pd.DataFrame(), "Generated query code failed safety validation"

            # Execute the generated code
            local_vars = {'df': df, 'pd': pd, 'result': None}
            exec(generated_code, {"__builtins__": {}}, local_vars)

            result = local_vars.get('result')

            if result is None or not isinstance(result, pd.DataFrame):
                logger.error(f"Execution did not produce a DataFrame: {type(result)}")
                return pd.DataFrame(), "Query execution failed to produce results"

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
                ['commit_sha', 'name', 'email', 'date']
            ]
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
            contributors = df.groupby(['name', 'email']).agg({
                'commit_sha': 'count',
                'lines_added': 'sum',
                'lines_deleted': 'sum'
            }).rename(columns={'commit_sha': 'commit_count'})

            contributors['total_changes'] = contributors['lines_added'] + contributors['lines_deleted']
            result = contributors.nlargest(limit, 'commit_count').reset_index()
            summary = f"Top {len(result)} contributors by commit count"

        elif query_type == "stats":
            # Overall statistics
            total_commits = len(df)
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
            ]
            summary = f"Latest {len(result)} issues"

        elif query_type == "open":
            # Use case-insensitive comparison (CSV has lowercase "open")
            open_issues = issues_df[issues_df['issue_state'].str.lower() == 'open']
            result = open_issues.nlargest(limit, 'created_at')[
                ['issue_num', 'title', 'user_login', 'created_at']
            ]
            summary = f"Open issues: {len(result)} shown (total: {len(open_issues)})"

        elif query_type == "closed":
            # Use case-insensitive comparison (CSV has lowercase "closed")
            closed_issues = issues_df[issues_df['issue_state'].str.lower() == 'closed']
            result = closed_issues.nlargest(limit, 'updated_at')[
                ['issue_num', 'title', 'user_login', 'created_at', 'updated_at']
            ]
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
            ]
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
            # Latest commits
            if any(kw in query_lower for kw in ["latest", "recent", "newest", "last"]) and not any(kw in query_lower for kw in ["average", "trend", "pattern", "all", "every"]):
                df, summary = self.query_commits(project_id, "latest", limit=10)
            # Basic stats (uses predefined aggregation)
            elif query_lower in ["stats", "statistics", "summary"] or (any(kw in query_lower for kw in ["how many total", "total commits", "total authors"]) and "average" not in query_lower):
                df, summary = self.query_commits(project_id, "stats")

            # COMPLEX QUERIES - These need full dataset access via LLM pandas generation
            # Aggregation queries (average, sum, patterns, trends, comparisons)
            elif any(kw in query_lower for kw in ["average", "mean", "median", "sum", "total lines", "pattern", "trend", "trending", "compare", "ratio", "percentage"]):
                logger.info(f"Detected aggregation query requiring full dataset, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)
            # Filtered queries (who did X, what files with Y, etc.)
            elif any(kw in query_lower for kw in ["documentation", "doc", "readme", "test", "bug", "feature", "fix", "focus on", "responsible for", "added or removed"]):
                logger.info(f"Detected filtered query requiring full dataset, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)
            # Top/most queries (top contributors, most lines, etc.)
            elif any(kw in query_lower for kw in ["top", "most", "highest", "largest", "biggest", "least", "smallest"]):
                logger.info(f"Detected ranking query requiring full dataset, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)
            # File queries
            elif any(kw in query_lower for kw in ["file", "files", "modified"]):
                logger.info(f"Detected file query, using LLM-powered pandas generation")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)
            # Default: use LLM for any unclassified query to ensure correctness
            else:
                logger.info(f"Unclassified query, using LLM-powered pandas generation for safety")
                df, summary = self.query_with_llm(project_id, query, "commits", limit=100)

        else:  # issues
            # Most commented (CHECK FIRST - specific queries take priority over stats)
            if any(kw in query_lower for kw in ["comment count", "most comment", "highest comment", "discussion"]):
                df, summary = self.query_issues(project_id, "most_commented", limit=5)
            # Stats (aggregation queries)
            elif any(kw in query_lower for kw in ["stat", "statistics", "how many", "total", "versus", "vs", "who opened"]) and "comment" not in query_lower:
                df, summary = self.query_issues(project_id, "stats")
            # Recently updated
            elif any(kw in query_lower for kw in ["updated", "recently updated", "most recent"]):
                df, summary = self.query_issues(project_id, "latest", limit=5)
            # Open issues
            elif "open" in query_lower and "closed" not in query_lower:
                df, summary = self.query_issues(project_id, "open", limit=5)
            # Closed issues
            elif "closed" in query_lower and "open" not in query_lower:
                df, summary = self.query_issues(project_id, "closed", limit=5)
            else:
                df, summary = self.query_issues(project_id, "latest", limit=5)

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
