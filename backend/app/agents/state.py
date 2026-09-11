import uuid
from typing import TypedDict, List, Dict, Optional, Any


class AgentState(TypedDict):
    """
    Shared memory schema carrying data context across LangGraph agent execution nodes.
    """
    query: str
    subject_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    intent: str
    context_chunks: List[Dict]
    next_agent: str
    response: str
    extra_data: Dict[str, Any]
