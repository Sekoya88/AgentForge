"""Compile optional AFG YAML sources to canonical AgentForge export JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentforge.graph_validate import parse_and_validate_graph


def load_afg_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("AFG YAML root must be a mapping")
    return raw


def compile_afg_yaml_to_export(data: dict[str, Any]) -> dict[str, Any]:
    """
    Build an import-compatible export dict from YAML.

    Required top-level key: graph_definition (mapping).
    Optional: name, description, model_config, skills, execution_policy, version.
    """
    gd = data.get("graph_definition")
    if not isinstance(gd, dict):
        raise ValueError("graph_definition is required and must be a mapping")

    validated = parse_and_validate_graph(gd)
    export: dict[str, Any] = {
        "graph_definition": validated.to_dict(),
    }
    if "name" in data and data["name"] is not None:
        export["name"] = str(data["name"])
    if "description" in data and data["description"] is not None:
        export["description"] = data["description"]
    if "model_config" in data and isinstance(data["model_config"], dict):
        export["model_config"] = dict(data["model_config"])
    if "skills" in data and data["skills"] is not None:
        export["skills"] = list(data["skills"])
    if "execution_policy" in data and isinstance(data["execution_policy"], dict):
        export["execution_policy"] = dict(data["execution_policy"])
    if "version" in data and data["version"] is not None:
        export["version"] = int(data["version"])
    return export
