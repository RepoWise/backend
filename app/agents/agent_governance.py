"""
Agent 1: Governance RAG with Vector Search

Handles:
- License questions
- Policy inquiries
- Contribution guidelines
- Code of Conduct
- Security policies
- Governance structure

ENHANCED: NLI-based grounding verification to prevent hallucinations
"""
import time
from typing import Dict, List
from loguru import logger

from app.agents.base_agent import BaseAgent, AgentState
from app.models.llm_client import LLMClient
from app.rag.rag_engine import RAGEngine
from app.rag.nli_verifier import get_nli_verifier


class GovernanceRAGAgent(BaseAgent):
    """
    Agent 1: Governance document queries with RAG

    Uses vector similarity search to retrieve relevant governance documents
    and generates grounded responses with source attribution
    """

    GROUNDING_PROMPT_TEMPLATE = """You are an expert in open source software governance for the {project_name} project.

CRITICAL INSTRUCTIONS:
1. Answer ONLY based on the provided governance documents below
2. If the answer is not in the documents, say "I don't have information about that in the governance documents"
3. NEVER make up file names, URLs, or policies
4. Quote exact text when citing governance rules
5. Cite which document type your answer comes from (e.g., CONTRIBUTING.md, CODE_OF_CONDUCT.md)
6. Be specific and actionable

GOVERNANCE DOCUMENTS:
{context}

{conversation_context}

User Question: {query}

Please provide a clear, accurate answer based ONLY on the governance documents above. Cite your sources."""

    def __init__(self, rag_engine=None, enable_nli=True):
        super().__init__(name="Agent 1: Governance RAG")
        self.llm_client = LLMClient()
        # Use shared RAG engine instance if provided, otherwise create new one
        self.rag_engine = rag_engine if rag_engine is not None else RAGEngine()
        # Initialize NLI verifier for hallucination prevention
        self.nli_verifier = get_nli_verifier(enable=enable_nli)

    async def handle_query(self, state: AgentState) -> AgentState:
        """
        Handle governance queries with RAG retrieval

        Args:
            state: Agent state with query and project_id

        Returns:
            Updated state with grounded response and sources
        """
        start_time = time.time()

        if not state.project_id:
            state.error = "Project ID required for governance queries"
            state.response = (
                "Please specify a project to query governance documents."
            )
            return state

        logger.info(
            f"[{self.name}] Handling governance query for {state.project_id}: '{state.query[:50]}...'"
        )

        try:
            # Step 1: Retrieve relevant context from vector database
            retrieval_start = time.time()
            context, sources = self.rag_engine.get_context_for_query(
                state.query, state.project_id, max_chunks=5
            )
            retrieval_time_ms = (time.time() - retrieval_start) * 1000

            if not context:
                state.response = (
                    "No relevant governance documents found for this project. "
                    "Please make sure the project has been crawled first using the /crawl endpoint."
                )
                state.sources = []
                state.metadata = self._create_metadata(
                    retrieval_performed=True,
                    documents_found=0,
                    retrieval_time_ms=retrieval_time_ms,
                )
                return state

            logger.info(
                f"[{self.name}] Retrieved {len(sources)} relevant chunks ({retrieval_time_ms:.2f}ms)"
            )

            # Step 2: Build grounded prompt with strict instructions
            prompt = self._build_grounded_prompt(
                query=state.query,
                context=context,
                project_id=state.project_id,
                conversation_history=state.conversation_history,
            )

            # Step 3: Generate grounded response with source attribution
            generation_start = time.time()
            response_text = await self._generate_grounded_response(
                prompt, temperature=0.3
            )
            generation_time_ms = (time.time() - generation_start) * 1000

            # Step 4: NLI-based grounding verification (hallucination prevention)
            verification_start = time.time()
            # Extract just the text content from sources for verification
            context_texts = [src.get("text", "") for src in sources if src.get("text")]
            verification_result = self.nli_verifier.verify_response(
                response_text, context_texts
            )
            verification_time_ms = (time.time() - verification_start) * 1000

            total_latency_ms = (time.time() - start_time) * 1000

            # Log verification results
            if verification_result["enabled"]:
                if verification_result["grounded"]:
                    logger.success(
                        f"[{self.name}] NLI verification PASSED "
                        f"(confidence={verification_result['confidence']:.2f}, {verification_time_ms:.2f}ms)"
                    )
                else:
                    logger.warning(
                        f"[{self.name}] NLI verification FAILED "
                        f"(confidence={verification_result['confidence']:.2f}, "
                        f"{len(verification_result['flagged_sentences'])} sentences flagged)"
                    )

            # Update state
            state.response = response_text
            state.sources = sources
            state.metadata = self._create_metadata(
                retrieval_performed=True,
                documents_found=len(sources),
                retrieval_time_ms=retrieval_time_ms,
                generation_time_ms=generation_time_ms,
                verification_time_ms=verification_time_ms,
                total_latency_ms=total_latency_ms,
                context_length=len(context),
                grounding_verified=verification_result["grounded"],
                nli_confidence=verification_result["confidence"],
                nli_enabled=verification_result["enabled"],
                flagged_sentences=len(verification_result.get("flagged_sentences", [])),
                contradiction_found=verification_result.get("contradiction_found", False),
            )

            logger.success(
                f"[{self.name}] Response generated with {len(sources)} sources ({total_latency_ms:.2f}ms)"
            )

            return state

        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            state.error = str(e)
            state.response = (
                "I encountered an error retrieving governance information. "
                "Please ensure the project has been indexed and try again."
            )
            return state

    def _build_grounded_prompt(
        self,
        query: str,
        context: str,
        project_id: str,
        conversation_history: List[Dict],
    ) -> str:
        """Build prompt with strict grounding instructions"""
        # Get project name from ID (simple extraction)
        project_name = project_id.replace("-", " ").title()

        # Add conversation context if available
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            conversation_context = "PREVIOUS CONVERSATION:\n"
            for msg in conversation_history[-2:]:  # Last 2 exchanges
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    conversation_context += f"User: {content}\n"
                elif role == "assistant":
                    conversation_context += f"Assistant: {content}\n"
            conversation_context += "\n"

        prompt = self.GROUNDING_PROMPT_TEMPLATE.format(
            project_name=project_name,
            context=context,
            conversation_context=conversation_context,
            query=query,
        )

        return prompt

    async def _generate_grounded_response(
        self, prompt: str, temperature: float = 0.3
    ) -> str:
        """Generate response with low temperature for factual accuracy"""
        try:
            import httpx

            payload = {
                "model": self.llm_client.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,  # Low temp for factual responses
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
            logger.error(f"Error generating grounded response: {e}")
            return "I apologize, but I couldn't generate a response. Please try again."

