"""
Shared Gemini API client for Argus security agents.

Handles transient API failures (503, 429, etc.) with exponential
backoff and optional fallback to an alternate model.
"""

import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Load root .env first, then backend/.env so local overrides work.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = os.getenv(
    "GEMINI_FALLBACK_MODEL",
    "gemini-2.5-flash"
)
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "4"))
GEMINI_RETRY_BASE_DELAY = float(
    os.getenv("GEMINI_RETRY_BASE_DELAY", "2")
)

RETRYABLE_STATUS_CODES = {
    429,  # rate limited
    500,
    502,
    503,
    504,
}

_client = None


def get_gemini_client():
    """
    Lazily initialize the Gemini client so import does not fail
    when GEMINI_API_KEY is unset (e.g. during quick scans).
    """

    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Add it to .env at the project root to enable AI agents."
            )

        _client = genai.Client(api_key=api_key)

    return _client


def get_error_status_code(error):
    """
    Extract an HTTP status code from a Gemini API error, if present.
    """

    if isinstance(error, genai_errors.APIError):
        return getattr(error, "code", None)

    message = str(error)

    for code in RETRYABLE_STATUS_CODES | {404}:
        if str(code) in message:
            return code

    if "UNAVAILABLE" in message or "RESOURCE_EXHAUSTED" in message:
        return 503

    if "NOT_FOUND" in message:
        return 404

    return None


def is_model_not_found_error(error):
    """
    Return True when the requested model name is invalid or retired.
    """

    status_code = get_error_status_code(error)

    if status_code == 404:
        return True

    message = str(error).lower()

    return (
        "not_found" in message
        and "model" in message
    )


def is_retryable_error(error):
    """
    Return True when the error is likely transient.
    """

    status_code = get_error_status_code(error)

    return status_code in RETRYABLE_STATUS_CODES


def retry_delay_seconds(attempt):
    """
    Exponential backoff with jitter.
    """

    base = GEMINI_RETRY_BASE_DELAY * (2 ** attempt)
    jitter = random.uniform(0, 1)

    return base + jitter


def models_to_attempt(requested_model):
    """
    Build an ordered list of models to try, primary then fallback.
    """

    primary = requested_model or GEMINI_MODEL
    models = [primary]

    fallback = GEMINI_FALLBACK_MODEL

    if fallback and fallback not in models:
        models.append(fallback)

    return models


def generate_with_model(client, model, system_instruction, prompt):
    """
    Make a single Gemini generate_content call.
    """

    response = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0
        )
    )

    return response.text or ""


def run_gemini_agent(
    system_instruction,
    prompt,
    model=None
):
    """
    Send a security analysis prompt to Gemini and return parsed JSON.

    Retries transient failures and falls back to GEMINI_FALLBACK_MODEL
    when the primary model is unavailable.
    """

    client = get_gemini_client()
    last_error = None
    models = models_to_attempt(model)

    for model_index, model_name in enumerate(models):
        for attempt in range(GEMINI_MAX_RETRIES):
            try:
                response_text = generate_with_model(
                    client,
                    model_name,
                    system_instruction,
                    prompt
                )

                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    return {"raw_output": response_text}

            except Exception as error:
                last_error = error

                if is_model_not_found_error(error):
                    print(
                        f"Gemini model {model_name} is unavailable "
                        f"(404). Trying next model..."
                    )
                    break

                if not is_retryable_error(error):
                    raise

                if attempt >= GEMINI_MAX_RETRIES - 1:
                    print(
                        f"Gemini model {model_name} failed after "
                        f"{GEMINI_MAX_RETRIES} attempts: {error}"
                    )
                    break

                delay = retry_delay_seconds(attempt)
                status_code = get_error_status_code(error)

                print(
                    f"Gemini {model_name} unavailable "
                    f"(HTTP {status_code}). "
                    f"Retry {attempt + 1}/{GEMINI_MAX_RETRIES} "
                    f"in {delay:.1f}s..."
                )

                time.sleep(delay)

        else:
            # Inner loop completed without break — success path returns above.
            continue

        # If this was the last model, stop trying.
        if model_index >= len(models) - 1:
            break

    if last_error is not None:
        raise last_error

    raise RuntimeError("Gemini request failed with no error details.")
