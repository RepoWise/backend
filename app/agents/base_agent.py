"""
Base Agent class for all specialized agents
"""
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel


class AgentState(BaseModel):
    """State passed between agents in LangGraph workflow"""

    query: str
    project_id: Optional[str] = None
    intent: Optional[str] = None
    conversation_history: List[Dict] = []
    response: Optional[str] = None
    sources: List[Dict] = []
    metadata: Dict = {}
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all agents

    Each agent must implement:
    - handle_query: Process query and return response
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def handle_query(self, state: AgentState) -> AgentState:
        """
        Handle query and update state

        Args:
            state: Current agent state

        Returns:
            Updated agent state with response
        """
        pass

    def _create_metadata(self, **kwargs) -> Dict:
        """Helper to create metadata dict"""
        return {"agent": self.name, **kwargs}
