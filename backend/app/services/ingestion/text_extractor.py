from pathlib import Path
import json


TEXT_FILE_SUFFIXES = {".txt", ".md", ".json"}


def _stringify_json_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _flatten_json_value(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        lines: list[str] = []
        for key, nested_value in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten_json_value(nested_value, next_prefix))
        return lines

    if isinstance(value, list):
        lines: list[str] = []
        for index, nested_value in enumerate(value):
            next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            lines.extend(_flatten_json_value(nested_value, next_prefix))
        return lines

    if prefix:
        return [f"{prefix}: {_stringify_json_scalar(value)}"]
    return [_stringify_json_scalar(value)]


def _extract_text_from_json_file(file_path: Path) -> str:
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("text_decode_error") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("json_decode_error") from exc

    flattened_lines = _flatten_json_value(payload)
    return "\n".join(line for line in flattened_lines if line.strip())


def extract_text_from_file(file_path: Path) -> str:
    """Extract plain text content from a supported local document."""
    suffix = file_path.suffix.lower()
    if suffix not in TEXT_FILE_SUFFIXES:
        raise ValueError("unsupported_file_type")

    if suffix == ".json":
        return _extract_text_from_json_file(file_path)

    try:
        # Keep UTF-8 as the baseline contract for the initial ingestion pipeline.
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("text_decode_error") from exc
