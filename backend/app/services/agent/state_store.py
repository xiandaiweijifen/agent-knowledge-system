import json
import os
import time
from pathlib import Path
from typing import Any, Callable


def _unlink_with_retries(path: Path, attempts: int = 5, delay_seconds: float = 0.05) -> None:
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay_seconds)


def _temp_dir_for(path: Path) -> Path:
    return path.parent / ".tmp"


def _cleanup_stale_temp_files(path: Path) -> None:
    for candidate in path.parent.glob(f"{path.name}.*.tmp"):
        try:
            _unlink_with_retries(candidate)
        except PermissionError:
            # Best-effort cleanup only. A locked stale temp file should not
            # block the canonical state write.
            pass
    temp_dir = _temp_dir_for(path)
    if temp_dir.exists():
        fixed_temp_path = temp_dir / f"{path.name}.tmp"
        try:
            _unlink_with_retries(fixed_temp_path)
        except PermissionError:
            pass


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = _temp_dir_for(path)
    temp_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_stale_temp_files(path)
    temp_path = temp_dir / f"{path.name}.tmp"
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_path.write_text(serialized, encoding="utf-8")
    try:
        os.replace(temp_path, path)
    except PermissionError:
        path.write_text(serialized, encoding="utf-8")
        try:
            if temp_path.exists():
                _unlink_with_retries(temp_path)
        except PermissionError:
            # Some Windows environments temporarily lock the temp file. Keep a
            # single well-known temp file instead of accumulating UUID files.
            pass
    _cleanup_stale_temp_files(path)


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    raw_content = path.read_text(encoding="utf-8").strip()
    if not raw_content:
        return []

    try:
        loaded = json.loads(raw_content)
    except json.JSONDecodeError:
        return []

    if not isinstance(loaded, list):
        return []

    return [item for item in loaded if isinstance(item, dict)]


class JsonListRepository:
    def __init__(
        self,
        path: Path,
        *,
        normalizer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.path = path
        self.normalizer = normalizer

    def load(self) -> list[dict[str, Any]]:
        records = load_json_list(self.path)
        if self.normalizer is None:
            return records
        return [self.normalizer(record) for record in records]

    def save(self, records: list[dict[str, Any]]) -> None:
        payload = records
        if self.normalizer is not None:
            payload = [self.normalizer(record) for record in records]
        atomic_write_json(self.path, payload)
