from app.core.config import REPO_ROOT, Settings


def test_vector_store_provider_defaults_to_qdrant():
    settings = Settings(
        _env_file=None,
        vector_store_provider="qdrant",
    )

    assert settings.vector_store_provider == "qdrant"


def test_qdrant_local_path_is_resolved_against_repo_root():
    settings = Settings(
        _env_file=None,
        qdrant_local_path="./data/qdrant",
    )

    assert settings.qdrant_local_path == str((REPO_ROOT / "data" / "qdrant").resolve())


def test_embedding_http_trust_env_defaults_to_false():
    settings = Settings(_env_file=None)

    assert settings.embedding_http_trust_env is False
