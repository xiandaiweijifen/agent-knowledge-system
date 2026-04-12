from app.services.llm.answer_service import (
    build_answer_citations,
    build_context_block,
    generate_rag_answer,
)


def test_build_context_block_includes_source_file_and_section_metadata():
    block = build_context_block(
        [
            {
                "chunk_id": "rag_overview.md::chunk_7",
                "source_filename": "rag_overview.md",
                "section_path": [
                    "Retrieval-Augmented Generation Overview",
                    "Common Failure Modes",
                ],
                "content": "Common RAG failure modes include poor chunk boundaries.",
            }
        ]
    )

    assert "[rag_overview.md::chunk_7]" in block
    assert "Source File: rag_overview.md" in block
    assert "Source Section: Retrieval-Augmented Generation Overview / Common Failure Modes" in block


def test_build_answer_citations_prioritizes_chunks_aligned_with_answer_content():
    citations = build_answer_citations(
        "Short-term mitigation includes disabling an expensive promotion rule. "
        "Recovery should be confirmed with checkout conversion metrics.",
        [
            {
                "chunk_id": "checkout_service_runbook.md::chunk_4",
                "source_filename": "checkout_service_runbook.md",
                "section_title": "Mitigation Notes",
                "section_path": [
                    "Checkout Service Runbook",
                    "Mitigation Notes",
                ],
                "heading_level": 2,
                "content": (
                    "Short-term mitigation may include disabling an expensive promotion "
                    "rule. Recovery should be confirmed with checkout conversion metrics."
                ),
                "score": 0.71,
            },
            {
                "chunk_id": "agent_workflow.md::chunk_5",
                "source_filename": "agent_workflow.md",
                "section_title": "Failure Handling",
                "section_path": ["Enterprise Agent Workflow Guide", "Failure Handling"],
                "heading_level": 2,
                "content": "A production workflow needs failure handling at every stage.",
                "score": 0.75,
            },
        ]
    )

    assert citations[0] == {
        "chunk_id": "checkout_service_runbook.md::chunk_4",
        "source_filename": "checkout_service_runbook.md",
        "section_title": "Mitigation Notes",
        "section_path": ["Checkout Service Runbook", "Mitigation Notes"],
        "heading_level": 2,
    }
    assert citations[1]["chunk_id"] == "agent_workflow.md::chunk_5"


def test_generate_rag_answer_fallback_includes_structured_citations(monkeypatch):
    monkeypatch.setattr("app.services.llm.answer_service.settings.chat_provider", "fallback")

    result = generate_rag_answer(
        question="What are the common failure modes in RAG systems?",
        matches=[
            {
                "chunk_id": "rag_overview.md::chunk_7",
                "source_filename": "rag_overview.md",
                "section_title": "Common Failure Modes",
                "section_path": [
                    "Retrieval-Augmented Generation Overview",
                    "Common Failure Modes",
                ],
                "heading_level": 2,
                "content": "Common RAG failure modes include poor chunk boundaries.",
            }
        ],
    )

    assert result["answer_source"] == "fallback"
    assert result["answer_citations"] == [
        {
            "chunk_id": "rag_overview.md::chunk_7",
            "source_filename": "rag_overview.md",
            "section_title": "Common Failure Modes",
            "section_path": [
                "Retrieval-Augmented Generation Overview",
                "Common Failure Modes",
            ],
            "heading_level": 2,
        }
    ]
