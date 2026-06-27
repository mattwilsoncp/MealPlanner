"""Robust JSON extraction from chat-completion model responses.

Smaller instruction-tuned models (Gemma, etc.) often ignore the
"return only JSON" instruction and reply with prose around the JSON
output, sometimes stuffed between two valid JSON fragments. Naive
``json.loads`` raises ``JSONDecodeError: Extra data: ...`` on the
trailing text. This helper walks the response, peeks for the first
valid JSON value matching the caller's expected type, and returns
it. Markdown code fences and leading/trailing whitespace are stripped
best-effort.
"""
from __future__ import annotations

import json


_OPENER_CONNECTORS = " \t\r\n,"


def extract_json_payload(raw_text, expected_type):
    """Return the first JSON value of *expected_type* from *raw_text*.

    ``expected_type`` must be ``dict`` or ``list``. When the caller asks
    for ``list`` and the model returned a single top-level object, the
    helper wraps it as a one-element list so downstream code can
    iterate uniformly.

    Raises ``RuntimeError`` with a short preview of the input if no
    matching JSON value is found.
    """
    if expected_type not in (dict, list):
        raise ValueError("expected_type must be dict or list")

    text = (raw_text or "").strip()
    if not text:
        raise RuntimeError("AI response was empty.")

    text = _strip_markdown_fences(text)

    decoder = json.JSONDecoder()
    cursor = 0
    while cursor < len(text):
        # Skip whitespace and stray commas between candidate values so we
        # can move cleanly past fragments like '},{' or a closing ']'
        # followed by prose.
        while cursor < len(text) and text[cursor] in _OPENER_CONNECTORS:
            cursor += 1
        if cursor >= len(text):
            break
        try:
            payload, end = decoder.raw_decode(text, cursor)
        except json.JSONDecodeError:
            # Position *cursor* cannot begin a JSON value. Move one
            # character forward and try again — this lets us skip past
            # prose like "Here is the recipe:" until we land on a '['
            # or '{'.
            cursor += 1
            continue

        shaped = _shape(payload, expected_type)
        if shaped is not None:
            return shaped

        # The parse succeeded but the value is the wrong shape. Skip
        # past its end so we don't drill into nested structures
        # (e.g. an inner dict inside an array when caller wanted dict).
        cursor = end

    raise RuntimeError(
        "AI response did not contain a JSON object or array. "
        f"Starts with: {text[:120]!r}"
    )


def _strip_markdown_fences(text):
    """Remove a leading and trailing ```` ``` ```` fence if present."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _shape(payload, expected_type):
    """Return *payload* reshaped for the caller, or ``None`` if *payload*
    doesn't match the expected JSON type."""
    if expected_type is dict:
        if isinstance(payload, dict):
            return payload
        return None
    # expected_type is list — wrap a singleton dict so iteration is uniform.
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    return None
