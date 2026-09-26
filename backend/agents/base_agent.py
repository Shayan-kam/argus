"""
Base class for all Argus security agents.

Agents use the Gemini API for LLM-powered analysis.
"""

import time

from findings import normalize_finding, deduplicate_findings
from gemini_base import run_gemini_agent


class BaseSecurityAgent:
    name = "Base Security Agent"
    vulnerability_type = "Security Vulnerability"

    # Used by the routing system.
    trigger_signals = []

    system_instructions = """
    Analyze the provided source code for security vulnerabilities.
    Only report vulnerabilities supported by concrete evidence.
    """

    def add_line_numbers(self, content):
        """
        Add line numbers so the model can report accurate locations.
        """

        lines = content.splitlines()
        numbered_lines = []

        for line_number, line in enumerate(lines, start=1):
            numbered_lines.append(
                f"{line_number:04d}: {line}"
            )

        return "\n".join(numbered_lines)

    def build_prompt(self, source_files):
        """
        Build a prompt using only files selected for this agent.
        """

        source_code = ""

        for source_file in source_files:
            numbered_content = self.add_line_numbers(
                source_file["content"]
            )

            source_code += (
                "\n\n"
                f"===== FILE: {source_file['file']} =====\n"
                f"{numbered_content}\n"
            )

        prompt = f"""
You are the {self.name}.

Your assigned vulnerability category is:

{self.vulnerability_type}

Your instructions:

{self.system_instructions}

Analyze only the assigned vulnerability category.

The following files were selected because static preprocessing
identified signals potentially related to your category:

{source_code}

Return ONLY valid JSON using exactly this structure:

{{
  "findings": [
    {{
      "title": "Short vulnerability title",
      "vulnerability_type": "{self.vulnerability_type}",
      "severity": "High",
      "confidence": 0.95,
      "file": "relative/path/to/file.py",
      "line": 12,
      "evidence": "Short redacted code excerpt",
      "description": "Explain the vulnerability and relevant data flow.",
      "recommendation": "Explain how to fix the vulnerability.",
      "source": "ai"
    }}
  ]
}}

If no vulnerability is found, return:

{{
  "findings": []
}}

Important requirements:

- Report only vulnerabilities in your assigned category.
- Do not invent files, lines, or code.
- Use exact relative paths from the supplied source.
- Use accurate line numbers from the numbered source.
- Never reproduce complete secrets or credentials.
- The source field MUST be exactly one of:
  "ai", "rule-based", or "hybrid".
- Never use "Agentic AI", "LLM", or other source values.
- Return JSON only.
- Do not use Markdown code fences.
"""

        return prompt

    def call_gemini(self, prompt):
        """
        Send the analysis prompt to Gemini and return the raw response.
        """

        return run_gemini_agent(
            system_instruction=self.system_instructions,
            prompt=prompt
        )

    def parse_response(self, response_data):
        if isinstance(response_data, dict) and "raw_output" in response_data:
            print(
                f"{self.name} returned non-JSON output."
            )
            print(response_data["raw_output"])
            return []

        if isinstance(response_data, list):
            raw_findings = response_data

        elif isinstance(response_data, dict):
            raw_findings = response_data.get(
                "findings",
                []
            )

        else:
            print(
                f"{self.name} returned unexpected response type: "
                f"{type(response_data).__name__}"
            )
            return []

        findings = []

        for raw_finding in raw_findings:
            if not isinstance(raw_finding, dict):
                continue

            try:
                finding = normalize_finding(raw_finding)
                findings.append(finding)

            except Exception as error:
                print(
                    f"Could not normalize finding from "
                    f"{self.name}: {error}"
                )

        return deduplicate_findings(findings)

    def analyze(self, source_files):
        """
        Analyze only the focused source files selected by the router.
        """

        if not source_files:
            print(
                f"{self.name}: no relevant source files. Skipping."
            )
            return [], 0.0

        start_time = time.perf_counter()

        prompt = self.build_prompt(source_files)

        print(
            f"Sending focused source code to {self.name} (Gemini)..."
        )

        response_data = self.call_gemini(prompt)

        print(
            f"Received response from {self.name}."
        )

        findings = self.parse_response(response_data)

        elapsed_seconds = time.perf_counter() - start_time

        print(
            f"{self.name} returned {len(findings)} finding(s) "
            f"in {elapsed_seconds:.2f} seconds."
        )

        return findings, elapsed_seconds
