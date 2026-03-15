import shutil
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = BACKEND_DIR / "tests" / "_tmp"
TOOL_STATE_DIR = BACKEND_DIR.parent / "data" / "tool_state"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _handle_remove_readonly(func, path, exc_info):
    del exc_info
    Path(path).chmod(0o700)
    func(path)


def _cleanup_test_tmp_root() -> None:
    if TEST_TMP_ROOT.exists():
        shutil.rmtree(TEST_TMP_ROOT, ignore_errors=True, onerror=_handle_remove_readonly)


def _cleanup_state_tmp_files() -> None:
    if not TOOL_STATE_DIR.exists():
        return
    for temp_file in TOOL_STATE_DIR.glob("*.tmp"):
        try:
            temp_file.unlink(missing_ok=True)
        except PermissionError:
            pass
    temp_dir = TOOL_STATE_DIR / ".tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True, onerror=_handle_remove_readonly)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_tmp_root():
    _cleanup_test_tmp_root()
    _cleanup_state_tmp_files()
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    _cleanup_test_tmp_root()
    _cleanup_state_tmp_files()


@pytest.fixture
def workspace_tmp_path():
    temp_dir = TEST_TMP_ROOT / uuid.uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=True)
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True, onerror=_handle_remove_readonly)
