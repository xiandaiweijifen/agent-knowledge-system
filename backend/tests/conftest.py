import shutil
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = BACKEND_DIR / "tests" / "_tmp"
SESSION_TMP_ROOT = TEST_TMP_ROOT / f"session_{uuid.uuid4().hex}"
TOOL_STATE_DIR = BACKEND_DIR.parent / "data" / "tool_state"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.llm.planner_cache_service import clear_planner_cache


def _handle_remove_readonly(func, path, exc_info):
    del exc_info
    Path(path).chmod(0o700)
    func(path)


def _cleanup_tmp_root(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True, onerror=_handle_remove_readonly)


def _cleanup_state_tmp_files() -> None:
    if not TOOL_STATE_DIR.exists():
        return
    temp_dir = TOOL_STATE_DIR / ".tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True, onerror=_handle_remove_readonly)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_tmp_root():
    _cleanup_state_tmp_files()
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    _cleanup_tmp_root(SESSION_TMP_ROOT)
    _cleanup_state_tmp_files()


@pytest.fixture
def workspace_tmp_path():
    temp_dir = SESSION_TMP_ROOT / uuid.uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=True)
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True, onerror=_handle_remove_readonly)


@pytest.fixture(autouse=True)
def isolated_workflow_run_store(workspace_tmp_path, monkeypatch):
    workflow_run_store_path = workspace_tmp_path / "workflow_runs.json"
    monkeypatch.setattr(
        "app.services.agent.orchestrator_service.WORKFLOW_RUN_STORE_PATH",
        workflow_run_store_path,
    )


@pytest.fixture(autouse=True)
def isolate_llm_planner_providers(monkeypatch):
    monkeypatch.setattr(settings, "tool_planner_provider", "fallback")
    monkeypatch.setattr(settings, "clarification_planner_provider", "fallback")
    monkeypatch.setattr(settings, "workflow_planner_provider", "fallback")
    monkeypatch.setattr(settings, "planner_cache_ttl_seconds", 120)
    monkeypatch.setattr(settings, "planner_cache_max_entries", 256)
    clear_planner_cache()
