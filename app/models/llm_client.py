"""
LLM Client for Ollama integration with Llama 3.2
Handles prompt engineering and streaming responses
"""
from typing import Dict, List, Optional, AsyncIterator
from loguru import logger
import httpx
import json

from app.core.config import settings


class LLMClient:
    """
    Client for local LLM inference via Ollama

    Supports:
    - Synchronous and asynchronous generation
    - Streaming responses
    - Context-aware prompt engineering
    - Temperature and parameter control
    - Connection pooling for performance
    """

    # Shared connection pool for all instances
    _async_client: Optional[httpx.AsyncClient] = None
    _sync_client: Optional[httpx.Client] = None

    def __init__(self):
        """Initialize Ollama client with connection pooling"""
        self.host = settings.ollama_host
        self.model = settings.ollama_model
        self.api_endpoint = f"{self.host}/api"

        # Initialize shared clients if not already created
        if LLMClient._async_client is None:
            LLMClient._async_client = httpx.AsyncClient(
                timeout=120.0,
                limits=httpx.Limits(
                    max_connections=20,  # Connection pool size
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0
                )
            )
            logger.info("✅ Async connection pool initialized (20 connections)")

        if LLMClient._sync_client is None:
            LLMClient._sync_client = httpx.Client(
                timeout=120.0,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30.0
                )
            )
            logger.info("✅ Sync connection pool initialized (10 connections)")

        logger.info(f"LLM Client initialized - Model: {self.model}, Host: {self.host}")

    def _build_governance_prompt(
        self,
        query: str,
        context: str,
        project_name: str,
        include_sources: bool = True,
        conversation_history: Optional[List[Dict]] = None,
    ) -> str:
        """
        Build context-aware prompt for governance queries

        Args:
            query: User question
            context: Retrieved governance document context
            project_name: Name of the project
            include_sources: Whether to ask LLM to cite sources
            conversation_history: Previous conversation messages

        Returns:
            Formatted prompt string
        """
        system_prompt = f"""You are an expert assistant specialized in open source software governance.
You help users understand governance policies, contribution processes, and community guidelines for OSS projects.

You are currently answering questions about the {project_name} project.

Guidelines:
1. Answer based ONLY on the provided governance documents
2. If the answer is not in the documents, say "I don't have information about that in the governance documents"
3. Be specific and cite which document type your answer comes from (e.g., CONTRIBUTING.md, CODE_OF_CONDUCT.md)
4. Provide clear, actionable information
5. Use bullet points for multi-step processes
6. Be concise but complete
7. Use previous conversation context when relevant to understand follow-up questions

GOVERNANCE DOCUMENTS:
{context}

"""

        # Add conversation history if provided
        if conversation_history and len(conversation_history) > 0:
            system_prompt += "\nPREVIOUS CONVERSATION:\n"
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    system_prompt += f"User: {content}\n"
                elif role == "assistant":
                    system_prompt += f"Assistant: {content}\n"
            system_prompt += "\n"

        user_prompt = f"""Question: {query}

Please provide a clear answer based on the governance documents above."""

        if include_sources:
            user_prompt += (
                " Cite which governance document(s) you're referencing."
            )

        full_prompt = f"{system_prompt}\n{user_prompt}"

        return full_prompt

    async def generate_response(
        self,
        query: str,
        context: str,
        project_name: str = "the project",
        temperature: float = 0.3,
        max_tokens: int = 1000,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Generate response using Ollama API (async)

        Args:
            query: User query
            context: Retrieved context from RAG
            project_name: Project name for context
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens to generate
            conversation_history: Previous conversation messages

        Returns:
            Dict with response and metadata
        """
        prompt = self._build_governance_prompt(
            query, context, project_name, conversation_history=conversation_history
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40,
            },
        }

        try:
            # Use shared connection pool
            response = await self._async_client.post(
                f"{self.api_endpoint}/generate", json=payload
            )
            response.raise_for_status()

            result = response.json()

            return {
                "response": result.get("response", ""),
                "model": result.get("model", self.model),
                "context_length": result.get("context", 0),
                "total_duration_ms": result.get("total_duration", 0) / 1_000_000,
                "eval_count": result.get("eval_count", 0),
                "prompt_eval_count": result.get("prompt_eval_count", 0),
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Ollama API: {e}")
            return {
                "response": f"Error: Could not connect to LLM service. Make sure Ollama is running with: ollama serve",
                "error": str(e),
            }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {"response": f"Error generating response: {str(e)}", "error": str(e)}

    async def generate_response_stream(
        self,
        query: str,
        context: str,
        project_name: str = "the project",
        temperature: float = 0.3,
        max_tokens: int = 1000,
        conversation_history: Optional[List[Dict]] = None,
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from Ollama

        Args:
            query: User query
            context: Retrieved context from RAG
            project_name: Project name for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            conversation_history: Previous conversation messages

        Yields:
            Response chunks as they're generated
        """
        prompt = self._build_governance_prompt(
            query, context, project_name, conversation_history=conversation_history
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40,
            },
        }

        try:
            # Use shared connection pool for streaming
            async with self._async_client.stream(
                "POST", f"{self.api_endpoint}/generate", json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                yield chunk["response"]

                            # Check if done
                            if chunk.get("done", False):
                                break

                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse chunk: {line}")
                            continue

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in streaming: {e}")
            yield f"\n\n[Error: Could not connect to LLM service]"

        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"\n\n[Error: {str(e)}]"

    async def check_model_availability(self) -> Dict:
        """
        Check if the configured model is available in Ollama

        Returns:
            Dict with availability status and model info
        """
        try:
            # List available models using shared client
            response = await self._async_client.get(f"{self.api_endpoint}/tags")
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            is_available = any(
                self.model in name or name.startswith(self.model.split(":")[0])
                for name in model_names
            )

            return {
                "available": is_available,
                "configured_model": self.model,
                "available_models": model_names,
            }

        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            return {
                "available": False,
                "error": str(e),
                "message": "Could not connect to Ollama. Make sure it's running.",
            }

    def generate_simple(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 100,
    ) -> str:
        """
        Simple synchronous generation for short tasks like intent classification

        Args:
            prompt: The prompt to send to the LLM
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40,
            },
        }

        try:
            # Use shared sync client
            response = self._sync_client.post(f"{self.api_endpoint}/generate", json=payload)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"Error in simple generation: {e}")
            return ""

    def generate_response_sync(
        self,
        query: str,
        context: str,
        project_name: str = "the project",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> Dict:
        """
        Synchronous version of generate_response (for non-async contexts)

        Args:
            query: User query
            context: Retrieved context from RAG
            project_name: Project name for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Dict with response and metadata
        """
        prompt = self._build_governance_prompt(query, context, project_name)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40,
            },
        }

        try:
            # Use shared sync client
            response = self._sync_client.post(f"{self.api_endpoint}/generate", json=payload)
            response.raise_for_status()

            result = response.json()

            return {
                "response": result.get("response", ""),
                "model": result.get("model", self.model),
                "context_length": result.get("context", 0),
                "total_duration_ms": result.get("total_duration", 0) / 1_000_000,
                "eval_count": result.get("eval_count", 0),
                "prompt_eval_count": result.get("prompt_eval_count", 0),
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Ollama API: {e}")
            return {
                "response": f"Error: Could not connect to LLM service. Make sure Ollama is running with: ollama serve",
                "error": str(e),
            }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {"response": f"Error generating response: {str(e)}", "error": str(e)}
