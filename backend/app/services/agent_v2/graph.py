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

from app.services.agent_v2.state import AgentState
from app.services.agent_v2.nodes.answer import answer_node
from app.services.agent_v2.nodes.clarify import clarify_node
from app.services.agent_v2.nodes.retrieval import retrieval_node
from app.services.agent_v2.nodes.router import route_decision, router_node
from app.services.agent_v2.nodes.tool_exec import tool_exec_node


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
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("tool_exec", tool_exec_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("answer", answer_node)

    # Edges
    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route_decision)
    builder.add_edge("retrieval", "answer")
    builder.add_edge("tool_exec", "answer")
    builder.add_edge("clarify", END)
    builder.add_edge("answer", END)

    return builder.compile(checkpointer=checkpointer)


# Module-level compiled graph (no persistence) — useful for quick tests
agent_graph = build_graph()
