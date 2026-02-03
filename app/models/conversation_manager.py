"""
Conversation Manager with Running Summary
Maintains a compressed summary of conversation history to reduce token usage
"""
from typing import Dict, Optional
from loguru import logger


class ConversationManager:
    """
    Manages conversation context using a running summary approach.
    Instead of passing full conversation history, maintains:
    - A running summary (250-300 tokens)
    - The last exchange (for recent context)
    This reduces token usage from O(n) to O(1) per conversation turn.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.running_summary = ""
        self.last_exchange = None
        self.turn_count = 0
        self.project_id = None  # Track which project this conversation is about

    def reset(self):
        """Reset conversation state"""
        self.running_summary = ""
        self.last_exchange = None
        self.turn_count = 0
        self.project_id = None
        logger.debug("Conversation manager reset")

    def check_and_reset_if_project_changed(self, new_project_id: str) -> bool:
        """
        Check if user switched to a different project and reset conversation if so.
        Returns True if conversation was reset, False otherwise.
        """
        if self.project_id is None:
            # First time setting project
            self.project_id = new_project_id
            return False

        if self.project_id != new_project_id:
            # User switched projects - clear conversation history
            logger.info(f"Project changed from {self.project_id} to {new_project_id} - resetting conversation")
            self.reset()
            self.project_id = new_project_id
            return True

        return False

    def get_context_for_prompt(self) -> str:
        """Get formatted conversation context for LLM prompt"""
        if self.turn_count == 0:
            return ""

        context_parts = []
        if self.running_summary:
            context_parts.append(f"CONVERSATION SUMMARY:\n{self.running_summary}")
        if self.last_exchange:
            context_parts.append(
                f"LAST EXCHANGE:\nUser: {self.last_exchange['user']}\n"
                f"Assistant: {self.last_exchange['assistant']}"
            )
        return "\n\n".join(context_parts)

    def update_after_response(self, user_message: str, assistant_response: str) -> str:
        """Update running summary after a conversation turn"""
        try:
            if self.turn_count == 0:
                self.running_summary = self._create_initial_summary(user_message, assistant_response)
            else:
                self.running_summary = self._update_summary(user_message, assistant_response)

            self.last_exchange = {
                "user": user_message,
                "assistant": self._truncate_response(assistant_response)
            }
            self.turn_count += 1
            logger.debug(f"Updated conversation summary (turn {self.turn_count})")
            return self.running_summary

        except Exception as e:
            logger.error(f"Error updating conversation summary: {e}")
            self.last_exchange = {
                "user": user_message,
                "assistant": self._truncate_response(assistant_response)
            }
            self.turn_count += 1
            return self.running_summary

    def _create_initial_summary(self, user_message: str, assistant_response: str) -> str:
        """Create initial summary from first conversation turn"""
        truncated = self._truncate_response(assistant_response, max_chars=1500)
        prompt = f"""You are creating a RUNNING SUMMARY of an ongoing conversation about a software project. This summary will be ACCUMULATED over multiple turns.

FIRST EXCHANGE:
User: {user_message}
Assistant: {truncated}

Create a comprehensive summary (EXACTLY 250-300 tokens) that captures:
1. What the user asked about (their goals/intent)
2. Key facts and information provided in the response
3. Important project details mentioned (maintainers, policies, processes, etc.)
4. Context that would be useful for future questions

Write the summary in third-person narrative form. Be SPECIFIC - include names, numbers, policies mentioned.
Output ONLY the summary (250-300 tokens), no preamble or meta-commentary."""

        return self.llm_client.generate_simple(prompt, temperature=0, max_tokens=400).strip()

    def _update_summary(self, user_message: str, assistant_response: str) -> str:
        """Update existing summary with new conversation turn"""
        truncated = self._truncate_response(assistant_response, max_chars=1500)
        prompt = f"""You are maintaining a RUNNING SUMMARY of an ongoing conversation. Your task is to ACCUMULATE information across conversation turns.

PREVIOUS SUMMARY (250-300 tokens):
{self.running_summary}

NEW EXCHANGE:
User: {user_message}
Assistant: {truncated}

CRITICAL REQUIREMENTS:
1. KEEP ALL IMPORTANT INFORMATION from the previous summary
2. ADD new facts, details, and context from the new exchange
3. Maintain EXACTLY 250-300 tokens by condensing repetitive details, not by removing unique information
4. Be SPECIFIC - preserve names, numbers, policies, and concrete details
5. Write in third-person narrative form
6. DO NOT just replace with the new exchange - ACCUMULATE across all turns

Example of good accumulation:
- BAD: "User asked about maintainers" (loses previous context)
- GOOD: "User explored project license (MIT), maintainers (Alice, Bob, Carol with merge rights), and now asked about contribution process"

Output ONLY the updated summary (250-300 tokens), no preamble."""

        return self.llm_client.generate_simple(prompt, temperature=0, max_tokens=400).strip()

    def _truncate_response(self, text: str, max_chars: int = 500) -> str:
        """Truncate response to fit in summary context"""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    def to_dict(self) -> Dict:
        """Serialize conversation state for API response"""
        return {
            "running_summary": self.running_summary,
            "last_exchange": self.last_exchange,
            "turn_count": self.turn_count,
            "project_id": self.project_id
        }

    def from_dict(self, data: Dict):
        """Restore conversation state from API request"""
        self.running_summary = data.get("running_summary", "")
        self.last_exchange = data.get("last_exchange", None)
        self.turn_count = data.get("turn_count", 0)
        self.project_id = data.get("project_id", None)
