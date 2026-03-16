from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    embedding_provider: str = "mock"
    chat_provider: str = "fallback"
    tool_planner_provider: str = "fallback"
    clarification_planner_provider: str = "fallback"
    workflow_planner_provider: str = "fallback"
    workflow_planner_debug_capture: bool = False
    planner_cache_ttl_seconds: int = 120
    planner_cache_max_entries: int = 256
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_tool_planner_model: str = ""
    openai_clarification_planner_model: str = ""
    openai_workflow_planner_model: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_chat_model: str = "gemini-2.5-flash-lite"
    gemini_tool_planner_model: str = ""
    gemini_clarification_planner_model: str = ""
    gemini_workflow_planner_model: str = ""
    database_url: str = ""
    redis_url: str = ""

    model_config = SettingsConfigDict(
        env_file=(
            str(REPO_ROOT / ".env"),
            str(BACKEND_ROOT / ".env"),
        ),
        extra="ignore",
    )


settings = Settings()
