from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from nimbus_support.config import Settings, get_settings
from nimbus_support.graph.state import AgentState
from nimbus_support.tracing import observation

SYSTEM_PROMPT = """You are a Nimbus customer-support clerk, not a general chatbot.

You will receive a user question, optional chat_history (last window of this session),
retrieved help-center chunks, and an optional live order lookup.

Chunks are nearest-neighbor search hits. They may be irrelevant.
chat_history is prior human/ai turns in this session — use it to resolve follow-ups
like "does that also log me out" without inventing new policy.
If an order lookup chunk is present (source_type order_lookup / slug order-*), you may
quote only those fields. Never invent tracking numbers or statuses.

Rules:
- Answer ONLY if a chunk actually contains the answer to THIS question (after resolving
  pronouns from chat_history).
- If chunks are about a different topic (for example refunds when the user asked about weather), you must not quote them.
- Never invent policy, prices, tracking numbers, or exceptions.
- Never process refunds or cancellations. You may only explain the written policy.
- citation_slugs must be slugs from the provided chunks. Empty if you cannot answer.

Return JSON only:
{"route": "grounded" | "out_of_scope", "answer": "string", "citation_slugs": ["slug"]}
"""


@dataclass(frozen=True)
class GenerateResult:
    route: str
    answer: str
    citation_slugs: list[str]


class LLMClient(Protocol):
    def complete(
        self,
        *,
        query: str,
        chunks: list[dict[str, Any]],
        messages: list[dict[str, str]] | None = None,
        order: dict[str, Any] | None = None,
    ) -> GenerateResult:
        ...


def generate_node(state: AgentState, llm: LLMClient) -> dict:
    with observation("generate"):
        result = llm.complete(
            query=state.get("query", ""),
            chunks=state.get("chunks") or [],
            messages=state.get("messages") or [],
            order=state.get("order"),
        )
    route = result.route if result.route in {"grounded", "out_of_scope"} else "out_of_scope"
    return {
        "route": route,
        "draft": result.answer,
        "cited_slugs": result.citation_slugs,
    }


def list_gemini_models() -> list[str]:
    """Names your API key can actually call (not the docs marketing names)."""
    settings = get_settings()
    if not settings.gemini_key:
        raise RuntimeError("GEMINI_API_KEY missing in .env")
    from google import genai

    client = genai.Client(api_key=settings.gemini_key)
    names: list[str] = []
    for model in client.models.list():
        raw = getattr(model, "name", "") or ""
        short = raw.split("/")[-1]
        methods = getattr(model, "supported_actions", None) or getattr(
            model, "supported_generation_methods", None
        )
        if methods and "generateContent" not in str(methods):
            continue
        if short.startswith("gemini") and "embed" not in short:
            names.append(short)
    return sorted(set(names))


def make_llm_client(settings: Settings | None = None) -> LLMClient | None:
    """Gemini wins if both keys are set. Identity/jailbreak work with neither."""
    settings = settings or get_settings()
    if settings.gemini_key:
        return GeminiChat(settings)
    if settings.openai_api_key:
        return OpenAIChat(settings)
    return None


def _user_payload(
    query: str,
    chunks: list[dict[str, Any]],
    messages: list[dict[str, str]] | None,
    order: dict[str, Any] | None,
) -> str:
    return json.dumps(
        {
            "question": query,
            "chat_history": messages or [],
            "order": order,
            "chunks": [
                {
                    "slug": chunk.get("slug"),
                    "title": chunk.get("title"),
                    "source_type": chunk.get("source_type"),
                    "content": chunk.get("content"),
                }
                for chunk in chunks
            ],
        }
    )


class GeminiChat:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.gemini_key:
            raise RuntimeError(
                "GEMINI_API_KEY is missing. Get one at https://aistudio.google.com/apikey "
                "and put it in .env"
            )
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=self._settings.gemini_key)

    def complete(
        self,
        *,
        query: str,
        chunks: list[dict[str, Any]],
        messages: list[dict[str, str]] | None = None,
        order: dict[str, Any] | None = None,
    ) -> GenerateResult:
        response = self._client.models.generate_content(
            model=self._settings.gemini_chat_model,
            contents=_user_payload(query, chunks, messages, order),
            config=self._types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,
                max_output_tokens=400,
                response_mime_type="application/json",
                automatic_function_calling=self._types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
        return _parse_generate_json(response.text or "{}")


class OpenAIChat:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Identity/jailbreak still work without it; "
                "support answers need a key. Put it in .env"
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=self._settings.openai_api_key)

    def complete(
        self,
        *,
        query: str,
        chunks: list[dict[str, Any]],
        messages: list[dict[str, str]] | None = None,
        order: dict[str, Any] | None = None,
    ) -> GenerateResult:
        response = self._client.chat.completions.create(
            model=self._settings.openai_chat_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_payload(query, chunks, messages, order)},
            ],
        )
        text = response.choices[0].message.content or "{}"
        return _parse_generate_json(text)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse_generate_json(text: str) -> GenerateResult:
    cleaned = _FENCE.sub("", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return GenerateResult(route="out_of_scope", answer="", citation_slugs=[])
    slugs = data.get("citation_slugs") or []
    if not isinstance(slugs, list):
        slugs = []
    return GenerateResult(
        route=str(data.get("route") or "out_of_scope"),
        answer=str(data.get("answer") or ""),
        citation_slugs=[str(slug) for slug in slugs],
    )
