"""Normalize LLM message content (e.g. Gemini block lists) to plain text."""

from __future__ import annotations

from typing import Any


def coerce_message_content_to_str(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
                else:
                    c = block.get("content")
                    if isinstance(c, str):
                        parts.append(c)
                    # else: block has no usable text/content key — intentionally skipped
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)
