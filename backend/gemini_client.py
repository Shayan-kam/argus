"""
Gemini API client for Argus agents.

This is the only place that talks to Google. Agents just send a prompt
and receive JSON text, the same way they would with any chat API.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


LOGGER = logging.getLogger("argus.gemini")

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env", override=False)

DEFAULT_MODELS = [
    os.getenv("GEMINI_MODEL", "").strip(),
    "gemini-2.5-flash",
]


def _model_candidates():
    seen = set()
    ordered = []

    for model_name in DEFAULT_MODELS:
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        ordered.append(model_name)

    return ordered


def get_api_key():
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()


@lru_cache(maxsize=1)
def get_client():
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Put it in Argus/backend/.env"
        )

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=120_000,
            retry_options=types.HttpRetryOptions(
                attempts=2,
                initial_delay=1.0,
                max_delay=4.0,
                exp_base=2.0,
                jitter=0.2,
                http_status_codes=[429, 500, 502, 503, 504],
            ),
        ),
    )


def generate_json(prompt: str) -> str:
    """
    Call Gemini and return raw JSON text.
    """

    client = get_client()
    last_error = None

    for model_name in _model_candidates():
        LOGGER.info("Calling Gemini model %s", model_name)

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
        except Exception as error:
            last_error = error
            LOGGER.warning(
                "Gemini model %s failed: %s",
                model_name,
                error,
            )

            if "RESOURCE_EXHAUSTED" in str(error) or "429" in str(error):
                raise RuntimeError(
                    f"Gemini quota or rate limit reached for {model_name}: "
                    f"{error}"
                ) from error

            continue

        text = (getattr(response, "text", None) or "").strip()

        if text:
            LOGGER.info(
                "Gemini model %s returned %s characters",
                model_name,
                len(text),
            )
            return text

        last_error = RuntimeError(
            f"Gemini model {model_name} returned an empty response"
        )
        LOGGER.warning(str(last_error))

    raise RuntimeError(
        f"All Gemini model attempts failed. Last error: {last_error}"
    )
