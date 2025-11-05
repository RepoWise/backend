"""
Agent 4: Recommendations with ReACT Integration

Handles:
- Actionable recommendations for project sustainability
- Evidence-based suggestions from research literature
- Feature-based recommendation filtering
- ReACT (Research-based Actions) database integration

Data Source: 105 evidence-based recommendations from OSSPREY-ReACT-API
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from app.agents.base_agent import BaseAgent, AgentState
from app.models.llm_client import LLMClient


class RecommendationsAgent(BaseAgent):
    """
    Agent 4: Evidence-based recommendations using ReACT database

    Provides actionable recommendations for improving project sustainability
    based on 105 evidence-based ReACTs extracted from research literature.
    """

    RECOMMENDATION_PROMPT_TEMPLATE = """You are an expert OSS sustainability consultant providing evidence-based recommendations.

CRITICAL INSTRUCTIONS:
1. Provide actionable recommendations from the ReACT database below
2. Cite the specific ReACT-ID and reference papers for each recommendation
3. Explain WHY each recommendation helps (based on research evidence)
4. Prioritize recommendations by importance score
5. Be specific about WHO should implement (entity responsible)
6. NEVER make up recommendations - only use the ReACT data provided

AVAILABLE RECOMMENDATIONS:
{react_context}

User Question: {query}

Please provide 3-5 most relevant recommendations with:
- Clear action items
- Responsible entities
- Evidence from research papers
- Expected impact on sustainability

Format your response with clear sections and citations."""

    def __init__(self):
        super().__init__(name="Agent 4: Recommendations")
        self.llm_client = LLMClient()

        # Load ReACT recommendations database
        self.react_data = self._load_react_database()
        logger.info(f"[{self.name}] Loaded {len(self.react_data)} evidence-based recommendations")

    def _load_react_database(self) -> List[Dict]:
        """Load the ReACT recommendations from JSON file"""
        react_file = Path(__file__).parent.parent / "data" / "react_set.json"

        try:
            with open(react_file, 'r') as f:
                data = json.load(f)
            logger.success(f"Loaded ReACT database: {len(data)} recommendations")
            return data
        except Exception as e:
            logger.error(f"Failed to load ReACT database: {e}")
            return []

    async def handle_query(self, state: AgentState) -> AgentState:
        """
        Handle recommendation queries

        Args:
            state: Agent state with query

        Returns:
            Updated state with recommendations
        """
        start_time = time.time()

        logger.info(
            f"[{self.name}] Handling recommendation query: '{state.query[:50]}...'"
        )

        try:
            # Step 1: Search for relevant recommendations
            relevant_reacts = self._search_recommendations(state.query)

            if not relevant_reacts:
                state.response = (
                    "I couldn't find specific recommendations matching your query in our evidence-based database. "
                    "Could you rephrase your question or ask about:\n"
                    "- Developer engagement\n"
                    "- Community management\n"
                    "- Documentation practices\n"
                    "- Code quality improvements\n"
                    "- Project governance"
                )
                state.sources = []
                return state

            logger.info(f"[{self.name}] Found {len(relevant_reacts)} relevant recommendations")

            # Step 2: Format ReACT context for LLM
            react_context = self._format_react_context(relevant_reacts[:10])  # Top 10

            # Step 3: Build prompt with recommendations
            prompt = self.RECOMMENDATION_PROMPT_TEMPLATE.format(
                react_context=react_context,
                query=state.query
            )

            # Step 4: Generate recommendations response
            generation_start = time.time()
            response_text = await self._generate_recommendations(prompt)
            generation_time_ms = (time.time() - generation_start) * 1000

            # Step 5: Format sources (research papers)
            sources = self._extract_sources(relevant_reacts[:5])  # Top 5 for sources

            total_latency_ms = (time.time() - start_time) * 1000

            # Update state
            state.response = response_text
            state.sources = sources
            state.metadata = self._create_metadata(
                recommendations_found=len(relevant_reacts),
                recommendations_used=len(relevant_reacts[:10]),
                generation_time_ms=generation_time_ms,
                total_latency_ms=total_latency_ms,
            )

            logger.success(
                f"[{self.name}] Response generated with {len(sources)} research citations ({total_latency_ms:.2f}ms)"
            )

            return state

        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            state.error = str(e)
            state.response = (
                "I encountered an error retrieving recommendations. "
                "Please try rephrasing your question."
            )
            return state

    def _search_recommendations(self, query: str) -> List[Dict]:
        """
        Search for relevant recommendations based on query

        Simple keyword matching against:
        - ReACT title
        - Entity responsible
        - Features

        Args:
            query: User query

        Returns:
            List of relevant ReACT recommendations sorted by importance
        """
        query_lower = query.lower()

        # Extract search keywords
        keywords = [
            "developer", "developers", "community", "documentation", "docs",
            "contributor", "contributors", "maintainer", "maintainers",
            "engagement", "quality", "code", "testing", "ci/cd",
            "governance", "leadership", "communication", "support",
            "onboarding", "newcomer", "newcomers", "friendly",
            "collaboration", "team", "overlap", "network"
        ]

        matched_reacts = []

        for react in self.react_data:
            score = 0

            # Match against title (high weight)
            title = react.get("ReACT_title", "").lower()
            if any(keyword in query_lower for keyword in keywords if keyword in title):
                score += 3

            # Match against entity responsible
            entity = react.get("Entity_responsible", "").lower()
            if any(keyword in query_lower for keyword in keywords if keyword in entity):
                score += 2

            # Match against features
            features = react.get("Features", "").lower()
            if "dev" in query_lower and "dev" in features:
                score += 1

            # Direct keyword match in title
            for keyword in keywords:
                if keyword in query_lower and keyword in title:
                    score += 2

            # Add to results if score > 0
            if score > 0:
                react_copy = react.copy()
                react_copy["_relevance_score"] = score
                matched_reacts.append(react_copy)

        # Sort by relevance score (descending), then importance (descending)
        matched_reacts.sort(
            key=lambda x: (x.get("_relevance_score", 0), x.get("Importance", 0)),
            reverse=True
        )

        return matched_reacts

    def _format_react_context(self, reacts: List[Dict]) -> str:
        """
        Format ReACT recommendations as context for LLM

        Args:
            reacts: List of ReACT dictionaries

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, react in enumerate(reacts, 1):
            react_id = react.get("ReACT-ID", f"ReACT-{i}")
            title = react.get("ReACT_title", "Unknown recommendation")
            entity = react.get("Entity_responsible", "Project team")
            importance = react.get("Importance", 0)

            # Get research papers
            articles = react.get("articles", [])
            paper_citations = []
            for article in articles[:2]:  # Max 2 papers per ReACT
                paper_title = article.get("title", "Unknown paper")
                doi = article.get("doi", "")
                paper_citations.append(f"  - {paper_title} ({doi})")

            react_text = f"""
[{react_id}] {title}
  Responsible: {entity}
  Importance: {importance}/5
  Evidence from research:
{chr(10).join(paper_citations) if paper_citations else "  - (No papers listed)"}
"""
            context_parts.append(react_text)

        return "\n".join(context_parts)

    def _extract_sources(self, reacts: List[Dict]) -> List[Dict]:
        """
        Extract research paper sources from ReACTs

        Args:
            reacts: List of ReACT dictionaries

        Returns:
            List of source dictionaries
        """
        sources = []
        seen_dois = set()

        for react in reacts:
            react_id = react.get("ReACT-ID", "")
            react_title = react.get("ReACT_title", "")
            articles = react.get("articles", [])

            for article in articles:
                doi = article.get("doi", "")
                if doi and doi not in seen_dois:
                    sources.append({
                        "type": "research_paper",
                        "title": article.get("title", "Unknown paper"),
                        "doi": doi,
                        "react_id": react_id,
                        "react_title": react_title
                    })
                    seen_dois.add(doi)

        return sources

    async def _generate_recommendations(
        self, prompt: str, temperature: float = 0.4
    ) -> str:
        """Generate recommendations response with moderate creativity"""
        try:
            import httpx

            payload = {
                "model": self.llm_client.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,  # Moderate temp for recommendations
                    "num_predict": 1000,
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
            logger.error(f"Error generating recommendations: {e}")
            return "I apologize, but I couldn't generate recommendations. Please try again."
