"""Adapter registry — maps tool names to their handler functions."""

from collections.abc import Callable

from app.schemas.tools import ToolExecutionRequest, ToolExecutionResponse

ToolAdapter = Callable[[ToolExecutionRequest], ToolExecutionResponse]

_ADAPTERS: dict[str, ToolAdapter] = {}


def register_adapter(tool_name: str, adapter: ToolAdapter) -> None:
    _ADAPTERS[tool_name] = adapter


def get_adapter(tool_name: str) -> ToolAdapter | None:
    return _ADAPTERS.get(tool_name)
