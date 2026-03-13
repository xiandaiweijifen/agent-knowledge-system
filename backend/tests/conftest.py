import shutil
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def workspace_tmp_path():
    temp_dir = BACKEND_DIR / "tests" / "_tmp" / uuid.uuid4().hex
    temp_dir.mkdir(parents=True, exist_ok=True)
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)
