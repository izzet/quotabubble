"""General utilities for QuotaBubble."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_REDACTED = "[REDACTED]"

# Each pair is (pattern, replacement); replacements keep any prefix group (e.g. the
# header name) via \1 and drop the captured secret, or replace the whole match when
# the match *is* the secret (a bare token, key, or email address).
_REDACTION_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(authorization[\"']?\s*[:=]\s*[\"']?)(\S+(?:\s+\S+)?)", re.IGNORECASE),
        r"\1" + _REDACTED,
    ),
    (re.compile(r"\b(bearer\s+)(\S+)", re.IGNORECASE), r"\1" + _REDACTED),
    (
        re.compile(r"(set-cookie[\"']?\s*[:=]\s*[\"']?)(\S+)", re.IGNORECASE),
        r"\1" + _REDACTED,
    ),
    (re.compile(r"\b(cookie[\"']?\s*[:=]\s*[\"']?)(\S+)", re.IGNORECASE), r"\1" + _REDACTED),
    (
        re.compile(r"(api[_-]?key[\"']?\s*[:=]\s*[\"']?)(\S+)", re.IGNORECASE),
        r"\1" + _REDACTED,
    ),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), _REDACTED),
    (re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9]{16,}\b"), _REDACTED),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b"), _REDACTED),
]


def redact_secrets(text: str) -> str:
    """Replace tokens, keys, cookies, auth headers, and email addresses with [REDACTED]."""
    for pattern, replacement in _REDACTION_RULES:
        text = pattern.sub(replacement, text)
    return text


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text to path so a crash or concurrent write cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


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
