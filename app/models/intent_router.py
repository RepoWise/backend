"""
Intent Classification Router
Determines whether a query should go to:
- General LLM (generic questions not project-specific)
- Project Doc RAG (project documents: README, LICENSE, CONTRIBUTING, etc.)
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
    - PROJECT_DOC_BASED: Questions about project governance, contribution, maintainers
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
        "which", "what are the", "ratio", "vs"
    }

    # Keywords for each intent type
    PROJECT_DOC_BASED_KEYWORDS = {
        "maintainer", "maintainers", "maintains", "maintained", "contribute", "contributing", "governance",
        "code of conduct", "coc", "license", "security", "policy", "guideline",
        "community", "decision", "voting", "leadership", "structure", "role",
        "responsibility", "contact", "reporting", "process", "required", "rules",
        # Code review and approval process keywords
        "review", "reviewer", "reviews",
        "merge", "merging",
        "permission", "permissions", "access",
        "approval", "approver", "approve"
    }

    COMMITS_KEYWORDS = {
        "commit", "committer", "committed", "commit message",
        "author", "file changed", "lines added", "lines deleted",
        "recent commit", "latest commit", "modification",
        "who changed", "when changed", "changelog", "most active", "top contributor",
        "files did", "which files", "modified the most", "files have been",
        # Pull request data and contributor actions
        "pull request", "pull requests",
        "who fixed", "fixed the most", "fixed most",
        "who wrote", "who modified",
        # Core developers and active contributors (statistical, commit-based)
        "core developer", "core developers", "active developer", "active developers",
        "key developer", "key developers", "main developer", "main developers"
    }

    ISSUES_KEYWORDS = {
        "issue", "bug", "feature request", "problem", "report", "ticket",
        "open issue", "closed issue", "issue state", "reporter", "comment",
        "discussion", "enhancement", "fix", "resolved",
        "ratio of", "how quickly", "closure rate", "being closed"
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
        "what do you know", "what is your purpose",

        # Weather queries
        "weather", "temperature", "forecast", "climate", "raining", "sunny",
        "cold", "hot", "celsius", "fahrenheit", "weather today", "weather like",

        # News/Current events
        "news", "headlines", "breaking news", "latest news", "today's news",
        "current events", "happening today", "in the news",

        # Politics
        "politics", "politician", "president", "congress", "senate", "political", "democrat", "republican",

        # Sports
        "sports", "game", "score", "match", "tournament", "championship",
        "team", "player", "football", "basketball", "baseball", "soccer",

        # Entertainment (removed standalone "show" - too broad, matches "show me...")
        "movie", "film", "actor", "actress", "celebrity", "tv show",
        "netflix", "series", "episode", "watching",

        # General knowledge (non-technical)
        "capital of", "population of", "largest city",
        "tallest mountain", "deepest ocean"
    }

    def __init__(self, llm_client=None, use_llm_classification=False):
        """
        Initialize intent router

        Args:
            llm_client: Optional LLM client for advanced classification
            use_llm_classification: If True, use LLM for primary classification; if False, use keyword-based
        """
        self.llm_client = llm_client
        self.use_llm_classification = use_llm_classification
        logger.info(f"Intent Router initialized (mode: {'LLM' if use_llm_classification else 'keyword-based'})")

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

    def classify_intent_llm(self, query: str, has_project_context: bool = True) -> Tuple[str, float]:
        """
        LLM-based intent classification using prompt engineering

        Args:
            query: User query
            has_project_context: Whether user has selected a project

        Returns:
            (intent_type, confidence)
            intent_type: GENERAL, PROJECT_DOC_BASED, COMMITS, ISSUES, OUT_OF_SCOPE
            confidence: 0.0-1.0
        """
        if not self.llm_client:
            logger.error("LLM client not available for classification")
            return "GENERAL", 0.3

        # Build classification prompt with examples
        prompt = f"""You are an expert query intent classifier for an open source software governance analysis system.

Classify the user's query into EXACTLY ONE category:

**PROJECT_DOC_BASED**: Questions about project governance, policies, contribution processes, maintainers, leadership, code of conduct, licenses, security policies, reporting procedures, decision-making processes.
Examples:
- "Who are the maintainers?"
- "How do I report a bug?" (process, not statistics)
- "What is the code of conduct?"
- "How are maintainers elected?"
- "Can I use this project commercially?"

**COMMITS**: Questions about commit history, code changes, file modifications, contributors, authorship, commit statistics, code activity, developer behavior patterns based on commits.
Examples:
- "Who are the top contributors by commit count?"
- "Who are the core developers?" (statistical top contributors)
- "Who is the core developer?" (top contributor)
- "Which files have been modified the most?"
- "Show me the latest commits"
- "Who contributed to documentation?" (based on files changed)
- "Which contributors focus on bug fixes vs. new features?" (analyzing commit messages)
- "SELECT commits WHERE author = 'X'"
- "COUNT total commits"

**ISSUES**: Questions about bug reports, feature requests, issue tracking, tickets, issue statistics, issue reporters, community engagement through issues.
Examples:
- "How many issues are open vs closed?"
- "Who are the most active issue reporters?"
- "What are the most commented issues?"
- "Who requests the most features?" (based on issues filed)
- "SELECT issues WHERE state = 'open'"
- "COUNT open issues"

**GENERAL**: Generic programming/tech questions NOT specific to the selected project. Educational content about software concepts, Git, programming languages, best practices.
Examples:
- "What is open source software?"
- "How does Git version control work?"
- "What is the difference between Git and GitHub?"
- "Explain machine learning basics"
- "What are best practices for code reviews?"

**OUT_OF_SCOPE**: Conversational queries about the assistant itself, greetings with no substantive question, meta-questions not about the project.
Examples:
- "Hello" (no question)
- "Who are you?"
- "What can you do?"

**Key Decision Rules**:
1. If query asks "how to [do something]" regarding contribution/reporting → PROJECT_DOC_BASED (process)
2. If query asks "how many/count/show me" regarding commits/files/code → COMMITS (data)
3. If query asks "how many/count/show me" regarding issues/bugs/tickets → ISSUES (data)
4. If query mentions "bug fixes" in context of commit messages or code changes → COMMITS
5. If query mentions "bug reports" in context of issues filed → ISSUES
6. If query is generic knowledge not about the specific project → GENERAL
7. SQL-like queries with "SELECT/COUNT/SUM" should route to COMMITS or ISSUES based on table name

User Query: "{query}"
Project Context: {"User has selected a project" if has_project_context else "No project selected"}

Respond with ONLY the category name: PROJECT_DOC_BASED, COMMITS, ISSUES, GENERAL, or OUT_OF_SCOPE"""

        try:
            llm_response = self.llm_client.generate_simple(prompt, max_tokens=20, temperature=0)
            llm_intent = llm_response.strip().upper()

            # Validate LLM response
            valid_intents = ["PROJECT_DOC_BASED", "COMMITS", "ISSUES", "GENERAL", "OUT_OF_SCOPE"]
            if llm_intent in valid_intents:
                confidence = 0.90  # High confidence for LLM classification
                logger.info(f"✅ LLM classified: '{query}' → {llm_intent} ({confidence:.2f})")
                return llm_intent, confidence
            else:
                logger.warning(f"⚠️  LLM returned invalid intent: {llm_intent}, falling back to keyword-based")
                return self.classify_intent_keyword(query, has_project_context)
        except Exception as e:
            logger.error(f"❌ LLM classification failed: {e}, falling back to keyword-based")
            return self.classify_intent_keyword(query, has_project_context)

    def classify_intent_keyword(self, query: str, has_project_context: bool = True) -> Tuple[str, float]:
        """
        Keyword-based hierarchical intent classification

        Stage 1: Procedure detection (PROJECT_DOC_BASED priority)
        Stage 2: Statistical detection (COMMITS/ISSUES)
        Stage 3: Keyword scoring with matched tokens
        Stage 4: LLM fallback (for ambiguous cases)

        Args:
            query: User query
            has_project_context: Whether user has selected a project

        Returns:
            (intent_type, confidence)
            intent_type: GENERAL, PROJECT_DOC_BASED, COMMITS, ISSUES
            confidence: 0.0-1.0
        """
        query_lower = query.lower()

        # =================================================================
        # STAGE 0: OUT-OF-SCOPE DETECTION (highest priority)
        # =================================================================
        # Detect conversational/meta questions not about the project
        # BUT: Allow greetings if followed by actual project questions

        # Strip common greetings from the beginning to extract the core query
        greeting_prefixes = ["hello", "hi there", "hey", "good morning", "good afternoon", "hi"]
        cleaned_query = query_lower.strip()

        # Remove greeting prefixes (with optional comma/punctuation)
        for greeting in greeting_prefixes:
            if cleaned_query.startswith(greeting):
                # Remove greeting and any following comma/punctuation
                cleaned_query = cleaned_query[len(greeting):].lstrip(" ,!.")
                break

        # If after removing greeting, there's substantial content (>5 words or contains project keywords)
        # then it's NOT out of scope - it's a polite question about the project
        if cleaned_query != query_lower:  # Greeting was removed
            word_count = len(cleaned_query.split())
            has_substance = word_count >= 5 or any(kw in cleaned_query for kw in
                list(self.PROJECT_DOC_BASED_KEYWORDS) + list(self.COMMITS_KEYWORDS) + list(self.ISSUES_KEYWORDS))

            if has_substance:
                logger.info(f"🎯 Stage 0: Greeting detected but query has substance → Continue classification")
                # Continue to next stage - don't classify as OUT_OF_SCOPE
                query_lower = cleaned_query  # Use cleaned query for further classification
            else:
                # Just a greeting with no real question
                logger.info(f"🎯 Stage 0: Pure greeting → OUT_OF_SCOPE")
                return "OUT_OF_SCOPE", 0.99
        else:
            # No greeting detected, check for other out-of-scope patterns
            if any(pattern in query_lower for pattern in self.OUT_OF_SCOPE_PATTERNS):
                logger.info(f"🎯 Stage 0: Out-of-scope → OUT_OF_SCOPE")
                return "OUT_OF_SCOPE", 0.99

        # If no project context, likely general
        if not has_project_context:
            if any(word in query_lower for word in ["add project", "select project", "choose project"]):
                return "GENERAL", 0.9
            return "GENERAL", 0.95

        # =================================================================
        # STAGE 1: PROCEDURE QUESTIONS → PROJECT_DOC_BASED (highest priority)
        # =================================================================
        matched_procedure = [p for p in self.PROCEDURE_PHRASES if p in query_lower]
        has_stats = any(stat in query_lower for stat in self.STATISTICAL_INDICATORS)

        if matched_procedure and not has_stats:
            logger.info(f"🎯 Stage 1: Procedure → PROJECT_DOC_BASED | matched: {matched_procedure[:2]}")
            return "PROJECT_DOC_BASED", 0.95

        # =================================================================
        # STAGE 2: STATISTICAL QUESTIONS → COMMITS/ISSUES
        # =================================================================
        if has_stats:
            # Determine if stats query is about commits or issues based on context
            # Use the full keyword sets for better coverage
            commits_context = any(kw in query_lower for kw in self.COMMITS_KEYWORDS)
            issues_context = any(kw in query_lower for kw in self.ISSUES_KEYWORDS)

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
        governance_score, gov_matches = self._count_keywords(query_lower, self.PROJECT_DOC_BASED_KEYWORDS)
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
        # When has_project_context=True, user is asking about a specific project, so prefer PROJECT_DOC_BASED
        if is_generic and not has_project_ref and not has_project_context and max(governance_score, commits_score, issues_score) == 0:
            logger.info(f"🎯 Stage 3: Generic query → GENERAL")
            return "GENERAL", 0.8

        # If has project context but query seems generic with no keywords, default to PROJECT_DOC_BASED
        # This handles queries like "what examples does it have?" when user has selected a project
        if has_project_context and is_generic and max(governance_score, commits_score, issues_score) == 0:
            logger.info(f"🎯 Stage 3: Project-specific general query → PROJECT_DOC_BASED")
            return "PROJECT_DOC_BASED", 0.7

        # Calculate scores with priority ordering
        scores = {
            "PROJECT_DOC_BASED": governance_score,
            "COMMITS": commits_score,
            "ISSUES": issues_score,
        }

        max_intent = max(scores, key=scores.get)
        max_score = scores[max_intent]

        # Confidence threshold for keyword matching
        if max_score >= 1.5:  # At least one strong keyword match
            confidence = min(0.95, max_score / 3.0)  # 3+ matches = very confident
            matched = gov_matches if max_intent == "PROJECT_DOC_BASED" else (com_matches if max_intent == "COMMITS" else iss_matches)
            logger.info(f"🎯 Stage 3: Keyword scoring → {max_intent} ({confidence:.2f}) | matched: {matched[:3]}")
            return max_intent, confidence

        # =================================================================
        # STAGE 4: LLM FALLBACK (for ambiguous cases)
        # =================================================================
        if max_score < 1.5 and self.llm_client:
            logger.info(f"🔄 Stage 4: Ambiguous case (max_score={max_score:.2f}), using LLM fallback")
            try:
                prompt = f"""You are a query intent classifier. Classify the following user query into EXACTLY ONE of these categories:

PROJECT_DOC_BASED - Questions about project governance, contribution process, maintainers, code of conduct, policies, reporting procedures
COMMITS - Questions about commit history, code changes, file modifications, contributors, authorship
ISSUES - Questions about bug reports, feature requests, issue tracking, tickets
GENERAL - Generic programming questions not specific to this project

Query: "{query}"

Respond with ONLY ONE WORD: PROJECT_DOC_BASED, COMMITS, ISSUES, or GENERAL"""

                llm_response = self.llm_client.generate_simple(prompt, max_tokens=10, temperature=0)
                llm_intent = llm_response.strip().upper()

                # Validate LLM response
                valid_intents = ["PROJECT_DOC_BASED", "COMMITS", "ISSUES", "GENERAL"]
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
            # Check governance/process context first (review process, permissions, etc.)
            governance_terms = ["review", "merge", "permission", "approve", "approval", "access"]
            if any(term in query_lower for term in governance_terms) or "maintain" in query_lower:
                return "PROJECT_DOC_BASED", 0.65
            else:
                return "COMMITS", 0.60

        elif query_lower.startswith(("what is", "what are", "what's")):
            return "PROJECT_DOC_BASED", 0.55

        elif query_lower.startswith(("how to", "how do", "how can")):
            return "PROJECT_DOC_BASED", 0.60

        elif "how many" in query_lower or "count" in query_lower:
            return "COMMITS", 0.50

        else:
            logger.info(f"🤷 No clear match, defaulting to GENERAL")
            return "GENERAL", 0.40

    def classify_intent(self, query: str, has_project_context: bool = True) -> Tuple[str, float]:
        """
        Main entry point for intent classification
        Routes to LLM-based or keyword-based classification based on configuration

        Args:
            query: User query
            has_project_context: Whether user has selected a project

        Returns:
            (intent_type, confidence)
        """
        if self.use_llm_classification:
            return self.classify_intent_llm(query, has_project_context)
        else:
            return self.classify_intent_keyword(query, has_project_context)

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
        import string

        count = 0
        matched = []

        # Remove punctuation from text for better word boundary matching
        text_clean = text.translate(str.maketrans('', '', string.punctuation))

        for keyword in keywords:
            if keyword in text:
                matched.append(keyword)

                # Check for exact word match with better boundary detection
                # Use cleaned text (no punctuation) for word boundary checks
                keyword_clean = keyword.translate(str.maketrans('', '', string.punctuation))

                # Exact word match scores higher (1.5)
                # Check word boundaries in cleaned text
                if f" {keyword_clean} " in f" {text_clean} " or text_clean.startswith(keyword_clean) or text_clean.endswith(keyword_clean):
                    count += 1.5
                else:
                    # Partial match (0.5)
                    count += 0.5
        return count, matched

    def should_use_rag(self, intent: str) -> bool:
        """Determine if intent requires RAG or direct LLM"""
        return intent in ["PROJECT_DOC_BASED", "COMMITS", "ISSUES"]

    def get_data_source(self, intent: str) -> str:
        """Get data source type for intent"""
        if intent == "PROJECT_DOC_BASED":
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
        gov_matches = [kw for kw in self.PROJECT_DOC_BASED_KEYWORDS if kw in query_lower]
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
