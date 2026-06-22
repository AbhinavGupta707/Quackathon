from __future__ import annotations

import importlib.util
from contextlib import ExitStack, contextmanager
from typing import Any, Iterator

from app.config import Settings
from app.schemas import ServiceHealthState, ServiceStatus


_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "content",
    "image",
    "frame",
    "raw_event",
    "raw_events",
    "raw_payload",
    "secret",
    "token",
}


def langsmith_status(settings: Settings) -> ServiceStatus:
    if importlib.util.find_spec("langsmith") is None:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="LangSmith SDK is not installed; tracing is unavailable.",
        )
    if not settings.langsmith_tracing:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="LangSmith tracing is disabled; set LANGSMITH_TRACING=true to enable provider/workflow traces.",
        )
    if not settings.langsmith_configured:
        return ServiceStatus(
            state=ServiceHealthState.DEGRADED,
            message="LangSmith tracing is requested but LANGSMITH_API_KEY is not configured.",
        )
    return ServiceStatus(
        state=ServiceHealthState.OK,
        message=f"LangSmith tracing is enabled for project '{settings.langsmith_project}'.",
    )


@contextmanager
def langsmith_trace(
    settings: Settings,
    name: str,
    *,
    run_type: str = "chain",
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any | None]:
    """Create an optional LangSmith trace without making tracing a runtime dependency."""

    if not settings.langsmith_runtime_enabled:
        yield None
        return

    try:
        from langsmith import Client
        from langsmith.run_helpers import trace, tracing_context
    except Exception:
        yield None
        return

    stack = ExitStack()
    try:
        client = Client(
            api_key=settings.langsmith_key_value(),
            api_url=str(settings.langsmith_endpoint),
        )
        safe_inputs = sanitize_for_trace(inputs or {}, include_content=settings.langsmith_trace_content)
        safe_outputs = sanitize_for_trace(outputs or {}, include_content=settings.langsmith_trace_content)
        safe_metadata = sanitize_for_trace(metadata or {}, include_content=False)
        stack.enter_context(
            tracing_context(
                enabled=True,
                client=client,
                project_name=settings.langsmith_project,
                tags=tags,
                metadata=safe_metadata,
            )
        )
        run = stack.enter_context(
            trace(
                name,
                run_type=run_type,
                inputs=safe_inputs,
                outputs=safe_outputs,
                client=client,
                project_name=settings.langsmith_project,
                tags=tags,
                metadata=safe_metadata,
            )
        )
    except Exception:
        stack.close()
        yield None
        return

    try:
        yield run
    finally:
        try:
            stack.close()
        except Exception:
            pass


def add_trace_outputs(
    run: Any | None,
    outputs: dict[str, Any],
    *,
    include_content: bool = False,
) -> None:
    if run is None:
        return
    try:
        run.add_outputs(sanitize_for_trace(outputs, include_content=include_content))
    except Exception:
        pass


def sanitize_for_trace(value: Any, *, include_content: bool) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if (
                key_lower in _SENSITIVE_KEYS
                or key_lower.endswith("api_key")
                or key_lower.endswith("secret")
                or key_lower.endswith("token")
            ):
                sanitized[key] = "[redacted]"
            elif not include_content and key_lower in {"query", "answer", "messages", "content"}:
                sanitized[key] = "[content omitted]"
            else:
                sanitized[key] = sanitize_for_trace(item, include_content=include_content)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_trace(item, include_content=include_content) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_for_trace(item, include_content=include_content) for item in value)
    return value
