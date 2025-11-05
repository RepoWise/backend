"""
LangGraph Orchestration for Agentic RAG System

Implements router-based workflow:
1. Intent Router classifies query
2. Routes to appropriate specialized agent
3. Agent processes query and returns response
"""
from typing import Dict, List, Optional
from loguru import logger

from langgraph.graph import StateGraph, END

from app.agents.base_agent import AgentState
from app.agents.intent_router import IntentRouter, Intent
from app.agents.agent_general import GeneralLLMAgent
from app.agents.agent_governance import GovernanceRAGAgent
from app.agents.agent_code_collab import CodeCollabGraphAgent
from app.agents.agent_recommendations import RecommendationsAgent
from app.agents.agent_forecaster import ForecasterAgent


class AgenticOrchestrator:
    """
    Main orchestrator for agentic RAG system

    Manages:
    - Intent classification
    - Agent routing
    - Response aggregation
    - Error handling
    """

    def __init__(self, rag_engine=None):
        """Initialize orchestrator with agents"""
        # Initialize intent router
        self.intent_router = IntentRouter()

        # Initialize agents - share RAG engine instance if provided
        self.agents = {
            Intent.GENERAL: GeneralLLMAgent(),
            Intent.GOVERNANCE: GovernanceRAGAgent(rag_engine=rag_engine),
            Intent.CODE_COLLAB: CodeCollabGraphAgent(),
            Intent.RECOMMENDATIONS: RecommendationsAgent(),
            Intent.SUSTAINABILITY: ForecasterAgent(),
        }

        # Build LangGraph workflow
        self.workflow = self._build_workflow()

        logger.info("AgenticOrchestrator initialized with agents: " +
                   ", ".join([agent.name for agent in self.agents.values()]))

    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph workflow

        Flow:
        1. route_intent: Classify query intent
        2. route_to_agent: Conditional routing to specialized agent
        3. agent_*: Agent processes query
        4. END: Return final state
        """
        workflow = StateGraph(AgentState)

        # Add routing node
        workflow.add_node("route_intent", self._route_intent_node)

        # Add agent nodes
        workflow.add_node("agent_general", self._agent_general_node)
        workflow.add_node("agent_governance", self._agent_governance_node)
        workflow.add_node("agent_code_collab", self._agent_code_collab_node)
        workflow.add_node("agent_recommendations", self._agent_recommendations_node)
        workflow.add_node("agent_sustainability", self._agent_sustainability_node)

        # Set entry point
        workflow.set_entry_point("route_intent")

        # Add conditional edges from router to agents
        workflow.add_conditional_edges(
            "route_intent",
            self._decide_agent_route,
            {
                "agent_general": "agent_general",
                "agent_governance": "agent_governance",
                "agent_code_collab": "agent_code_collab",
                "agent_recommendations": "agent_recommendations",
                "agent_sustainability": "agent_sustainability",
            },
        )

        # Add edges from agents to END
        workflow.add_edge("agent_general", END)
        workflow.add_edge("agent_governance", END)
        workflow.add_edge("agent_code_collab", END)
        workflow.add_edge("agent_recommendations", END)
        workflow.add_edge("agent_sustainability", END)

        return workflow.compile()

    def _route_intent_node(self, state: AgentState) -> AgentState:
        """Node: Route query to appropriate intent"""
        intent, routing_metadata = self.intent_router.route_query(
            state.query, state.project_id
        )

        state.intent = intent.value
        state.metadata.update({"routing": routing_metadata})

        logger.info(f"Intent routed to: {intent.value} ({routing_metadata['method']})")

        return state

    def _decide_agent_route(self, state: AgentState) -> str:
        """Conditional edge: Decide which agent node to route to"""
        intent = state.intent

        # Map intent to agent node name
        intent_to_node = {
            Intent.GENERAL.value: "agent_general",
            Intent.GOVERNANCE.value: "agent_governance",
            Intent.CODE_COLLAB.value: "agent_code_collab",
            Intent.RECOMMENDATIONS.value: "agent_recommendations",
            Intent.SUSTAINABILITY.value: "agent_sustainability",
        }

        node_name = intent_to_node.get(intent, "agent_general")

        logger.info(f"Routing to agent node: {node_name}")

        return node_name

    async def _agent_general_node(self, state: AgentState) -> AgentState:
        """Node: Execute Agent 0 (General LLM)"""
        agent = self.agents[Intent.GENERAL]
        return await agent.handle_query(state)

    async def _agent_governance_node(self, state: AgentState) -> AgentState:
        """Node: Execute Agent 1 (Governance RAG)"""
        agent = self.agents[Intent.GOVERNANCE]
        return await agent.handle_query(state)

    async def _agent_recommendations_node(self, state: AgentState) -> AgentState:
        """Node: Execute Agent 4 (Recommendations)"""
        agent = self.agents[Intent.RECOMMENDATIONS]
        return await agent.handle_query(state)

    async def _agent_sustainability_node(self, state: AgentState) -> AgentState:
        """Node: Execute Agent 3 (Forecaster)"""
        agent = self.agents[Intent.SUSTAINABILITY]
        return await agent.handle_query(state)

    async def _agent_code_collab_node(self, state: AgentState) -> AgentState:
        """Node: Execute Agent 2 (Code Collaboration GraphRAG)"""
        agent = self.agents[Intent.CODE_COLLAB]
        return await agent.handle_query(state)

    async def process_query(
        self,
        query: str,
        project_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Process user query through agentic workflow

        Args:
            query: User question
            project_id: Optional project identifier
            conversation_history: Optional previous conversation

        Returns:
            Dict with response, sources, and metadata
        """
        logger.info(f"Processing query: '{query[:50]}...'")

        # Create initial state
        state = AgentState(
            query=query,
            project_id=project_id,
            conversation_history=conversation_history or [],
            metadata={},
        )

        try:
            # Execute workflow
            final_state = await self.workflow.ainvoke(state.dict())

            # LangGraph returns a dict, not AgentState object
            # Extract result
            result = {
                "query": final_state.get("query", query),
                "response": final_state.get("response") or "No response generated",
                "sources": final_state.get("sources", []),
                "metadata": {
                    **final_state.get("metadata", {}),
                    "intent": final_state.get("intent"),
                    "project_id": final_state.get("project_id"),
                },
                "error": final_state.get("error"),
            }

            logger.success(
                f"Query processed successfully with intent: {final_state.get('intent')}"
            )

            return result

        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            return {
                "query": query,
                "response": "I encountered an error processing your request. Please try again.",
                "sources": [],
                "metadata": {},
                "error": str(e),
            }

    def get_stats(self) -> Dict:
        """Get orchestrator statistics"""
        return {
            "intent_router": self.intent_router.get_stats(),
            "agents": {
                intent.value: agent.name for intent, agent in self.agents.items()
            },
        }
