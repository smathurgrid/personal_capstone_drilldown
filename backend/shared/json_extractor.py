"""Shared helpers for parsing structured output from LLM responses."""

import re


def extract_json(text: str, expect: str = "object") -> str:
    """Extract a JSON string from markdown fences or free-form model output.

    expect="object" balances braces ({}); expect="array" balances brackets ([]).
    """
    open_char, close_char, empty = ("[", "]", "[]") if expect == "array" else ("{", "}", "{}")
    if not text:
        return empty
    text = text.strip()
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1).strip()
    start = text.find(open_char)
    if start == -1:
        return empty
    extracted = text[start:]
    bracket_count = 0
    end_index = -1
    in_string = False
    escape = False
    for i, char in enumerate(extracted):
        if char == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if char == open_char:
                bracket_count += 1
            elif char == close_char:
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
    open_n = extracted.count(open_char)
    close_n = extracted.count(close_char)
    if open_n > close_n:
        extracted += close_char * (open_n - close_n)
    return extracted
