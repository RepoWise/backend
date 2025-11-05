"""
Agent 3: Sustainability Forecaster

Handles:
- Sustainability predictions and forecasts
- Project health trajectories
- Risk assessment and decline indicators
- Time-series analysis of project metrics

NOTE: Currently provides analysis without full Pex integration.
      Full LSTM model integration requires:
      - Model weights from OSSPREY-Pex-Forecaster
      - Network feature data (socio-technical metrics)
      - Monthly time-series data
"""
import time
from typing import Dict, List, Optional
from loguru import logger

from app.agents.base_agent import BaseAgent, AgentState
from app.models.llm_client import LLMClient


class ForecasterAgent(BaseAgent):
    """
    Agent 3: Sustainability forecasting and trajectory analysis

    Provides insights about project sustainability trends, predictions,
    and risk factors based on forecasting models.
    """

    FORECASTER_PROMPT_TEMPLATE = """You are an expert in OSS project sustainability forecasting and health assessment.

CRITICAL INSTRUCTIONS:
1. Provide analysis based on sustainability forecasting principles
2. Explain what factors indicate project health or decline
3. Discuss trajectory patterns (growing, stable, declining, at-risk)
4. Be honest about prediction limitations without real-time data
5. Reference the 14 socio-technical network features used in forecasting:
   - Developer engagement metrics (num_dev, dev_per_file, etc.)
   - Network structure metrics (clustering coefficient, density, overlap)
   - Collaboration patterns (graph density, network overlap)

FORECASTING CONTEXT:
The OSSPREY Pex forecasting system uses bidirectional LSTM models trained on 14 network features
to predict project sustainability trajectories. Key indicators include:

- **Developer Engagement**: Number of active developers, developer-per-file ratios
- **Network Health**: Clustering coefficient, graph density, network overlap
- **Collaboration Quality**: Developer network connectivity, file ownership patterns
- **Temporal Patterns**: Month-over-month trends in engagement and structure

User Question: {query}

Please provide insights about sustainability forecasting, trajectory analysis, or risk assessment.
Explain what metrics matter and what patterns indicate health vs. decline."""

    def __init__(self):
        super().__init__(name="Agent 3: Forecaster")
        self.llm_client = LLMClient()
        logger.info(f"[{self.name}] Initialized (Pex integration pending)")

    async def handle_query(self, state: AgentState) -> AgentState:
        """
        Handle forecasting/sustainability queries

        Args:
            state: Agent state with query

        Returns:
            Updated state with forecasting analysis
        """
        start_time = time.time()

        logger.info(
            f"[{self.name}] Handling forecasting query: '{state.query[:50]}...'"
        )

        try:
            # Build forecasting prompt
            prompt = self.FORECASTER_PROMPT_TEMPLATE.format(query=state.query)

            # Generate response
            generation_start = time.time()
            response_text = await self._generate_forecast_analysis(prompt)
            generation_time_ms = (time.time() - generation_start) * 1000

            # Add context about forecasting features
            sources = self._get_forecasting_sources()

            total_latency_ms = (time.time() - start_time) * 1000

            # Update state
            state.response = response_text
            state.sources = sources
            state.metadata = self._create_metadata(
                forecasting_mode="analysis",
                pex_integrated=False,
                generation_time_ms=generation_time_ms,
                total_latency_ms=total_latency_ms,
            )

            logger.success(
                f"[{self.name}] Response generated ({total_latency_ms:.2f}ms)"
            )

            return state

        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            state.error = str(e)
            state.response = (
                "I encountered an error analyzing sustainability forecasts. "
                "Please try rephrasing your question."
            )
            return state

    def _get_forecasting_sources(self) -> List[Dict]:
        """
        Get metadata about forecasting features and methodology

        Returns:
            List of source dictionaries describing forecasting system
        """
        return [
            {
                "type": "forecasting_feature",
                "category": "Developer Engagement",
                "features": [
                    "st_num_dev (socio-technical developer count)",
                    "t_num_dev_nodes (technical developer nodes)",
                    "t_num_dev_per_file (developers per file ratio)"
                ],
                "description": "Measures active developer participation"
            },
            {
                "type": "forecasting_feature",
                "category": "Network Structure",
                "features": [
                    "s_avg_clustering_coef (social clustering coefficient)",
                    "t_graph_density (technical graph density)",
                    "s_weighted_mean_degree (social degree centrality)"
                ],
                "description": "Measures collaboration network health"
            },
            {
                "type": "forecasting_feature",
                "category": "Collaboration Patterns",
                "features": [
                    "t_net_overlap (technical network overlap)",
                    "s_net_overlap (social network overlap)",
                    "s_num_nodes (social network size)"
                ],
                "description": "Measures cross-functional collaboration"
            },
            {
                "type": "forecasting_model",
                "model": "Bidirectional LSTM",
                "features_count": 14,
                "description": "Time-series forecasting using socio-technical network features"
            }
        ]

    async def _generate_forecast_analysis(
        self, prompt: str, temperature: float = 0.5
    ) -> str:
        """Generate forecasting analysis response"""
        try:
            import httpx

            payload = {
                "model": self.llm_client.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,  # Moderate temp for analysis
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
            logger.error(f"Error generating forecast analysis: {e}")
            return "I apologize, but I couldn't generate a forecast analysis. Please try again."


# Future: Full Pex Integration Class
class PexForecasterService:
    """
    Service wrapper for OSSPREY Pex forecasting system

    Will integrate:
    - LSTM model loading (from model-weights/)
    - Network feature extraction
    - Time-series prediction
    - Trajectory classification

    NOTE: Requires Pex forecaster dependencies and data
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_loaded = False
        # TODO: Load LSTM model from path
        # TODO: Initialize network feature extractors

    def predict_trajectory(self, project_data: Dict) -> Dict:
        """
        Predict sustainability trajectory for a project

        Args:
            project_data: Network features and time-series data

        Returns:
            Prediction results with confidence scores
        """
        # TODO: Implement full Pex forecasting
        return {
            "trajectory": "stable",
            "confidence": 0.0,
            "risk_level": "unknown",
            "message": "Full Pex integration pending"
        }
