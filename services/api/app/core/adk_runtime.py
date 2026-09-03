"""Thin execution layer over the Google ADK.

Every crew member is an ADK `LlmAgent` carrying an `output_schema`, so each one
returns a validated Pydantic model rather than prose. That constraint is what
lets a seven stage pipeline be deterministic: stage N+1 receives a typed object,
never a paragraph it has to re-interpret.

The ADK forbids combining `output_schema` with tool use, so all deterministic
work (screenplay parsing, Parallel search fan-out, stripboard optimisation)
happens in the orchestrator between stages and is handed to the next agent as
structured context.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import TypeVar

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

log = logging.getLogger(__name__)

APP_NAME = "firstad"

T = TypeVar("T", bound=BaseModel)

_session_service = InMemorySessionService()

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class AgentExecutionError(RuntimeError):
    """Raised when a crew member cannot produce a valid typed result."""


def _extract_json(text: str) -> str:
    """Pull the JSON body out of a model response.

    `output_schema` normally guarantees clean JSON, but a fenced block still
    shows up occasionally when a stage is retried with a repair prompt.
    """
    stripped = text.strip()
    fenced = _FENCE_RE.search(stripped)
    if fenced:
        return fenced.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


_RATE_LIMIT_MARKERS = (
    "429",
    "resource_exhausted",
    "resourceexhausted",
    "quota",
    "rate limit",
    "too many requests",
)


def _is_rate_limited(exc: BaseException) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(marker in blob for marker in _RATE_LIMIT_MARKERS)


@lru_cache
def _gate() -> asyncio.Semaphore:
    """Cap how many agents may be talking to Gemini at once.

    The free tier limits requests per minute, not only per day, so a pipeline
    that fans out as wide as the work allows will trip it on a long script.
    Serialising a little costs a few seconds and turns a failed run into a
    slower one.
    """
    return asyncio.Semaphore(get_settings().max_agent_concurrency)


async def run_agent(
    agent: LlmAgent,
    prompt: str,
    schema: type[T],
    *,
    run_id: str,
    attempts: int | None = None,
) -> T:
    """Execute one crew member and return its validated output.

    Retries cover two different failures: a response that will not validate
    against the schema, and a rate limit. The first is retried with a repair
    prompt, the second with exponential backoff and no prompt change.
    """
    if attempts is None:
        attempts = get_settings().agent_retry_attempts

    last_error: str = ""
    backoff = 4.0

    for attempt in range(1, attempts + 1):
        session_id = f"{run_id}:{agent.name}:{attempt}"
        await _session_service.create_session(
            app_name=APP_NAME, user_id=run_id, session_id=session_id
        )

        runner = Runner(app_name=APP_NAME, agent=agent, session_service=_session_service)

        message = prompt
        if last_error:
            message = (
                f"{prompt}\n\n"
                f"Your previous response could not be parsed against the required schema. "
                f"The error was: {last_error}\n"
                f"Return only valid JSON matching the schema, with no commentary."
            )

        final_text = ""
        try:
            async with _gate():
                async for event in runner.run_async(
                    user_id=run_id,
                    session_id=session_id,
                    new_message=types.Content(role="user", parts=[types.Part(text=message)]),
                ):
                    if event.is_final_response() and event.content and event.content.parts:
                        final_text = "".join(p.text or "" for p in event.content.parts)
        except Exception as exc:  # noqa: BLE001 - retried or re-raised below
            if _is_rate_limited(exc) and attempt < attempts:
                log.warning(
                    "%s hit a rate limit, waiting %.0fs before retry %s/%s",
                    agent.name,
                    backoff,
                    attempt + 1,
                    attempts,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                # Not a schema failure, so the prompt is left untouched.
                continue
            raise AgentExecutionError(f"{agent.name} failed: {type(exc).__name__}: {exc}") from exc

        if not final_text.strip():
            last_error = "empty response"
            log.warning("%s returned nothing on attempt %s", agent.name, attempt)
            continue

        try:
            payload = json.loads(_extract_json(final_text))
        except json.JSONDecodeError as exc:
            last_error = f"invalid JSON: {exc}"
            log.warning("%s produced unparseable JSON on attempt %s", agent.name, attempt)
            continue

        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            last_error = str(exc)[:600]
            log.warning("%s failed schema validation on attempt %s", agent.name, attempt)
            continue

    raise AgentExecutionError(f"{agent.name} failed after {attempts} attempts: {last_error}")
