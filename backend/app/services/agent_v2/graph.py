"""
LangGraph agent graph definition.

Topology
--------
START → router → (conditional) → retrieval → answer → END
                              → tool_exec  → answer → END
                              → clarify            → END

The graph is compiled once at import time without a checkpointer.
Pass a checkpointer (AsyncPostgresSaver from app.state) when you need
persistence and resume support.
"""

from langgraph.graph import END, START, StateGraph

from app.services.agent_v2.nodes.answer import answer_node
from app.services.agent_v2.nodes.router import route_decision, router_node
from app.services.agent_v2.nodes.specialists import (
    clarification_specialist_node,
    knowledge_specialist_node,
    operations_specialist_node,
)
from app.services.agent_v2.nodes.supervisor import supervisor_decision, supervisor_node
from app.services.agent_v2.state import AgentState


def build_graph(checkpointer=None):
    """
    Build and compile the agent StateGraph.

    Args:
        checkpointer: optional LangGraph checkpointer (e.g. AsyncPostgresSaver).
                      When provided the graph gains persistence and resume support.

    Returns:
        A compiled LangGraph graph ready for .invoke() / .ainvoke().
    """
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("router", router_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("knowledge_specialist", knowledge_specialist_node)
    builder.add_node("operations_specialist", operations_specialist_node)
    builder.add_node("clarification_specialist", clarification_specialist_node)
    builder.add_node("answer", answer_node)

    # Edges
    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "retrieval": "supervisor",
            "tool_exec": "supervisor",
            "clarify": "supervisor",
        },
    )
    builder.add_conditional_edges("supervisor", supervisor_decision)
    builder.add_edge("knowledge_specialist", "answer")
    builder.add_edge("operations_specialist", "answer")
    builder.add_edge("clarification_specialist", "router")
    builder.add_edge("answer", END)

    return builder.compile(checkpointer=checkpointer)


# Module-level compiled graph (no persistence) — useful for quick tests
agent_graph = build_graph()
