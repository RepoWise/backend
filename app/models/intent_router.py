"""
Intent Classification Router
Determines whether a query should go to:
- General LLM (generic questions not project-specific)
- Governance RAG (governance documents)
- Commits Query Engine (commits CSV data)
- Issues Query Engine (issues CSV data)
"""
from typing import Tuple
from loguru import logger


class IntentRouter:
    """
    Routes user queries to appropriate processing pipeline

    Intent Types:
    - GENERAL: Generic ML/programming questions (not project-specific)
    - GOVERNANCE: Questions about project governance, contribution, maintainers
    - COMMITS: Questions about commits, contributors, code changes
    - ISSUES: Questions about issues, bugs, feature requests
    """

    # High-priority governance phrases (checked first) - PROCEDURE QUESTIONS
    PROCEDURE_PHRASES = {
        # How-to questions
        "how do i", "how can i", "how to", "how should i", "how would i",
        "what is the process", "what are the steps", "what steps",
        "required steps", "process for", "steps before", "before submitting",

        # Bug/Issue reporting (process, not data)
        "report a bug", "report an issue", "file a bug", "file an issue",
        "submit a bug", "submit an issue", "how to report", "where to report",
        "found a bug", "found an issue",

        # Contact/Communication
        "who do i contact", "who should i contact", "how to contact",
        "get in touch", "reach out", "contact maintainers",
        "maintains the project", "who maintains",

        # Contribution process
        "how to contribute", "how do i contribute", "how can i contribute",
        "become a contributor", "start contributing",

        # Security/Governance
        "security reporting", "report vulnerability", "report a vulnerability",
        "vulnerability found", "security issue",
        "voting rules", "decision process", "technical decisions"
    }

    # Statistical/Data indicators (COMMITS/ISSUES intent)
    STATISTICAL_INDICATORS = {
        "how many", "count", "number of", "total", "sum of",
        "list all", "show all", "show me", "display",
        "top", "most", "least", "highest", "lowest", "best", "worst",
        "latest", "recent", "newest", "oldest",
        "which", "what are the"
    }

    # Keywords for each intent type
    GOVERNANCE_KEYWORDS = {
        "maintainer", "maintains", "maintained", "contribute", "contributing", "governance",
        "code of conduct", "coc", "license", "security", "policy", "guideline",
        "community", "decision", "voting", "leadership", "structure", "role",
        "responsibility", "contact", "reporting", "process", "required", "rules"
    }

    COMMITS_KEYWORDS = {
        "commit", "committer", "committed", "commit message",
        "author", "file changed", "lines added", "lines deleted",
        "recent commit", "latest commit", "modification",
        "who changed", "when changed", "changelog", "most active", "top contributor"
    }

    ISSUES_KEYWORDS = {
        "issue", "bug", "feature request", "problem", "report", "ticket",
        "open issue", "closed issue", "issue state", "reporter", "comment",
        "discussion", "enhancement", "fix", "resolved"
    }

    GENERAL_INDICATORS = {
        # Questions that don't reference "this project" or specific data
        "what is", "how does", "explain", "define", "what are",
        "how to", "why", "when to use", "difference between",
        "best practice", "tutorial", "example", "learn"
    }

    # Out-of-scope conversational queries (NOT about the project)
    OUT_OF_SCOPE_PATTERNS = {
        # Identity/self-referential questions
        "who are you", "what are you", "are you", "tell me about yourself",
        "introduce yourself", "your name", "who made you", "who created you",

        # Greetings/pleasantries
        "hello", "hi there", "hey", "good morning", "good afternoon",
        "how are you", "what's up", "nice to meet you",

        # Capability questions about the assistant
        "what can you do", "what can you help", "can you help me",
        "what do you know", "what is your purpose"
    }

    def __init__(self, llm_client=None):
        """
        Initialize intent router

        Args:
            llm_client: Optional LLM client for advanced classification
        """
        self.llm_client = llm_client
        logger.info("Intent Router initialized")

    def is_aggregation_query(self, query: str) -> bool:
        """
        Detect if query is asking for aggregation/count

        Examples:
        - "how many issues are open?"
        - "count the number of commits"
        - "total contributors"
        - "how many open vs closed"

        Returns:
            True if aggregation query, False otherwise
        """
        query_lower = query.lower()

        aggregation_patterns = [
            "how many", "count", "number of", "total",
            "sum of", "count of", "# of",
            "how much", "what's the count"
        ]

        return any(pattern in query_lower for pattern in aggregation_patterns)

    def classify_intent(self, query: str, has_project_context: bool = True) -> Tuple[str, float]:
        """
        Hierarchical intent classification with LLM fallback

        Stage 1: Procedure detection (GOVERNANCE priority)
        Stage 2: Statistical detection (COMMITS/ISSUES)
        Stage 3: Keyword scoring with matched tokens
        Stage 4: LLM fallback (for ambiguous cases)

        Args:
            query: User query
            has_project_context: Whether user has selected a project

        Returns:
            (intent_type, confidence)
            intent_type: GENERAL, GOVERNANCE, COMMITS, ISSUES
            confidence: 0.0-1.0
        """
        query_lower = query.lower()

        # =================================================================
        # STAGE 0: OUT-OF-SCOPE DETECTION (highest priority)
        # =================================================================
        # Detect conversational/meta questions not about the project
        if any(pattern in query_lower for pattern in self.OUT_OF_SCOPE_PATTERNS):
            logger.info(f"🎯 Stage 0: Out-of-scope → OUT_OF_SCOPE")
            return "OUT_OF_SCOPE", 0.99

        # If no project context, likely general
        if not has_project_context:
            if any(word in query_lower for word in ["add project", "select project", "choose project"]):
                return "GENERAL", 0.9
            return "GENERAL", 0.95

        # =================================================================
        # STAGE 1: PROCEDURE QUESTIONS → GOVERNANCE (highest priority)
        # =================================================================
        matched_procedure = [p for p in self.PROCEDURE_PHRASES if p in query_lower]
        has_stats = any(stat in query_lower for stat in self.STATISTICAL_INDICATORS)

        if matched_procedure and not has_stats:
            logger.info(f"🎯 Stage 1: Procedure → GOVERNANCE | matched: {matched_procedure[:2]}")
            return "GOVERNANCE", 0.95

        # =================================================================
        # STAGE 2: STATISTICAL QUESTIONS → COMMITS/ISSUES
        # =================================================================
        if has_stats:
            # Determine if stats query is about commits or issues based on context
            commits_context = any(kw in query_lower for kw in [
                "commit", "author", "contributor", "file changed", "lines added",
                "lines deleted", "changelog", "code change"
            ])
            issues_context = any(kw in query_lower for kw in [
                "issue", "bug", "ticket", "feature request", "problem", "report"
            ])

            if commits_context and not issues_context:
                logger.info(f"🎯 Stage 2: Statistical → COMMITS")
                return "COMMITS", 0.90
            elif issues_context and not commits_context:
                logger.info(f"🎯 Stage 2: Statistical → ISSUES")
                return "ISSUES", 0.90
            # If both or neither, fall through to keyword scoring

        # =================================================================
        # STAGE 3: KEYWORD SCORING WITH MATCHED TOKENS
        # =================================================================
        governance_score, gov_matches = self._count_keywords(query_lower, self.GOVERNANCE_KEYWORDS)
        commits_score, com_matches = self._count_keywords(query_lower, self.COMMITS_KEYWORDS)
        issues_score, iss_matches = self._count_keywords(query_lower, self.ISSUES_KEYWORDS)

        # Check for general indicators
        is_generic = any(phrase in query_lower for phrase in self.GENERAL_INDICATORS)

        # Project-specific indicators (expanded to catch more variations)
        has_project_ref = any(word in query_lower for word in [
            "this project", "the project", "this repo", "the repository",
            "here", "this codebase", "keras-io", "keras", "resilientdb",
            "kubernetes", "airflow", "terraform", "vscode", "postgresql"
        ])

        # If query seems generic and doesn't reference project specifically AND no project context
        # When has_project_context=True, user is asking about a specific project, so prefer GOVERNANCE
        if is_generic and not has_project_ref and not has_project_context and max(governance_score, commits_score, issues_score) == 0:
            logger.info(f"🎯 Stage 3: Generic query → GENERAL")
            return "GENERAL", 0.8

        # If has project context but query seems generic with no keywords, default to GOVERNANCE
        # This handles queries like "what examples does it have?" when user has selected a project
        if has_project_context and is_generic and max(governance_score, commits_score, issues_score) == 0:
            logger.info(f"🎯 Stage 3: Project-specific general query → GOVERNANCE")
            return "GOVERNANCE", 0.7

        # Calculate scores with priority ordering
        scores = {
            "GOVERNANCE": governance_score,
            "COMMITS": commits_score,
            "ISSUES": issues_score,
        }

        max_intent = max(scores, key=scores.get)
        max_score = scores[max_intent]

        # Confidence threshold for keyword matching
        if max_score >= 1.5:  # At least one strong keyword match
            confidence = min(0.95, max_score / 3.0)  # 3+ matches = very confident
            matched = gov_matches if max_intent == "GOVERNANCE" else (com_matches if max_intent == "COMMITS" else iss_matches)
            logger.info(f"🎯 Stage 3: Keyword scoring → {max_intent} ({confidence:.2f}) | matched: {matched[:3]}")
            return max_intent, confidence

        # =================================================================
        # STAGE 4: LLM FALLBACK (for ambiguous cases)
        # =================================================================
        if max_score < 1.5 and self.llm_client:
            logger.info(f"🔄 Stage 4: Ambiguous case (max_score={max_score:.2f}), using LLM fallback")
            try:
                prompt = f"""You are a query intent classifier. Classify the following user query into EXACTLY ONE of these categories:

GOVERNANCE - Questions about project governance, contribution process, maintainers, code of conduct, policies, reporting procedures
COMMITS - Questions about commit history, code changes, file modifications, contributors, authorship
ISSUES - Questions about bug reports, feature requests, issue tracking, tickets
GENERAL - Generic programming questions not specific to this project

Query: "{query}"

Respond with ONLY ONE WORD: GOVERNANCE, COMMITS, ISSUES, or GENERAL"""

                llm_response = self.llm_client.generate_simple(prompt, max_tokens=10, temperature=0.1)
                llm_intent = llm_response.strip().upper()

                # Validate LLM response
                valid_intents = ["GOVERNANCE", "COMMITS", "ISSUES", "GENERAL"]
                if llm_intent in valid_intents:
                    logger.info(f"✅ Stage 4: LLM classified → {llm_intent}")
                    return llm_intent, 0.75  # Medium confidence for LLM fallback
                else:
                    logger.warning(f"⚠️  LLM returned invalid intent: {llm_intent}, falling back to heuristics")
            except Exception as e:
                logger.error(f"❌ LLM fallback failed: {e}")

        # =================================================================
        # FALLBACK: HEURISTIC PATTERNS (no strong matches)
        # =================================================================
        if query_lower.startswith(("who ", "who's", "who are")):
            if "maintain" in query_lower:
                return "GOVERNANCE", 0.65
            else:
                return "COMMITS", 0.60

        elif query_lower.startswith(("what is", "what are", "what's")):
            return "GOVERNANCE", 0.55

        elif query_lower.startswith(("how to", "how do", "how can")):
            return "GOVERNANCE", 0.60

        elif "how many" in query_lower or "count" in query_lower:
            return "COMMITS", 0.50

        else:
            logger.info(f"🤷 No clear match, defaulting to GENERAL")
            return "GENERAL", 0.40

    def _count_keywords(self, text: str, keywords: set) -> Tuple[float, list]:
        """
        Count keyword matches in text with scoring

        Args:
            text: Query text (lowercased)
            keywords: Set of keywords to match

        Returns:
            (score, matched_keywords)
            score: Float score based on match quality
            matched_keywords: List of keywords that matched
        """
        count = 0
        matched = []
        for keyword in keywords:
            if keyword in text:
                matched.append(keyword)
                # Exact word match scores higher
                if f" {keyword} " in f" {text} " or text.startswith(keyword) or text.endswith(keyword):
                    count += 1.5
                else:
                    count += 0.5
        return count, matched

    def should_use_rag(self, intent: str) -> bool:
        """Determine if intent requires RAG or direct LLM"""
        return intent in ["GOVERNANCE", "COMMITS", "ISSUES"]

    def get_data_source(self, intent: str) -> str:
        """Get data source type for intent"""
        if intent == "GOVERNANCE":
            return "vector_db"
        elif intent in ["COMMITS", "ISSUES"]:
            return "csv"
        else:
            return "none"

    def explain_routing(self, query: str, has_project_context: bool = True) -> str:
        """
        Explain why a query was routed a certain way (for debugging)

        Args:
            query: User query
            has_project_context: Whether project is selected

        Returns:
            Explanation string
        """
        intent, confidence = self.classify_intent(query, has_project_context)

        explanation = f"Query: '{query}'\n"
        explanation += f"Intent: {intent} (confidence: {confidence:.2f})\n"
        explanation += f"Project context: {has_project_context}\n"
        explanation += f"Use RAG: {self.should_use_rag(intent)}\n"
        explanation += f"Data source: {self.get_data_source(intent)}\n"

        # Show keyword matches
        query_lower = query.lower()
        gov_matches = [kw for kw in self.GOVERNANCE_KEYWORDS if kw in query_lower]
        com_matches = [kw for kw in self.COMMITS_KEYWORDS if kw in query_lower]
        iss_matches = [kw for kw in self.ISSUES_KEYWORDS if kw in query_lower]

        if gov_matches:
            explanation += f"Governance keywords: {gov_matches}\n"
        if com_matches:
            explanation += f"Commits keywords: {com_matches}\n"
        if iss_matches:
            explanation += f"Issues keywords: {iss_matches}\n"

        return explanation


# Example usage and testing
if __name__ == "__main__":
    router = IntentRouter()

    test_queries = [
        ("Who are the maintainers?", True),
        ("What is machine learning?", True),
        ("How do I contribute to this project?", True),
        ("Show me the latest commits", True),
        ("What are the open issues?", True),
        ("Who is the most active contributor?", True),
        ("What files changed recently?", True),
        ("How many bugs are open?", True),
        ("What is the code of conduct?", True),
        ("Explain backpropagation", True),
        ("What's the difference between supervised and unsupervised learning?", False),
    ]

    print("="*70)
    print("INTENT CLASSIFICATION TESTS")
    print("="*70)

    for query, has_context in test_queries:
        intent, confidence = router.classify_intent(query, has_context)
        print(f"\nQuery: '{query}'")
        print(f"Has Project: {has_context}")
        print(f"→ Intent: {intent} ({confidence:.2f})")
        print(f"  Data Source: {router.get_data_source(intent)}")
