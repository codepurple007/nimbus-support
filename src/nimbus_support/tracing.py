"""Observability. n8n's built-in tracer is LangSmith; this project uses Langfuse
(same idea: wrap retrieve + generate). No invented n8n node.

Keys: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, optional LANGFUSE_HOST.
Without keys this is a no-op.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from nimbus_support.config import get_settings
from nimbus_support.pii import redact

_client = None
_failed = False


def tracing_enabled() -> bool:
    settings = get_settings()
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _client_or_none():
    global _client, _failed
    if _failed or not tracing_enabled():
        return None
    if _client is not None:
        return _client
    try:
        from langfuse import Langfuse

        settings = get_settings()
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or "https://cloud.langfuse.com",
        )
        return _client
    except Exception:
        _failed = True
        return None


@contextmanager
def observation(name: str, **kwargs: Any) -> Iterator[Any]:
    client = _client_or_none()
    if client is None:
        yield None
        return
    start = getattr(client, "start_as_current_observation", None)
    if start is None:
        yield None
        return
    with start(name=name) as obs:
        payload = kwargs.get("input")
        if payload is not None and hasattr(obs, "update"):
            try:
                obs.update(input=_redact_payload(payload))
            except Exception:
                pass
        yield obs


def flush() -> None:
    client = _client_or_none()
    if client is not None:
        client.flush()


def _redact_payload(payload: Any) -> Any:
    if isinstance(payload, str):
        return redact(payload)
    if isinstance(payload, dict):
        return {key: _redact_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_redact_payload(item) for item in payload]
    return payload
