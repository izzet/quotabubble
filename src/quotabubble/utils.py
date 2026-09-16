"""General utilities for QuotaBubble."""

from __future__ import annotations


def strip_jsonc_comments(text: str) -> str:
    """Strip single-line (//) and multi-line (/* ... */) comments from JSONC text.

    Correctly ignores comment delimiters within quoted strings and handles
    escaped quotes within strings.
    """
    result: list[str] = []
    in_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
        else:
            if char == '"':
                in_string = True
                result.append(char)
                i += 1
            elif char == "/" and i + 1 < n and text[i + 1] == "/":
                i += 2
                while i < n and text[i] != "\n":
                    i += 1
            elif char == "/" and i + 1 < n and text[i + 1] == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
            else:
                result.append(char)
                i += 1
    return "".join(result)
