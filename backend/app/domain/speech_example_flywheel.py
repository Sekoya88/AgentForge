"""Helpers for optional speech-example collection (ASR training flywheel)."""

from __future__ import annotations

from app.domain.graph_definition import GraphDefinitionValidated
from app.domain.value_objects import MessageDict

SPEECH_EXAMPLE_FEEDBACK_MIN_SCORE = 0.8


def graph_has_asr_node(graph: GraphDefinitionValidated) -> bool:
    return any(n.type == "asr" for n in graph.nodes)


def transcription_from_output_messages(messages: list[MessageDict] | None) -> str:
    if not messages:
        return ""
    parts: list[str] = []
    for m in messages:
        c = m.content
        if isinstance(c, str) and c.strip():
            parts.append(c.strip())
    return "\n".join(parts)
