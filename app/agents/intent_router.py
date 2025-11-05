"""
Hybrid Intent Router with Deterministic Guards + LLM Fallback

Fast path: Deterministic pattern matching (<5ms)
Fallback: LLM classification (100-500ms)
"""
import re
import time
from typing import Tuple, Dict, Optional
from enum import Enum
from loguru import logger

from app.models.llm_client import LLMClient


class Intent(str, Enum):
    """Intent categories for routing queries"""

    GENERAL = "general"  # Greetings, general help, what-can-you-do
    GOVERNANCE = "governance"  # Governance docs, policies, licenses
    SUSTAINABILITY = "sustainability"  # Forecasts, health metrics, predictions
    CODE_COLLAB = "code_collaboration"  # Developer questions, who worked on X
    RECOMMENDATIONS = "recommendations"  # ReACT recommendations, actions


class IntentRouter:
    """
    Two-stage hybrid intent router:
    1. Deterministic pattern matching (95% of queries, <5ms)
    2. LLM classification (5% fallback, 100-500ms)
    """

    # Deterministic patterns for fast routing
    # NOTE: Order matters! More specific patterns (CODE_COLLAB) checked before broader ones (GOVERNANCE)
    DETERMINISTIC_PATTERNS = {
        Intent.GENERAL: [
            r"^(hi|hello|hey|howdy|greetings)[\s!?]*$",
            r"^(thanks|thank you|thx|cheers)[\s!?]*$",
            r"^(goodbye|bye|see you|cya)[\s!?]*$",
            r"^what (can|do) you (do|help)",
            r"^(help|how do i use)",
            r"^tell me about (yourself|this|ossprey)",
            r"^(who|what) are you",
        ],
        # CODE_COLLAB checked before GOVERNANCE for specificity
        Intent.CODE_COLLAB: [
            # Developer-specific queries
            r"who (worked|contributed|modified|authored|wrote|owns|maintains|committed|edited|changed)",
            r"developer(s)? (for|on|of|working|who|that)",
            r"contributor(s)? (for|on|of|to|who|that)",
            r"author(s)? of",
            r"(which|what) (file|module|component|package) (did|does)",
            # Collaboration patterns
            r"collaboration|collaborator(s)?",
            r"team member(s)?",
            r"worked (on|with|together)",
            r"file coupling|coupled files",
            # Activity and history
            r"most active (developer|contributor|maintainer)",
            r"commit history|commit log|commits (by|from|of)",
            r"developer activity|contributor activity",
            r"(who|what|which) commits?",
            r"code owner(ship)?",
            r"frequently (modified|changed|edited)",
        ],
        Intent.GOVERNANCE: [
            # High-level governance
            r"governance|policy|policies",
            r"license|licensing|copyright",
            r"code of conduct|conduct|coc",
            r"charter|bylaws|constitution",
            r"trademark|patent|legal",
            # Contribution guidelines (not specific queries about contributors)
            r"contributing guide|contribution guide",
            r"how (do i|to|can i) contribute",
            r"pull request (guidelines|rules|process|template)",
            r"commit message (format|style|convention|guidelines)",
            r"style guide|coding standards|code style",
            # Documentation
            r"documentation (standards|guidelines|style)",
            r"readme|security policy|security\.md",
            # Process
            r"workflow|ci/cd|github actions",
            r"issue (template|guidelines|labels)",
            r"branch(ing)? (strategy|model|policy)",
        ],
        Intent.SUSTAINABILITY: [
            r"sustainability|sustainable|health",
            r"forecast|predict|prediction|future",
            r"risk|risky|declining|decline",
            r"trend|trending|trajectory",
            r"(project|community) (health|vitality)",
            r"bus factor|key person risk",
        ],
        Intent.RECOMMENDATIONS: [
            r"recommend|recommendation|suggest|suggestion",
            r"should (i|we) (do|implement|add|fix)",
            r"best practice|improve|optimization",
            r"action|react|what to do",
            r"how (can|to) (improve|enhance|optimize|boost)",
        ],
    }

    LLM_CLASSIFICATION_PROMPT = """You are an intent classifier for OSS project queries.

Classify the user query into ONE of these intents:
- general: Greetings, help requests, general conversation (NO document retrieval needed)
- governance: Questions about licenses, policies, governance docs, contribution guidelines
- sustainability: Questions about project health, forecasts, trends, risks
- code_collaboration: Questions about developers, contributors, who worked on what
- recommendations: Requests for recommendations, suggestions, best practices

Query: "{query}"

IMPORTANT: Only respond with the intent name, nothing else.

Intent:"""

    def __init__(self):
        self.llm_client = LLMClient()
        self.stats = {
            "deterministic_hits": 0,
            "llm_fallback": 0,
            "total_queries": 0,
        }

    def route_query(
        self, query: str, project_id: Optional[str] = None
    ) -> Tuple[Intent, Dict]:
        """
        Route query to appropriate agent

        Returns:
            Tuple of (intent, metadata)
            metadata contains: {"method": "deterministic"|"llm", "confidence": float, "latency_ms": float}
        """
        start_time = time.time()
        self.stats["total_queries"] += 1

        # Stage 1: Try deterministic matching (fast path)
        deterministic_intent = self._deterministic_route(query)

        if deterministic_intent:
            latency_ms = (time.time() - start_time) * 1000
            self.stats["deterministic_hits"] += 1

            logger.info(
                f"Deterministic routing: '{query[:50]}...' → {deterministic_intent.value} ({latency_ms:.2f}ms)"
            )

            return deterministic_intent, {
                "method": "deterministic",
                "confidence": 1.0,
                "latency_ms": latency_ms,
            }

        # Stage 2: LLM classification fallback
        self.stats["llm_fallback"] += 1
        llm_intent, confidence = self._llm_route(query)

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            f"LLM routing: '{query[:50]}...' → {llm_intent.value} "
            f"(confidence={confidence:.2f}, {latency_ms:.2f}ms)"
        )

        return llm_intent, {
            "method": "llm",
            "confidence": confidence,
            "latency_ms": latency_ms,
        }

    def _deterministic_route(self, query: str) -> Optional[Intent]:
        """
        Fast deterministic pattern matching
        Returns Intent if match found, None otherwise
        """
        query_lower = query.lower().strip()

        # Try each intent's patterns
        for intent, patterns in self.DETERMINISTIC_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return intent

        return None

    def _llm_route(self, query: str) -> Tuple[Intent, float]:
        """
        LLM-based intent classification (fallback)
        Returns (Intent, confidence)
        """
        try:
            # Use LLM to classify intent
            prompt = self.LLM_CLASSIFICATION_PROMPT.format(query=query)

            # Generate with low temperature for more deterministic output
            response = self.llm_client.generate_simple(
                prompt=prompt, temperature=0.1, max_tokens=10
            )

            # Parse intent from response
            intent_str = response.strip().lower()

            # Map to Intent enum
            intent_mapping = {
                "general": Intent.GENERAL,
                "governance": Intent.GOVERNANCE,
                "sustainability": Intent.SUSTAINABILITY,
                "code_collaboration": Intent.CODE_COLLAB,
                "code collaboration": Intent.CODE_COLLAB,  # Handle space variant
                "recommendations": Intent.RECOMMENDATIONS,
            }

            # Calculate confidence based on match quality
            if intent_str in intent_mapping:
                # Clear match - high confidence
                intent = intent_mapping[intent_str]
                confidence = 0.9
            elif any(key in intent_str for key in intent_mapping.keys()):
                # Partial match - medium confidence
                for key, value in intent_mapping.items():
                    if key in intent_str:
                        intent = value
                        confidence = 0.75
                        break
            else:
                # No clear match - low confidence, fall back to GOVERNANCE
                logger.warning(f"LLM returned unclear intent: '{intent_str}', falling back to GOVERNANCE")
                intent = Intent.GOVERNANCE
                confidence = 0.5

            # Confidence threshold: if too uncertain, route to GOVERNANCE (safest)
            if confidence < 0.7 and intent != Intent.GOVERNANCE:
                logger.info(f"Confidence {confidence:.2f} below threshold, falling back to GOVERNANCE")
                return Intent.GOVERNANCE, confidence

            return intent, confidence

        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            # Default to governance (safest fallback)
            return Intent.GOVERNANCE, 0.5

    def get_stats(self) -> Dict:
        """Get routing statistics"""
        total = self.stats["total_queries"]
        if total == 0:
            return {"deterministic_rate": 0.0, "llm_rate": 0.0, "total": 0}

        return {
            "deterministic_rate": self.stats["deterministic_hits"] / total,
            "llm_rate": self.stats["llm_fallback"] / total,
            "total": total,
            "deterministic_hits": self.stats["deterministic_hits"],
            "llm_fallback": self.stats["llm_fallback"],
        }
