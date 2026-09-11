import uuid
from typing import Dict, Optional, Any

from app.agents.graph import agent_workflow


class AgentOrchestrationService:
    """
    Orchestration layer invoking compiled LangGraph agent workflow states.
    """

    async def run_agent_workflow(
        self,
        query: str,
        subject_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Initializes AgentState input dictionary, triggers async graph invocation,
        and returns the final updated state containing the generated response.
        """
        # Define initial inputs
        initial_state = {
            "query": query,
            "subject_id": subject_id,
            "user_id": user_id,
            "intent": "general",
            "context_chunks": [],
            "next_agent": "supervisor",
            "response": "",
            "extra_data": {}
        }

        # Run StateGraph workflow asynchronously
        final_state = await agent_workflow.ainvoke(initial_state)
        return final_state


# Singleton service instance
agent_orchestration_service = AgentOrchestrationService()
