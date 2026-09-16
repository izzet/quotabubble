from __future__ import annotations

import json

from quotabubble.utils import strip_jsonc_comments


def test_strip_jsonc_comments_preserves_strings() -> None:
    text = """
    // Leading comment
    {
      /* block comment */
      "url": "https://opencode.ai/config.json", // inline comment
      "key": "val/*not a comment*/ue"
    }
    /* Trailing block comment */
    """
    cleaned = strip_jsonc_comments(text)
    data = json.loads(cleaned)
    assert data["url"] == "https://opencode.ai/config.json"
    assert data["key"] == "val/*not a comment*/ue"


def test_strip_jsonc_comments_escaped_quotes() -> None:
    text = '{"message": "Hello \\"//not a comment\\" world"}'
    cleaned = strip_jsonc_comments(text)
    data = json.loads(cleaned)
    assert data["message"] == 'Hello "//not a comment" world'


def test_strip_jsonc_comments_empty_and_no_comments() -> None:
    assert strip_jsonc_comments("") == ""
    assert strip_jsonc_comments('{"a": 1}') == '{"a": 1}'
