import os
import json
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def run_gemini_agent(system_instruction: str, code_content: str, model: str = "gemini-2.5-flash") -> dict:
    prompt = f"Analyze the following code:\n\n```\n{code_content}\n```"
    response = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json"
        )
    )
    try:
        return json.loads(response.text)
    except Exception:
        return {"raw_output": response.text}