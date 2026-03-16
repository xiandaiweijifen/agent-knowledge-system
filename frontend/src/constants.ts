import type { Locale, ViewKey } from "./types";

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

const viewCopy: Record<Locale, Array<{ key: ViewKey; label: string; kicker: string }>> = {
  en: [
    { key: "documents", label: "Documents", kicker: "Ingestion artifacts" },
    { key: "query", label: "Query Lab", kicker: "Retrieval and answer tracing" },
    { key: "evaluation", label: "Evaluation", kicker: "Retrieval benchmark sets" },
  ],
  zh: [
    { key: "documents", label: "文档", kicker: "摄取产物" },
    { key: "query", label: "查询台", kicker: "检索与回答追踪" },
    { key: "evaluation", label: "评测", kicker: "检索基准集" },
  ],
};

export function getViews(locale: Locale) {
  return viewCopy[locale];
}
