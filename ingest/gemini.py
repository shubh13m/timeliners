"""Gemini API wrapper with retry, circuit breaker, rate-limit guard, and audit logging."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Type, TypeVar

import google.generativeai as genai
import structlog
from pydantic import BaseModel, ValidationError

from .config import (
    GEMINI_MAX_CONSECUTIVE_FAILURES,
    GEMINI_MIN_INTERVAL_S,
    Settings,
)
from .db import get_client

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class CircuitBreakerOpen(RuntimeError):
    """Raised when too many consecutive Gemini calls have failed."""


class GeminiClient:
    def __init__(self, settings: Settings):
        genai.configure(api_key=settings.gemini_api_key)
        self._model_name = settings.gemini_model
        self._last_call_ts: float = 0.0
        self._consecutive_failures: int = 0

    def _sleep_if_needed(self) -> None:
        elapsed = time.monotonic() - self._last_call_ts
        wait = GEMINI_MIN_INTERVAL_S - elapsed
        if wait > 0:
            time.sleep(wait)

    def _log_run(self, phase: str, prompt: str, response_text: str | None, status: str, error: str | None) -> None:
        try:
            get_client().table("ai_runs").insert(
                {
                    "phase": phase,
                    "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "prompt_tokens": len(prompt) // 4,  # rough
                    "response_tokens": (len(response_text) // 4) if response_text else 0,
                    "response": json.loads(response_text) if response_text else None,
                    "status": status,
                    "error": error,
                }
            ).execute()
        except Exception as e:  # never let logging break the pipeline
            log.warning("ai_run_log_failed", error=str(e))

    def generate_json(
        self,
        prompt: str,
        schema: Type[T],
        phase: str,
        max_retries: int = 1,
    ) -> T:
        """Call Gemini with JSON mode and validate against a Pydantic schema."""
        if self._consecutive_failures >= GEMINI_MAX_CONSECUTIVE_FAILURES:
            raise CircuitBreakerOpen(
                f"Aborting: {self._consecutive_failures} consecutive Gemini failures."
            )

        model = genai.GenerativeModel(
            self._model_name,
            generation_config={"response_mime_type": "application/json"},
        )

        attempt = 0
        last_error: str | None = None
        response_text: str | None = None

        while attempt <= max_retries:
            self._sleep_if_needed()
            self._last_call_ts = time.monotonic()

            effective_prompt = prompt
            if attempt > 0:
                effective_prompt = (
                    prompt
                    + "\n\nIMPORTANT: Previous response failed validation. "
                    "Return ONLY valid JSON matching the schema exactly. No prose."
                )

            try:
                resp = model.generate_content(effective_prompt)
                response_text = resp.text or ""
                data = json.loads(response_text)
                validated = schema.model_validate(data)
                self._log_run(phase, effective_prompt, response_text, "ok", None)
                self._consecutive_failures = 0
                return validated
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = f"{type(e).__name__}: {e}"
                log.warning("gemini_invalid_response", phase=phase, attempt=attempt, error=last_error)
                attempt += 1
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                log.error("gemini_call_failed", phase=phase, error=last_error)
                self._consecutive_failures += 1
                self._log_run(phase, effective_prompt, response_text, "error", last_error)
                raise

        # Exhausted retries.
        self._consecutive_failures += 1
        self._log_run(phase, prompt, response_text, "invalid_json", last_error)
        raise ValueError(f"Gemini returned invalid JSON after {max_retries + 1} attempts: {last_error}")
