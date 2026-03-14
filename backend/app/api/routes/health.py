from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/health/system")
def system_health():
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": (
            settings.gemini_embedding_model
            if settings.embedding_provider == "gemini"
            else settings.openai_embedding_model
            if settings.embedding_provider == "openai"
            else "mock-embedding-v1"
        ),
        "chat_provider": settings.chat_provider,
        "chat_model": (
            settings.gemini_chat_model
            if settings.chat_provider == "gemini"
            else settings.openai_chat_model
            if settings.chat_provider == "openai"
            else "local-fallback"
        ),
        "providers": {
            "gemini_configured": bool(settings.gemini_api_key),
            "openai_configured": bool(settings.openai_api_key),
        },
        "storage": {
            "database_configured": bool(settings.database_url),
            "redis_configured": bool(settings.redis_url),
        },
    }
