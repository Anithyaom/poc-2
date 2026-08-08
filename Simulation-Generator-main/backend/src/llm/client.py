"""Shared OpenAI-compatible client: model routing, timeouts, structured-output validation.

Two providers, both spoken through the OpenAI SDK since Ollama's server implements
the same API: **openai** drives simulation generation (LLM #2) because core_html
quality is what a teacher sees; **ollama** drives plan generation (LLM #1) because
blueprint drafts and revisions are the most-iterated call and shouldn't spend
OpenAI budget on every retry.

Never trust LLM output — every response is parsed and re-validated against a
Pydantic model before anything is persisted (spec §6).
"""

import json
import logging
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from src.config.settings import settings

logger = logging.getLogger(__name__)

Provider = Literal["openai", "ollama"]


class LLMOutputError(Exception):
    """The model returned something we could not parse or validate.

    Carries the raw response so the job can persist it for debugging instead of
    crashing the worker.
    """

    def __init__(self, message: str, raw: str | None = None):
        super().__init__(message)
        self.raw = raw


_clients: dict[Provider, OpenAI] = {}


def get_client(provider: Provider = "openai") -> OpenAI:
    if provider not in _clients:
        if provider == "openai":
            if not settings.openai_api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. It is required from day one — there is no "
                    "mock path for simulation generation in simgen by design."
                )
            kwargs: dict[str, Any] = {
                "api_key": settings.openai_api_key,
                # Always pass base_url explicitly, even the default. Compose sets
                # OPENAI_BASE_URL="" (not unset) when the .env value is blank, and
                # the SDK falls back to reading that same env var itself when
                # base_url is omitted — it treats "" as a real (empty) root rather
                # than absent, producing a URL with no host.
                "base_url": settings.openai_base_url or "https://api.openai.com/v1",
                # max_retries covers transient network/5xx; validation retries are the caller's.
                "timeout": 300.0,
                "max_retries": 2,
            }
        else:
            kwargs = {
                "api_key": settings.ollama_api_key,
                "base_url": settings.ollama_base_url,
                "timeout": 300.0,
                "max_retries": 2,
            }
        _clients[provider] = OpenAI(**kwargs)
    return _clients[provider]


def _model_for(provider: Provider) -> str:
    return settings.openai_model if provider == "openai" else settings.ollama_model


def _max_tokens_for(provider: Provider) -> int:
    return (
        settings.openai_max_output_tokens
        if provider == "openai"
        else settings.ollama_max_output_tokens
    )


def verify_model(provider: Provider = "openai") -> dict[str, Any]:
    """Confirm the configured model id actually exists on the account/server.

    Called at API startup for both providers so a typo'd *_MODEL fails loudly at
    boot rather than inside a worker ten minutes later.
    """
    model = _model_for(provider)
    retrieved = get_client(provider).models.retrieve(model)
    return {"id": retrieved.id, "owned_by": retrieved.owned_by}


def structured_completion[T: BaseModel](
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
    model_cls: type[T],
    provider: Provider = "openai",
    max_output_tokens: int | None = None,
) -> tuple[T, dict[str, Any]]:
    """One structured-output call. Returns (validated model, raw parsed JSON)."""
    resp = get_client(provider).chat.completions.create(
        model=_model_for(provider),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        max_completion_tokens=max_output_tokens or _max_tokens_for(provider),
    )

    choice = resp.choices[0]
    content = choice.message.content

    if choice.finish_reason == "length":
        raise LLMOutputError(
            "Model hit the output token ceiling before finishing; raise "
            f"{'OPENAI' if provider == 'openai' else 'OLLAMA'}_MAX_OUTPUT_TOKENS.",
            raw=content,
        )
    if not content:
        raise LLMOutputError(
            f"Model returned empty content (finish_reason={choice.finish_reason}).",
            raw=None,
        )

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"Response was not valid JSON: {exc}", raw=content) from exc

    try:
        validated = model_cls.model_validate(parsed)
    except ValidationError as exc:
        raise LLMOutputError(f"Response failed schema validation: {exc}", raw=content) from exc

    return validated, parsed
