from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.nodes import (
    supervisor_node,
    doc_analyzer_node,
    pyq_analyzer_node,
    study_planner_node,
    answer_evaluator_node,
    quiz_generator_node,
    exam_predictor_node,
    rag_fallback_node
)

# Initialize workflow state graph
workflow = StateGraph(AgentState)

# 1. Register Nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("doc_analyzer", doc_analyzer_node)
workflow.add_node("pyq_analyzer", pyq_analyzer_node)
workflow.add_node("study_planner", study_planner_node)
workflow.add_node("answer_evaluator", answer_evaluator_node)
workflow.add_node("quiz_generator", quiz_generator_node)
workflow.add_node("exam_predictor", exam_predictor_node)
workflow.add_node("rag_fallback", rag_fallback_node)

# 2. Configure Entrypoint
workflow.set_entry_point("supervisor")


# 3. Router Edge Logic
def route_agent_edges(state: AgentState) -> str:
    """Read next_agent state parameter to route to matching node."""
    return state.get("next_agent", "rag_fallback")


# 4. Add Conditional Routing Links
workflow.add_conditional_edges(
    "supervisor",
    route_agent_edges,
    {
        "doc_analyzer": "doc_analyzer",
        "pyq_analyzer": "pyq_analyzer",
        "study_planner": "study_planner",
        "answer_evaluator": "answer_evaluator",
        "quiz_generator": "quiz_generator",
        "exam_predictor": "exam_predictor",
        "rag_fallback": "rag_fallback"
    }
)

# 5. Connect Endpoints to Terminate Workflow
workflow.add_edge("doc_analyzer", END)
workflow.add_edge("pyq_analyzer", END)
workflow.add_edge("study_planner", END)
workflow.add_edge("answer_evaluator", END)
workflow.add_edge("quiz_generator", END)
workflow.add_edge("exam_predictor", END)
workflow.add_edge("rag_fallback", END)

# 6. Compile Graph
agent_workflow = workflow.compile()
