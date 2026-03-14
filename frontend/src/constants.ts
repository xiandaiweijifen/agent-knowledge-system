import type { ViewKey } from "./types";

export const presetQuestions: Record<string, string[]> = {
  "rag_overview.md": [
    "What is RAG?",
    "Why is chunking important in a RAG system?",
    "What is the role of embeddings?",
    "Why do production systems use reranking?",
  ],
  "agent_workflow.md": [
    "How does request routing work in an agent workflow?",
    "When should the agent use the tool execution path?",
    "Why is clarification necessary in an agent workflow?",
    "What should engineers log for observability in an agent workflow system?",
  ],
};

export const views: Array<{ key: ViewKey; label: string; kicker: string }> = [
  { key: "documents", label: "Documents", kicker: "Ingestion artifacts" },
  { key: "query", label: "Query Lab", kicker: "Retrieval and answer tracing" },
  { key: "evaluation", label: "Evaluation", kicker: "Retrieval benchmark sets" },
];
