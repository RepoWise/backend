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

    def reset(self):
        """Reset conversation state"""
        self.running_summary = ""
        self.last_exchange = None
        self.turn_count = 0
        logger.debug("Conversation manager reset")

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
        prompt = f"""Create a concise summary (250-300 tokens) of this conversation start.

User: {user_message}Assistant: {truncated}

Focus on: key topics discussed, user's intent/goals, important facts from the response.
Output only the summary, no preamble."""

        return self.llm_client.generate_simple(prompt, temperature=0, max_tokens=350).strip()

    def _update_summary(self, user_message: str, assistant_response: str) -> str:
        """Update existing summary with new conversation turn"""
        truncated = self._truncate_response(assistant_response, max_chars=1500)
        prompt = f"""Update this conversation summary. Keep it 250-300 tokens.

PREVIOUS SUMMARY:
{self.running_summary}

NEW EXCHANGE:
User: {user_message}
Assistant: {truncated}

Preserve important context, integrate new information, remove outdated details.
Output only the updated summary, no preamble."""

        return self.llm_client.generate_simple(prompt, temperature=0, max_tokens=350).strip()

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
            "turn_count": self.turn_count
        }

    def from_dict(self, data: Dict):
        """Restore conversation state from API request"""
        self.running_summary = data.get("running_summary", "")
        self.last_exchange = data.get("last_exchange", None)
        self.turn_count = data.get("turn_count", 0)
