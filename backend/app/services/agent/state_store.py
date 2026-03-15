import json
import os
import uuid
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_path.write_text(serialized, encoding="utf-8")
    try:
        os.replace(temp_path, path)
    except PermissionError:
        path.write_text(serialized, encoding="utf-8")
        try:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
        except PermissionError:
            # Some Windows test directories temporarily lock the temp file.
            # The canonical state has already been written to `path`.
            pass
