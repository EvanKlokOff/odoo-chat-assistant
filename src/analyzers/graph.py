from langgraph.graph import StateGraph, END
from src.analyzers.state import AgentState
from src.analyzers.nodes import (
    analyze_query_type,
    retrieve_chat_messages,
    generate_review,
    check_compliance,
    extract_deviations,
)


def should_do_compliance(state: AgentState) -> str:
    """Determine which path to take based on query type"""
    if state.get("query_type") == "compliance":
        return "compliance"
    return "review"


def create_analysis_graph():
    """Create and compile the LangGraph workflow"""

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze_type", analyze_query_type)
    workflow.add_node("retrieve", retrieve_chat_messages)
    workflow.add_node("generate_review", generate_review)
    workflow.add_node("check_compliance", check_compliance)
    workflow.add_node("extract_deviations", extract_deviations)

    # Set entry point
    workflow.set_entry_point("analyze_type")

    # Add edges
    workflow.add_edge("analyze_type", "retrieve")

    # Conditional branching
    workflow.add_conditional_edges(
        "retrieve",
        should_do_compliance,
        {
            "compliance": "check_compliance",
            "review": "generate_review",
        }
    )

    # Add edges from analysis nodes
    workflow.add_edge("generate_review", END)
    workflow.add_edge("check_compliance", "extract_deviations")
    workflow.add_edge("extract_deviations", END)

    # Compile
    return workflow.compile()