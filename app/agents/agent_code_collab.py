"""
Agent 2: Code Collaboration GraphRAG

Handles:
- Developer network queries (who worked with whom?)
- File ownership and contribution patterns
- Code collaboration analysis
- Developer-file relationships
- Network metrics and statistics

Uses CSV-based graph data WITHOUT Neo4j database.
"""
import time
from typing import Dict, List, Optional
from loguru import logger

from app.agents.base_agent import BaseAgent, AgentState
from app.models.llm_client import LLMClient
from app.services.graph_loader import get_graph_loader, GraphDataLoader


class CodeCollabGraphAgent(BaseAgent):
    """
    Agent 2: Code collaboration and developer network analysis

    Provides insights about:
    - Developer contributions and expertise
    - Collaboration patterns
    - File ownership
    - Code coupling through shared developers
    """

    GRAPH_PROMPT_TEMPLATE = """You are an expert in analyzing developer collaboration networks and code ownership patterns in OSS projects.

CRITICAL INSTRUCTIONS:
1. Answer based ONLY on the graph data provided below
2. Cite specific developers, files, and commit numbers from the data
3. Explain collaboration patterns (who worked together, on what files)
4. Identify key contributors and ownership patterns
5. NEVER make up developers, files, or statistics
6. If the query asks about data not in the graph, say so clearly

GRAPH QUERY RESULTS:
{graph_context}

User Question: {query}

Please provide insights based on the graph data above. Include specific names, files, and numbers."""

    def __init__(self, graph_loader: Optional[GraphDataLoader] = None):
        super().__init__(name="Agent 2: Code Collaboration GraphRAG")
        self.llm_client = LLMClient()

        # Store provided loader (for testing) but prefer project-specific loaders
        self.default_graph_loader = graph_loader

        logger.info(f"[{self.name}] Initialized (will use project-specific graphs)")

    async def handle_query(self, state: AgentState) -> AgentState:
        """
        Handle code collaboration / developer network queries

        Args:
            state: Agent state with query

        Returns:
            Updated state with graph analysis
        """
        start_time = time.time()

        logger.info(
            f"[{self.name}] Handling graph query: '{state.query[:50]}...'"
        )

        try:
            # Get project-specific graph loader
            graph_loader = self._get_graph_loader(state.project_id)

            # Check if graph data is available
            if not graph_loader or not hasattr(graph_loader, 'df') or graph_loader.df is None or len(graph_loader.df) == 0:
                state.response = (
                    "No developer collaboration data available for this project yet. "
                    "The project needs to be scraped first to build the collaboration graph."
                )
                state.sources = []
                state.metadata = self._create_metadata(
                    query_type="no_data",
                    query_time_ms=0,
                    generation_time_ms=0,
                    total_latency_ms=0
                )
                return state

            # Step 1: Classify query type and execute graph queries
            query_start = time.time()
            graph_results, query_type = self._execute_graph_queries(state.query, graph_loader)
            query_time_ms = (time.time() - query_start) * 1000

            if not graph_results:
                state.response = (
                    "I couldn't find relevant information in the developer collaboration graph. "
                    "Try asking about:\\n"
                    "- Developer contributions (e.g., 'What did Edward Yoon work on?')\\n"
                    "- File ownership (e.g., 'Who worked on Matrix.java?')\\n"
                    "- Collaboration patterns (e.g., 'Who collaborated with Edward?')\\n"
                    "- Network statistics (e.g., 'Show network overview')"
                )
                state.sources = []
                return state

            logger.info(f"[{self.name}] Found {len(graph_results)} graph results ({query_type})")

            # Step 2: Format graph context for LLM
            graph_context = self._format_graph_context(graph_results, query_type)

            # Step 3: Build prompt with graph data
            prompt = self.GRAPH_PROMPT_TEMPLATE.format(
                graph_context=graph_context,
                query=state.query
            )

            # Step 4: Generate analysis
            generation_start = time.time()
            response_text = await self._generate_graph_analysis(prompt)
            generation_time_ms = (time.time() - generation_start) * 1000

            # Step 5: Format sources from graph results
            sources = self._extract_graph_sources(graph_results, query_type)

            total_latency_ms = (time.time() - start_time) * 1000

            # Update state
            state.response = response_text
            state.sources = sources
            state.metadata = self._create_metadata(
                query_type=query_type,
                results_count=len(graph_results),
                graph_query_time_ms=query_time_ms,
                generation_time_ms=generation_time_ms,
                total_latency_ms=total_latency_ms,
            )

            logger.success(
                f"[{self.name}] Response generated with {len(sources)} sources ({total_latency_ms:.2f}ms)"
            )

            return state

        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            state.error = str(e)
            state.response = (
                "I encountered an error analyzing the collaboration graph. "
                "Please try rephrasing your question."
            )
            return state

    def _get_graph_loader(self, project_id: Optional[str]) -> Optional[GraphDataLoader]:
        """
        Get project-specific graph loader

        Args:
            project_id: Project identifier

        Returns:
            GraphDataLoader instance or None
        """
        # If default loader provided (for testing), use it
        if self.default_graph_loader:
            return self.default_graph_loader

        # Otherwise get project-specific loader
        if project_id:
            return get_graph_loader(project_id)

        # Fallback to demo loader
        return get_graph_loader()

    def _execute_graph_queries(self, query: str, graph_loader: GraphDataLoader) -> tuple[List[Dict], str]:
        """
        Execute graph queries based on query intent

        Returns:
            (results, query_type)
        """
        query_lower = query.lower()

        # Developer → Files query
        if any(word in query_lower for word in ["what did", "files", "worked on", "contributed"]):
            # Extract developer name (simple heuristic)
            for word in query.split():
                if word[0].isupper() and len(word) > 2:
                    results = graph_loader.query_developer_files(word, limit=15)
                    if results:
                        return results, "developer_files"

        # File → Developers query
        if any(word in query_lower for word in ["who worked", "who modified", "who wrote"]):
            # Extract file pattern
            for word in query.split():
                if "." in word or "/" in word:  # Likely a file name
                    results = graph_loader.query_file_developers(word, limit=15)
                    if results:
                        return results, "file_developers"

        # Collaboration query
        if any(word in query_lower for word in ["collaborated", "worked with", "team", "partners"]):
            for word in query.split():
                if word[0].isupper() and len(word) > 2:
                    results = graph_loader.query_developer_collaborators(word, limit=10)
                    if results:
                        return results, "collaborators"

        # Network overview query
        if any(word in query_lower for word in ["overview", "statistics", "stats", "summary", "network"]):
            stats = graph_loader.get_network_stats()
            if stats:
                return [stats], "network_stats"

        # Fallback: try developer query with broader search
        # Extract any capitalized word as potential developer name
        for word in query.split():
            if word[0].isupper() and len(word) > 2:
                results = graph_loader.query_developer_files(word, limit=10)
                if results:
                    return results, "developer_files"

        # If nothing found, return network stats as fallback
        stats = graph_loader.get_network_stats()
        if stats:
            return [stats], "network_stats"

        return [], "unknown"

    def _format_graph_context(self, results: List[Dict], query_type: str) -> str:
        """
        Format graph query results as context for LLM

        Args:
            results: Graph query results
            query_type: Type of query executed

        Returns:
            Formatted context string
        """
        if query_type == "developer_files":
            context_parts = ["Developer File Contributions:\\n"]
            for i, item in enumerate(results[:10], 1):
                context_parts.append(
                    f"{i}. {item['file']}\\n"
                    f"   - Commits: {item['commits']}\\n"
                    f"   - Lines added: {item['lines_added']}\\n"
                    f"   - Lines deleted: {item['lines_deleted']}\\n"
                )
            return "".join(context_parts)

        elif query_type == "file_developers":
            context_parts = ["File Contributors:\\n"]
            for i, item in enumerate(results[:10], 1):
                context_parts.append(
                    f"{i}. {item['developer']} ({item['email']})\\n"
                    f"   - Commits: {item['commits']}\\n"
                    f"   - Lines added: {item['lines_added']}\\n"
                    f"   - Lines deleted: {item['lines_deleted']}\\n"
                )
            return "".join(context_parts)

        elif query_type == "collaborators":
            context_parts = ["Developer Collaborators:\\n"]
            for i, item in enumerate(results[:10], 1):
                context_parts.append(
                    f"{i}. {item['developer']} ({item['email']})\\n"
                    f"   - Shared files: {item['shared_files']}\\n"
                    f"   - Total commits: {item['total_commits']}\\n"
                )
            return "".join(context_parts)

        elif query_type == "network_stats":
            stats = results[0]
            context_parts = [
                f"Developer Collaboration Network Statistics:\\n\\n",
                f"Overall Metrics:\\n",
                f"- Total commits: {stats['total_commits']}\\n",
                f"- Total developers: {stats['total_developers']}\\n",
                f"- Total files: {stats['total_files']}\\n\\n",
                f"Developer Network:\\n",
                f"- Nodes (developers): {stats['developer_network']['nodes']}\\n",
                f"- Edges (collaborations): {stats['developer_network']['edges']}\\n",
                f"- Network density: {stats['developer_network']['density']:.4f}\\n",
                f"- Connected components: {stats['developer_network']['components']}\\n\\n",
                f"Top Contributors:\\n"
            ]

            for i, dev in enumerate(stats['top_developers'], 1):
                context_parts.append(f"{i}. {dev['developer']} - {dev['commits']} commits\\n")

            context_parts.append("\\nMost Edited Files:\\n")
            for i, file in enumerate(stats['top_files'], 1):
                context_parts.append(f"{i}. {file['file']} - {file['developers']} developers\\n")

            return "".join(context_parts)

        return "No graph data available."

    def _extract_graph_sources(self, results: List[Dict], query_type: str) -> List[Dict]:
        """
        Extract sources from graph results

        Args:
            results: Graph query results
            query_type: Type of query

        Returns:
            List of source dictionaries
        """
        sources = []

        if query_type == "developer_files":
            for item in results[:5]:
                sources.append({
                    "type": "file_contribution",
                    "file": item["file"],
                    "commits": item["commits"],
                    "changes": item["total_changes"]
                })

        elif query_type == "file_developers":
            for item in results[:5]:
                sources.append({
                    "type": "developer_contribution",
                    "developer": item["developer"],
                    "email": item["email"],
                    "commits": item["commits"],
                    "changes": item["total_changes"]
                })

        elif query_type == "collaborators":
            for item in results[:5]:
                sources.append({
                    "type": "collaboration",
                    "developer": item["developer"],
                    "email": item["email"],
                    "shared_files": item["shared_files"]
                })

        elif query_type == "network_stats":
            stats = results[0]
            sources.append({
                "type": "network_statistics",
                "total_commits": stats["total_commits"],
                "total_developers": stats["total_developers"],
                "network_density": stats["developer_network"]["density"]
            })

        return sources

    async def _generate_graph_analysis(
        self, prompt: str, temperature: float = 0.4
    ) -> str:
        """Generate graph analysis response"""
        try:
            import httpx

            payload = {
                "model": self.llm_client.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 800,
                    "top_p": 0.9,
                    "top_k": 40,
                },
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client.api_endpoint}/generate", json=payload
                )
                response.raise_for_status()

                result = response.json()
                return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"Error generating graph analysis: {e}")
            return "I apologize, but I couldn't generate a graph analysis. Please try again."
