"""
Shared Gemini API client for Argus security agents.
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
                "Add it to backend/.env to enable AI agents."
            )

        _client = genai.Client(api_key=api_key)

    return _client


def run_gemini_agent(
    system_instruction,
    prompt,
    model=None
):
    """
    Send a security analysis prompt to Gemini and return parsed JSON.

    The model is instructed to respond with application/json.
    """

    client = get_gemini_client()

    response = client.models.generate_content(
        model=model or GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0
        )
    )

    response_text = response.text or ""

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {"raw_output": response_text}
