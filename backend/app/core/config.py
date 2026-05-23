from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    agent_default_runtime: str = "legacy"
    embedding_provider: str = "mock"
    vector_store_provider: str = "qdrant"
    knowledge_write_qdrant: bool = True
    chat_provider: str = "fallback"
    route_planner_provider: str = "fallback"
    tool_planner_provider: str = "fallback"
    clarification_planner_provider: str = "fallback"
    workflow_planner_provider: str = "fallback"
    skill_planner_provider: str = "fallback"
    knowledge_retrieval_mode: str = "llamaindex"
    workflow_planner_debug_capture: bool = False
    planner_cache_ttl_seconds: int = 120
    planner_cache_max_entries: int = 256
    embedding_http_trust_env: bool = False
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_route_planner_model: str = ""
    openai_tool_planner_model: str = ""
    openai_clarification_planner_model: str = ""
    openai_workflow_planner_model: str = ""
    openai_skill_planner_model: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.5-flash-lite"
    gemini_route_planner_model: str = ""
    gemini_tool_planner_model: str = ""
    gemini_clarification_planner_model: str = ""
    gemini_workflow_planner_model: str = ""
    gemini_skill_planner_model: str = ""
    database_url: str = ""
    redis_url: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "agent_knowledge_chunks"
    qdrant_local_path: str = ""
    qdrant_prefer_grpc: bool = False
    qdrant_http_trust_env: bool = False
    qdrant_timeout_seconds: int = 5
    langsmith_tracing_enabled: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "agent-knowledge-system"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    @field_validator("qdrant_local_path", mode="before")
    @classmethod
    def normalize_qdrant_local_path(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""

        path = Path(normalized)
        if path.is_absolute():
            return str(path)

        return str((REPO_ROOT / path).resolve())

    model_config = SettingsConfigDict(
        env_file=(
            str(REPO_ROOT / ".env"),
            str(BACKEND_ROOT / ".env"),
        ),
        extra="ignore",
    )


settings = Settings()
