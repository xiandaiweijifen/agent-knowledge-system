from app.core.config import Settings


def test_vector_store_provider_defaults_to_qdrant():
    settings = Settings(
        _env_file=None,
        vector_store_provider="qdrant",
    )

    assert settings.vector_store_provider == "qdrant"
