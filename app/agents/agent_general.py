"""
Agent 0: General LLM for Conversational Queries

Handles:
- Greetings (Hello, Hi, Hey)
- Help requests (What can you do?)
- General conversation
- No document retrieval needed
"""
import time
from typing import Dict, List
from loguru import logger

from app.agents.base_agent import BaseAgent, AgentState
from app.models.llm_client import LLMClient


class GeneralLLMAgent(BaseAgent):
    """
    Agent 0: Conversational queries without retrieval

    Solves the "Hello" problem - responds naturally to greetings
    without citing governance documents inappropriately
    """

    SYSTEM_PROMPT = """You are OSSPREY Intelligence, an AI assistant specialized in open source software governance, sustainability, and collaboration analysis.

You help users with:
1. **Governance**: Understanding licenses, policies, contribution guidelines, codes of conduct
2. **Sustainability**: Analyzing project health, forecasting trends, identifying risks
3. **Collaboration**: Finding developers, understanding contribution patterns
4. **Recommendations**: Providing evidence-based best practices for OSS projects

When users greet you or ask what you can do:
- Respond conversationally and warmly
- Suggest relevant questions they might ask
- Be helpful without being overwhelming

When users ask for help:
- Explain the different types of questions you can answer
- Provide 2-3 example questions per category
- Keep it concise

IMPORTANT: You are currently in conversational mode. DO NOT retrieve or cite governance documents for greetings or general help requests."""

    def __init__(self):
        super().__init__(name="Agent 0: General LLM")
        self.llm_client = LLMClient()

    async def handle_query(self, state: AgentState) -> AgentState:
        """
        Handle conversational queries without retrieval

        Args:
            state: Agent state with query

        Returns:
            Updated state with conversational response
        """
        start_time = time.time()

        logger.info(
            f"[{self.name}] Handling conversational query: '{state.query[:50]}...'"
        )

        try:
            # Build conversational prompt
            prompt = self._build_conversational_prompt(
                state.query, state.conversation_history
            )

            # Generate response with moderate temperature for natural conversation
            response_text = await self._generate_response(prompt, temperature=0.7)

            latency_ms = (time.time() - start_time) * 1000

            # Update state
            state.response = response_text
            state.sources = []  # No sources for conversational responses
            state.metadata = self._create_metadata(
                retrieval_performed=False,
                latency_ms=latency_ms,
                mode="conversational",
            )

            logger.success(
                f"[{self.name}] Response generated ({latency_ms:.2f}ms)"
            )

            return state

        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            state.error = str(e)
            state.response = (
                "I apologize, but I encountered an error. Please try again."
            )
            return state

    def _build_conversational_prompt(
        self, query: str, conversation_history: List[Dict]
    ) -> str:
        """Build conversational prompt without governance context"""
        prompt = self.SYSTEM_PROMPT + "\n\n"

        # Add conversation history if available
        if conversation_history and len(conversation_history) > 0:
            prompt += "PREVIOUS CONVERSATION:\n"
            for msg in conversation_history[-3:]:  # Last 3 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            prompt += "\n"

        prompt += f"User: {query}\n\nAssistant:"

        return prompt

    async def _generate_response(
        self, prompt: str, temperature: float = 0.7
    ) -> str:
        """Generate conversational response"""
        try:
            # Use Ollama API directly for simple generation
            import httpx

            payload = {
                "model": self.llm_client.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 300,  # Shorter for conversational responses
                    "top_p": 0.9,
                    "top_k": 40,
                },
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.llm_client.api_endpoint}/generate", json=payload
                )
                response.raise_for_status()

                result = response.json()
                return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"Error generating conversational response: {e}")
            return "Hello! I'm OSSPREY Intelligence. I can help you understand OSS governance, sustainability, and collaboration. What would you like to know?"
