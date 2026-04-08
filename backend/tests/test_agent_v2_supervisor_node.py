from app.services.agent_v2.nodes.supervisor import supervisor_decision, supervisor_node


def test_supervisor_node_delegates_knowledge_route():
    result = supervisor_node(
        {
            "route": "knowledge_retrieval",
            "route_reason": "Knowledge question.",
        }
    )
    assert result["supervisor_agent"] == "knowledge_specialist"
    assert "knowledge_specialist" in result["supervisor_reason"]


def test_supervisor_decision_returns_operations_specialist():
    assert supervisor_decision({"supervisor_agent": "operations_specialist"}) == "operations_specialist"
