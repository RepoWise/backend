"""
Intelligent Question Suggestion System for OSS Forensics
Generates contextually relevant follow-up questions based on:
- User's current query
- Intent type (GOVERNANCE, COMMITS, ISSUES)
- Answer content analysis
- Project context
"""

import re
from typing import List, Dict, Tuple
from loguru import logger


class QuestionSuggester:
    """
    Suggests contextually relevant follow-up questions based on the user's query
    and the system's response.
    """

    # ========================================================================
    # BASE QUESTION BANK - Organized by Intent and Topic
    # ========================================================================

    GOVERNANCE_QUESTIONS = {
        "maintainer": [
            "What are the prerequisites for becoming a maintainer on this project?",
            "Who currently serves on the governance committee, and how can we reach them?",
            "What responsibilities do maintainers have?",
            "How are maintainers selected or elected?",
        ],
        "decision_making": [
            "How are decisions made when maintainers disagree on a proposed change?",
            "What is the voting process for major changes?",
            "Who has veto power in this project?",
            "How long does the decision-making process typically take?",
        ],
        "contribution_process": [
            "What steps should I follow before opening a large pull request?",
            "Are there coding standards or style guides I must follow?",
            "What is the review process once I open a pull request?",
            "How should I structure my commit messages?",
        ],
        "security": [
            "How should security vulnerabilities be reported and handled?",
            "Who is responsible for security issues?",
            "What is the typical response time for security reports?",
            "Is there a bug bounty program?",
        ],
        "legal": [
            "Does the project require a CLA or DCO for outside contributions?",
            "What license does this project use?",
            "Who owns the copyright for contributed code?",
            "Are there any patent considerations?",
        ],
        "communication": [
            "What communication channels does the project recommend for daily coordination?",
            "How do I join the project's Slack or Discord?",
            "Are there regular community meetings?",
            "How can I reach the maintainers directly?",
        ],
        "release": [
            "How are release managers or release schedules determined?",
            "What is the typical release cadence?",
            "How can I track the next release?",
            "What is the process for including a feature in a release?",
        ],
        "onboarding": [
            "How do we onboard new contributors effectively within current governance rules?",
            "Are there 'good first issues' for new contributors?",
            "What documentation should I read before contributing?",
            "Is there a mentorship program available?",
        ],
    }

    COMMITS_QUESTIONS = {
        "activity": [
            "How many commits have landed in the last month, and is activity trending up or down?",
            "What is the commit frequency compared to last quarter?",
            "Which days of the week see the most commit activity?",
            "Has there been a recent spike or drop in activity?",
        ],
        "contributors": [
            "Who are the top five contributors by commit count this quarter?",
            "Are there contributors with a sudden drop in activity that we should check in on?",
            "How many new contributors joined in the last month?",
            "What is the contributor retention rate?",
        ],
        "code_churn": [
            "Which files or modules have seen the most churn recently?",
            "Which areas of the codebase receive the most frequent commits?",
            "Are there files that are frequently modified together?",
            "Which modules have the most refactoring activity?",
        ],
        "impact": [
            "Can we identify the authors responsible for the most lines added or removed?",
            "Who has contributed the most to documentation?",
            "Which contributors focus on bug fixes vs. new features?",
            "What is the average commit size?",
        ],
        "pr_metrics": [
            "How long, on average, does it take for a pull request to be merged?",
            "What percentage of PRs are merged vs. closed?",
            "Which PRs have been open the longest?",
            "How many reviewers typically review each PR?",
        ],
    }

    ISSUES_QUESTIONS = {
        "status": [
            "How many issues are currently open versus closed, and what's the ratio?",
            "What is the trend in open issues over time?",
            "How many issues were resolved in the last release cycle?",
            "What percentage of issues are bugs vs. feature requests?",
        ],
        "engagement": [
            "Which issues have the highest comment counts or longest time open?",
            "Who are the most active issue reporters or triagers?",
            "What is the average time to first response on new issues?",
            "Which issues were updated most recently, and what is their status?",
        ],
        "themes": [
            "Are there recurring bug themes or labels that keep resurfacing?",
            "Which issue labels are most common?",
            "Are there areas of the codebase with many bug reports?",
            "What are the most requested features?",
        ],
        "at_risk": [
            "Are there high-priority bugs that lack assignees or recent updates?",
            "Which pull requests or issues are at risk of falling through the cracks?",
            "How many stale issues should we close?",
            "Which long-running issues need attention?",
        ],
        "documentation": [
            "What documentation gaps have contributors flagged recently?",
            "Are there common questions in issues that should be documented?",
            "Which parts of the docs receive the most issue reports?",
            "Have documentation improvements reduced related issues?",
        ],
        "health": [
            "Are our community health metrics (issues, commits, reviews) improving or declining?",
            "What is the issue close rate trend?",
            "How responsive is the project to new issues?",
            "Is the community growing or shrinking?",
        ],
    }

    # ========================================================================
    # QUESTION SUGGESTION LOGIC
    # ========================================================================

    def __init__(self):
        """Initialize the question suggester."""
        logger.info("QuestionSuggester initialized")

    def suggest_questions(
        self,
        current_query: str,
        intent: str,
        answer: str = None,
        project_context: Dict = None
    ) -> List[str]:
        """
        Generate 3-4 contextually relevant follow-up questions.

        Args:
            current_query: The user's current query
            intent: Intent type (GOVERNANCE, COMMITS, ISSUES)
            answer: The system's answer to current_query (optional, for deeper context)
            project_context: Additional project info (optional)

        Returns:
            List of 3-4 suggested follow-up questions
        """
        logger.info(f"Generating suggestions for intent={intent}, query={current_query[:50]}...")

        # Stage 1: Get base suggestions based on intent and query topic
        base_suggestions = self._get_base_suggestions(intent, current_query)

        # Stage 2: Refine based on answer content (if provided)
        if answer:
            base_suggestions = self._refine_with_answer_analysis(
                base_suggestions, current_query, answer, intent
            )

        # Stage 3: Ensure diversity and relevance
        final_suggestions = self._ensure_diversity(base_suggestions, current_query)

        # Return top 3-4
        return final_suggestions[:4]

    def _get_base_suggestions(self, intent: str, query: str) -> List[str]:
        """
        Get base suggestions based on intent type and query keywords.

        Returns a prioritized list of relevant questions.
        """
        query_lower = query.lower()
        suggestions = []

        if intent == "GOVERNANCE":
            suggestions = self._get_governance_suggestions(query_lower)
        elif intent == "COMMITS":
            suggestions = self._get_commits_suggestions(query_lower)
        elif intent == "ISSUES":
            suggestions = self._get_issues_suggestions(query_lower)
        else:
            # Default: show a mix
            suggestions = self._get_default_suggestions()

        return suggestions

    def _get_governance_suggestions(self, query_lower: str) -> List[str]:
        """Get governance-specific suggestions based on query keywords."""
        suggestions = []

        # Maintainer-related queries → suggest decision-making, responsibilities
        if any(kw in query_lower for kw in ["maintainer", "committee", "leadership"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["decision_making"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["maintainer"][:2])

        # Decision-making queries → suggest contribution process, communication
        elif any(kw in query_lower for kw in ["decision", "vote", "disagree", "conflict"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["contribution_process"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["communication"][:2])

        # Contribution process → suggest code standards, review, legal
        elif any(kw in query_lower for kw in ["pull request", "pr", "contribute", "before"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["contribution_process"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["legal"][:2])

        # Security queries → suggest communication channels, legal
        elif any(kw in query_lower for kw in ["security", "vulnerability", "report"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["security"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["communication"][:2])

        # Legal queries → suggest contribution process, maintainer info
        elif any(kw in query_lower for kw in ["cla", "dco", "license", "legal", "copyright"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["legal"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["contribution_process"][:2])

        # Communication queries → suggest onboarding, maintainer contact
        elif any(kw in query_lower for kw in ["communication", "channel", "slack", "discord", "reach"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["communication"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["onboarding"][:2])

        # Release queries → suggest contribution timing, decision-making
        elif any(kw in query_lower for kw in ["release", "version", "schedule"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["release"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["contribution_process"][:2])

        # Onboarding queries → suggest good first issues (link to ISSUES intent)
        elif any(kw in query_lower for kw in ["onboard", "new", "getting started", "first"]):
            suggestions.extend(self.GOVERNANCE_QUESTIONS["onboarding"])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["contribution_process"][:2])

        # Default governance suggestions
        else:
            suggestions.extend(self.GOVERNANCE_QUESTIONS["maintainer"][:2])
            suggestions.extend(self.GOVERNANCE_QUESTIONS["contribution_process"][:2])

        return suggestions

    def _get_commits_suggestions(self, query_lower: str) -> List[str]:
        """Get commit-specific suggestions based on query keywords."""
        suggestions = []

        # Activity trend queries → suggest contributor analysis, code churn
        if any(kw in query_lower for kw in ["how many", "activity", "trend", "last month"]):
            suggestions.extend(self.COMMITS_QUESTIONS["contributors"][:2])
            suggestions.extend(self.COMMITS_QUESTIONS["code_churn"][:2])

        # Contributor queries → suggest activity trends, impact analysis
        elif any(kw in query_lower for kw in ["contributor", "top", "most active", "who"]):
            suggestions.extend(self.COMMITS_QUESTIONS["impact"])
            suggestions.extend(self.COMMITS_QUESTIONS["activity"][:2])

        # Code churn queries → suggest impact, PR metrics
        elif any(kw in query_lower for kw in ["churn", "file", "module", "area", "codebase"]):
            suggestions.extend(self.COMMITS_QUESTIONS["code_churn"])
            suggestions.extend(self.COMMITS_QUESTIONS["impact"][:2])

        # Impact queries → suggest contributor rankings, code churn
        elif any(kw in query_lower for kw in ["lines", "added", "removed", "impact", "author"]):
            suggestions.extend(self.COMMITS_QUESTIONS["impact"])
            suggestions.extend(self.COMMITS_QUESTIONS["contributors"][:2])

        # PR metrics queries → suggest activity, contributor trends
        elif any(kw in query_lower for kw in ["pr", "pull request", "merge", "review"]):
            suggestions.extend(self.COMMITS_QUESTIONS["pr_metrics"])
            suggestions.extend(self.COMMITS_QUESTIONS["contributors"][:2])

        # Default commit suggestions
        else:
            suggestions.extend(self.COMMITS_QUESTIONS["activity"][:2])
            suggestions.extend(self.COMMITS_QUESTIONS["contributors"][:2])

        return suggestions

    def _get_issues_suggestions(self, query_lower: str) -> List[str]:
        """Get issue-specific suggestions based on query keywords."""
        suggestions = []

        # Status queries → suggest engagement, themes
        if any(kw in query_lower for kw in ["open", "closed", "ratio", "how many"]):
            suggestions.extend(self.ISSUES_QUESTIONS["engagement"][:2])
            suggestions.extend(self.ISSUES_QUESTIONS["themes"][:2])

        # Engagement queries → suggest status, at-risk analysis
        elif any(kw in query_lower for kw in ["comment", "active", "reporter", "triager", "response"]):
            suggestions.extend(self.ISSUES_QUESTIONS["engagement"])
            suggestions.extend(self.ISSUES_QUESTIONS["at_risk"][:2])

        # Theme queries → suggest documentation gaps, health metrics
        elif any(kw in query_lower for kw in ["recurring", "theme", "label", "pattern", "bug"]):
            suggestions.extend(self.ISSUES_QUESTIONS["themes"])
            suggestions.extend(self.ISSUES_QUESTIONS["documentation"][:2])

        # At-risk queries → suggest health metrics, engagement
        elif any(kw in query_lower for kw in ["priority", "stale", "risk", "falling", "unassigned"]):
            suggestions.extend(self.ISSUES_QUESTIONS["at_risk"])
            suggestions.extend(self.ISSUES_QUESTIONS["health"][:2])

        # Documentation queries → suggest themes, onboarding health
        elif any(kw in query_lower for kw in ["documentation", "docs", "gap", "missing"]):
            suggestions.extend(self.ISSUES_QUESTIONS["documentation"])
            suggestions.extend(self.ISSUES_QUESTIONS["themes"][:2])

        # Health queries → suggest status, at-risk, engagement
        elif any(kw in query_lower for kw in ["health", "metric", "trend", "improving", "declining"]):
            suggestions.extend(self.ISSUES_QUESTIONS["health"])
            suggestions.extend(self.ISSUES_QUESTIONS["status"][:2])

        # Default issue suggestions
        else:
            suggestions.extend(self.ISSUES_QUESTIONS["status"][:2])
            suggestions.extend(self.ISSUES_QUESTIONS["engagement"][:2])

        return suggestions

    def _get_default_suggestions(self) -> List[str]:
        """Get default suggestions when intent is unclear."""
        return [
            "What are the prerequisites for becoming a maintainer on this project?",
            "How many commits have landed in the last month, and is activity trending up or down?",
            "How many issues are currently open versus closed, and what's the ratio?",
            "What communication channels does the project recommend for daily coordination?",
        ]

    def _refine_with_answer_analysis(
        self,
        base_suggestions: List[str],
        query: str,
        answer: str,
        intent: str
    ) -> List[str]:
        """
        Refine suggestions based on the content of the answer.

        This creates more intelligent follow-ups by understanding what was
        answered and suggesting natural next questions.
        """
        answer_lower = answer.lower()
        refined = base_suggestions.copy()

        # If answer mentions specific maintainers/people → suggest how to reach them
        if re.search(r'\b(maintainer|committee|team)\b', answer_lower):
            if intent == "GOVERNANCE":
                refined.insert(0, "How can I reach the maintainers or governance committee?")
                refined.insert(1, "What communication channels does the project recommend for daily coordination?")

        # If answer mentions CLA/DCO → suggest contribution process
        if re.search(r'\b(cla|dco|sign|agreement)\b', answer_lower):
            refined.insert(0, "What steps should I follow before opening a large pull request?")

        # If answer mentions high activity or many commits → suggest contributor analysis
        if re.search(r'\b(many commits|high activity|increasing)\b', answer_lower):
            if intent == "COMMITS":
                refined.insert(0, "Who are the top five contributors by commit count this quarter?")
                refined.insert(1, "Which areas of the codebase receive the most frequent commits?")

        # If answer mentions drop in activity → suggest investigation
        if re.search(r'\b(drop|decrease|declining|fewer)\b', answer_lower):
            if intent == "COMMITS":
                refined.insert(0, "Are there contributors with a sudden drop in activity that we should check in on?")
            elif intent == "ISSUES":
                refined.insert(0, "Are our community health metrics improving or declining?")

        # If answer mentions high issue count → suggest triage questions
        if re.search(r'\b(many issues|high|backlog)\b', answer_lower):
            if intent == "ISSUES":
                refined.insert(0, "Are there high-priority bugs that lack assignees or recent updates?")
                refined.insert(1, "Which pull requests or issues are at risk of falling through the cracks?")

        # If answer mentions documentation → suggest doc-related questions
        if re.search(r'\b(documentation|docs|readme)\b', answer_lower):
            refined.insert(0, "What documentation gaps have contributors flagged recently?")

        # If answer says "not documented" or "not specified" → suggest general questions
        if re.search(r'\b(not documented|not specified|not found|no information)\b', answer_lower):
            if intent == "GOVERNANCE":
                refined.insert(0, "What communication channels does the project recommend for daily coordination?")
                refined.insert(1, "Are there 'good first issues' for new contributors?")

        return refined

    def _ensure_diversity(self, suggestions: List[str], current_query: str) -> List[str]:
        """
        Ensure suggestions are diverse and don't repeat the current query.

        Rules:
        - Remove duplicates
        - Remove questions too similar to current query
        - Ensure variety across different topics
        """
        # Remove duplicates while preserving order
        unique_suggestions = []
        seen = set()
        for q in suggestions:
            q_normalized = q.lower().strip()
            if q_normalized not in seen:
                seen.add(q_normalized)
                unique_suggestions.append(q)

        # Remove questions too similar to current query
        current_query_lower = current_query.lower()
        filtered = []
        for q in unique_suggestions:
            # Check similarity (simple keyword overlap)
            query_words = set(re.findall(r'\w+', current_query_lower))
            q_words = set(re.findall(r'\w+', q.lower()))
            common_words = query_words.intersection(q_words)

            # If more than 60% words overlap, it's too similar
            if len(common_words) / len(q_words) < 0.6:
                filtered.append(q)

        return filtered

    def get_initial_suggestions(self, project_name: str = None) -> List[str]:
        """
        Get initial suggestions when no query has been made yet.

        Returns a balanced mix across all intent types.
        """
        return [
            "What are the prerequisites for becoming a maintainer on this project?",
            "How many commits have landed in the last month, and is activity trending up or down?",
            "How many issues are currently open versus closed, and what's the ratio?",
            "What communication channels does the project recommend for daily coordination?",
        ]


# Export for easy import
__all__ = ["QuestionSuggester"]
