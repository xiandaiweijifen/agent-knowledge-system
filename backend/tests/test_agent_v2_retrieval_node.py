from app.services.agent_v2.nodes.retrieval import retrieval_node


def test_retrieval_node_runs_query_pipeline(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_v2.nodes.retrieval.run_query",
        lambda filename, question, top_k: type(
            "QueryResponse",
            (),
            {
                "answer": "retrieved answer",
                "answer_source": "fallback",
                "model": "gemini-2.5-flash",
                "answered_at": "2026-04-07T00:00:00+00:00",
                "answer_latency_ms": 123.0,
                "chat_provider": "gemini",
                "chat_model": "gemini-2.5-flash",
                "retrieval": type(
                    "RetrievalResult",
                    (),
                    {
                        "model_dump": lambda self: {
                            "filename": filename,
                            "embedding_provider": "gemini",
                            "embedding_model": "gemini-embedding-001",
                            "vector_dim": 3072,
                            "question": question,
                            "top_k": top_k,
                            "retrieved_at": "2026-04-07T00:00:00+00:00",
                            "retrieval_latency_ms": 50.0,
                            "query_embedding_provider": "gemini",
                            "query_embedding_model": "gemini-embedding-001",
                            "matches": [],
                        }
                    },
                )(),
            },
        )(),
    )

    result = retrieval_node(
        {
            "question": "What is LangGraph?",
            "filename": "doc.txt",
            "top_k": 3,
            "route": "knowledge_retrieval",
            "route_reason": "Knowledge question.",
            "route_planning_mode": "llm_openai",
            "retrieval_result": None,
            "tool_chain": [],
            "clarification_question": None,
            "clarification_plan": None,
            "applied_clarification_fields": [],
            "question_rewritten": False,
            "answer": None,
            "answer_source": None,
            "model": None,
            "answered_at": None,
            "answer_latency_ms": None,
            "chat_provider": None,
            "chat_model": None,
            "workflow_status": "in_progress",
            "error": None,
            "messages": [],
        }
    )

    assert result["answer"] == "retrieved answer"
    assert result["answer_source"] == "fallback"
    assert result["model"] == "gemini-2.5-flash"
    assert result["retrieval_result"]["filename"] == "doc.txt"


def test_retrieval_node_skips_query_when_filename_missing():
    result = retrieval_node(
        {
            "question": "Search docs for RAG overview",
            "filename": "",
            "top_k": 3,
            "route": "knowledge_retrieval",
            "route_reason": "Knowledge question.",
            "route_planning_mode": "llm_openai",
            "retrieval_result": None,
            "tool_chain": [],
            "clarification_question": None,
            "clarification_plan": None,
            "applied_clarification_fields": [],
            "question_rewritten": False,
            "answer": None,
            "answer_source": None,
            "model": None,
            "answered_at": None,
            "answer_latency_ms": None,
            "chat_provider": None,
            "chat_model": None,
            "workflow_status": "in_progress",
            "error": None,
            "messages": [],
        }
    )

    assert result["retrieval_result"] is None
    assert result["workflow_status"] == "in_progress"
