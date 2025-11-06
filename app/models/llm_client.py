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
        query_type: str = "general",
    ) -> str:
        """
        Build task-specific prompt with few-shot examples for governance queries

        Args:
            query: User question
            context: Retrieved governance document context
            project_name: Name of the project
            include_sources: Whether to ask LLM to cite sources
            conversation_history: Previous conversation messages
            query_type: Type of query (who, what, how, general)

        Returns:
            Formatted prompt string
        """
        # Task-specific instructions based on query type
        task_instructions = {
            "who": """
TASK: ENTITY EXTRACTION - Extract names, emails, GitHub usernames, and roles

CRITICAL INSTRUCTIONS:
1. Search the documents below for actual names, email addresses, and GitHub usernames
2. Look for these patterns:
   - Email format: "Name <email@domain>" or "M: Name <email>"
   - GitHub format: "@username" (e.g., @fchollet, @MarkDaoust)
   - CODEOWNERS format: "/path/ @username1 @username2"
   - Plain names: "Maintained by: John Doe"
3. ONLY extract names/usernames that actually appear in the documents
4. When you find GitHub usernames (starting with @), extract them as maintainers
5. If NO names/emails/usernames are found, you MUST respond: "No maintainer information found in the available documents"
6. IGNORE any format descriptions or template explanations
7. DO NOT invent or guess names - only extract what you can see

RESPONSE LENGTH: Provide a complete answer. List all entities found with their roles/context from the document.

EXAMPLE EXTRACTION:
Input: "/guides/ @fchollet @MarkDaoust @pcoet"
Output: "The maintainers for the /guides/ directory are @fchollet, @MarkDaoust, and @pcoet (GitHub usernames from CODEOWNERS)."
""",
            "how": """
TASK: PROCESS EXPLANATION - Explain step-by-step procedures

INSTRUCTIONS:
- Provide a comprehensive explanation of the process
- Break down into clear, numbered steps if the procedure has multiple stages
- Include any prerequisites, requirements, or important context
- Mention specific tools, commands, or guidelines referenced in the documents
- Add relevant details that help the user understand the complete process
- Cite which documents contain each piece of information

RESPONSE LENGTH: Match the complexity of the question. Simple processes can be 2-3 sentences, complex workflows need detailed step-by-step breakdowns.
""",
            "what": """
TASK: DEFINITION - Explain what something is

INSTRUCTIONS:
- Start with a clear, direct definition
- Provide comprehensive project-specific context from the documents
- Include relevant examples, use cases, or implementation details
- Explain the purpose, scope, or importance if mentioned in the documents
- Add any related information that provides complete understanding

RESPONSE LENGTH: Provide enough detail for full understanding. Include all relevant context from the documents.
""",
            "commits": """
TASK: ANALYZE COMMIT DATA - Answer questions about repository commits

CRITICAL INSTRUCTIONS:
1. Answer ONLY using the commit data shown below
2. DO NOT make up or invent information
3. Include specific details (commit SHAs, author names, dates, files, messages)
4. Provide comprehensive, well-formatted answers with all relevant data points
5. For statistical questions, include numbers, percentages, and context
6. For list questions, provide the COMPLETE requested list with supporting details
7. If the data doesn't answer the question, say "The commit data doesn't contain this information"

FORMATTING REQUIREMENTS:
- For "top N" queries: Provide exactly N items in numbered list format
- For "latest" queries: Show full commit details including SHA, author, date, message
- For trend questions: Analyze the data, provide numbers, and draw conclusions
- For file queries: Count/list files with context about changes
- For author queries: Include commit counts and provide GitHub usernames/emails

RESPONSE STRUCTURE FOR DIFFERENT QUERY TYPES:
→ "Who are top contributors?" → "Based on the provided commits data, the top N contributors by commit count are:\n\n1. [Name] with [X] commits\n2. [Name] with [X] commits..."
→ "Latest commits?" → "The [N] latest commits are:\n\n1. [SHA]\n   Author: [Name] ([Email])\n   Date: [Date]\n   Message: [Message]\n\n2. [Next commit]..."
→ "Has activity increased?" → "Based on commit data analysis: [State finding]. Over the past [period], there were [X] commits compared to [Y] in the previous period."

RESPONSE LENGTH: Provide complete, well-structured answers with ALL requested items and details. Do not truncate lists.
""",
            "issues": """
TASK: ANALYZE ISSUES DATA - Answer questions about repository issues

CRITICAL INSTRUCTIONS:
1. Answer ONLY using the issues data shown below
2. DO NOT make up or invent information
3. Include specific details (issue numbers, titles, users, states, dates, comment counts)
4. Provide comprehensive, well-formatted answers with all relevant data points
5. For statistical questions, include numbers, percentages, and trends
6. For list questions, provide the COMPLETE requested list with supporting details
7. If the data doesn't answer the question, say "The issues data doesn't contain this information"

FORMATTING REQUIREMENTS:
- For "top N" queries: Provide exactly N issues in numbered list format with full details
- For "most recent" queries: Sort by date and provide complete issue information
- For "longest open" queries: Calculate duration and list oldest issues with creation dates
- For pattern/theme questions: Analyze all visible data and identify recurring topics
- For status queries: Provide counts and percentages (e.g., "62 open (10.7%), 580 closed (89.3%)")
- For reporter queries: List unique contributors with their issue counts

RESPONSE STRUCTURE FOR DIFFERENT QUERY TYPES:
→ "Highest comment count?" → "The top [N] issues with the highest comment counts are:\n\n1. Issue #[NUM]: [Title]\n   Comments: [X] | State: [STATE] | Created: [DATE]\n   Reporter: [USER]\n\n2. [Next issue]..."
→ "Longest open issues?" → "The issues that have been open the longest are:\n\n1. Issue #[NUM] (open since [DATE], [X] days)\n   Title: [Title]\n   Reporter: [USER]\n\n2. [Next issue]..."
→ "Recurring themes?" → "Based on analysis of [X] issues, the recurring themes are:\n\n- **[Theme 1]**: [Count] issues ([percentage]%) - Examples: #[NUM], #[NUM]\n- **[Theme 2]**: [Count] issues..."
→ "Most active reporters?" → "The most active issue reporters are:\n\n1. [USER]: [X] issues reported\n2. [USER]: [X] issues reported..."

RESPONSE LENGTH: Provide complete, well-structured answers with ALL requested items and full details. Do not truncate lists or omit information.
""",
            "general": """
TASK: GENERAL INFORMATION RETRIEVAL

INSTRUCTIONS:
- Provide comprehensive, well-structured answers
- Cite document names when referencing information
- Use bullet points or numbered lists for multi-part answers
- Include all relevant context and details from the documents
- Balance brevity with completeness - don't omit important information

RESPONSE LENGTH: Match the question's complexity. Provide enough detail for complete understanding.
""",
        }

        # Get task-specific instructions
        task_instruction = task_instructions.get(query_type, task_instructions["general"])

        # Different prompt structure for CSV data vs governance documents
        if query_type in ["commits", "issues"]:
            data_label = f"{query_type.upper()} DATA"

            # Enhanced anti-hallucination rules for CSV data
            if query_type == "issues":
                extra_rules = """
6. NEVER invent issue numbers (like #1234, #5678)
7. NEVER invent usernames (like "JohnDoe", "JaneDoe", "BobSmith")
8. NEVER invent locations or states (like "CA", "NY", "TX")
9. If asked for "updated" issues but data only has "created" dates, say: "The data shows recently created issues, not recently updated"
10. Only use issue numbers, titles, and usernames that appear verbatim in the data below
11. If asked for "N items", provide EXACTLY N items, no more, no less
12. Include ALL available details: issue numbers, complete titles, reporter usernames, states, dates, comment counts
13. For analysis questions, examine ALL visible issues and provide comprehensive insights
14. Use structured formatting (numbered lists, bullet points, tables) for readability
"""
            elif query_type == "commits":
                extra_rules = """
6. NEVER invent commit SHAs or author names
7. If asked for "top contributors" and you see names with counts, LIST ALL OF THEM with counts
8. If asked for "N items", provide EXACTLY N items, no more, no less
9. If asked about "files" and you see filenames, COUNT or LIST THEM ALL
10. Include ALL available details: full SHAs (not truncated), complete emails, exact dates, commit messages
11. Do not be overly conservative - if data is clearly visible in the CSV, extract and present it
12. Use structured formatting (numbered lists, bullet points) for readability
"""
            else:
                extra_rules = ""

            system_prompt = f"""You are analyzing {query_type} data for the {project_name} repository.

{task_instruction}

⚠️ CRITICAL ANTI-HALLUCINATION RULES ⚠️
1. You MUST answer ONLY using the {query_type} data below
2. DO NOT use external knowledge, training data, or previous conversations
3. If information is missing, you MUST say: "The {query_type} data doesn't contain this information"
4. Be factual and precise
5. Include specific details from the data (SHAs, names, dates, numbers){extra_rules}

{data_label} FOR {project_name}:
{context}

REMINDER: Only use information from the {query_type} data above. Do not use external knowledge or invent data.

"""
        else:
            # Enhanced governance documents prompt with stronger anti-hallucination measures
            system_prompt = f"""You are a precise document analyst for the {project_name} project.

{task_instruction}

CRITICAL INSTRUCTIONS:

RULE 1: INFORMATION SOURCE
- Your ONLY source of information is the project documents provided below
- These documents include README, CONTRIBUTING, governance files, and other project documentation
- They contain information about the project's features, examples, guidelines, policies, and structure
- Answer questions about ANY aspect of the project if it appears in the documents
- DO NOT use external knowledge, training data, or general information beyond what's in the documents
- DO NOT make logical inferences beyond what is explicitly stated
- DO NOT fill in "reasonable" assumptions or common practices

RULE 2: HANDLING MISSING INFORMATION
If information is NOT in the documents, respond EXACTLY like this:
"The available project documents for {project_name} do not contain information about [topic]. I cannot answer this question based on the provided documents."

DO NOT:
❌ Provide general knowledge answers (e.g., "typically", "usually", "commonly")
❌ Make up specific details (numbers, percentages, thresholds, names, policies)
❌ Give partial answers then admit uncertainty afterward
❌ Hedge with phrases like "based on general practices" or "it's likely that"

RULE 3: VERIFICATION PROCESS
Before stating ANY fact:
1. Locate the exact text in the documents below
2. Verify it's explicitly stated, not inferred
3. Note which document it comes from
4. Only then include it in your answer

RULE 4: ANSWER FORMAT
✅ GOOD: "According to GOVERNANCE.md, maintainers are elected by consensus vote."
❌ BAD: "Maintainers are typically elected by a majority vote, though this isn't explicitly stated in the documents."

RULE 5: NAMES, NUMBERS, AND SPECIFICS
- Only mention names, emails, numbers, or percentages that appear verbatim in the documents
- If you cannot find a specific piece of information, say so explicitly
- Never invent examples or provide "typical" values

RULE 6: OUTPUT FORMAT - CRITICAL
DO NOT EXPOSE YOUR REASONING PROCESS TO THE USER.
- DO NOT write: "Here's a step-by-step guide...", "First, let me verify...", "Based on my analysis..."
- DO NOT explain: "I checked the documents...", "I found this in...", "Note that I followed..."
- DO NOT list steps: "1. Verify information, 2. Check LICENSE, 3. Review README..."
- DO NOT mention: "CRITICAL", "ANTI-HALLUCINATION", "PROTOCOL", "rules", or "guidelines I'm following"

CORRECT OUTPUT: Direct answer with source citation and adequate detail
Example: "You can contribute by submitting a PR adding examples to examples/vision/script_name.py (README.md). The maintainers who review contributions are @user1, @user2, and @user3 (CODEOWNERS)."

✅ CORRECT OUTPUT: When no information found
Example: "The available project documents do not contain information about voting procedures."

RULE 7: RESPONSE COMPLETENESS
- Provide COMPLETE answers with all relevant details from the documents
- Include supporting information like titles, dates, counts, names, or descriptions when available
- For list queries (e.g., "top 5 issues"), provide ALL requested items with details
- Balance brevity with informativeness - don't be overly terse
- The user is asking YOU a question. Give them a helpful, informative answer.

═══════════════════════════════════════════

AVAILABLE GOVERNANCE DOCUMENTS FOR {project_name}:
{context}

═══════════════════════════════════════════

FINAL REMINDER:
- Extract ONLY what is explicitly written above
- Cite document names when providing information (use format: "answer text (DOCUMENT_NAME)")
- If uncertain or information is missing, clearly state that
- DO NOT explain your reasoning process - just provide the answer

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

        user_prompt = f"""USER QUESTION: {query}

Your answer:"""

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
        query_type: str = "general",
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
            query_type: Type of query for task-specific prompting

        Returns:
            Dict with response and metadata
        """
        prompt = self._build_governance_prompt(
            query, context, project_name,
            conversation_history=conversation_history,
            query_type=query_type
        )

        # Use more conservative sampling parameters for factual accuracy
        # Lower temperature and top_p reduce hallucination risk
        actual_temperature = min(temperature, 0.2) if query_type != "general" else temperature

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": actual_temperature,  # Lower for factual queries
                "num_predict": max_tokens,
                "top_p": 0.7,  # Reduced from 0.9 for more focused sampling
                "top_k": 20,   # Reduced from 40 for more deterministic output
                "repeat_penalty": 1.1,  # Prevent repetition
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
        query_type: str = "general",
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
            query_type: Type of query for task-specific prompting

        Yields:
            Response chunks as they're generated
        """
        prompt = self._build_governance_prompt(
            query, context, project_name,
            conversation_history=conversation_history,
            query_type=query_type
        )

        # Use same conservative sampling as non-streaming
        actual_temperature = min(temperature, 0.2) if query_type != "general" else temperature

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": actual_temperature,
                "num_predict": max_tokens,
                "top_p": 0.7,
                "top_k": 20,
                "repeat_penalty": 1.1,
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
