"""Shared helpers for parsing structured output from LLM responses."""

import re


def extract_json(text: str) -> str:
    """Extract a JSON object string from markdown fences or free-form model output."""
    if not text:
        return "{}"
    text = text.strip()
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()
    start = text.find("{")
    if start == -1:
        return "{}"
    extracted = text[start:]
    bracket_count = 0
    end_index = -1
    in_string = False
    escape = False
    for i, char in enumerate(extracted):
        if char == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if char == "{":
                bracket_count += 1
            elif char == "}":
                bracket_count -= 1
                if bracket_count == 0:
                    end_index = i + 1
                    break
        escape = char == "\\" and not escape
        if char != "\\":
            escape = False
    if end_index != -1:
        return extracted[:end_index]
    if extracted.count('"') % 2 != 0:
        extracted += '"'
    open_braces = extracted.count("{")
    close_braces = extracted.count("}")
    if open_braces > close_braces:
        extracted += "}" * (open_braces - close_braces)
    return extracted
