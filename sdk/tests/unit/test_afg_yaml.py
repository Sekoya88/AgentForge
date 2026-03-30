import pytest
from pathlib import Path
from agentforge.afg_yaml import compile_afg_yaml_to_export, load_afg_yaml


VALID_YAML_CONTENT = """\
name: TestAgent
description: A test agent
model_config:
  provider: ollama
  model: llama3.2
  temperature: 0.7
graph_definition:
  nodes:
    - id: chat
      type: llm
      config:
        system_prompt: "Hello"
  edges:
    - from: chat
      to: END
  entry_point: chat
skills: []
execution_policy:
  max_graph_steps: 5
"""


class TestLoadAfgYaml:
    def test_load_valid_yaml(self, tmp_path):
        p = tmp_path / "agent.afg.yaml"
        p.write_text(VALID_YAML_CONTENT, encoding="utf-8")
        data = load_afg_yaml(p)
        assert data["name"] == "TestAgent"
        assert data["model_config"]["provider"] == "ollama"

    def test_load_invalid_yaml_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("- just a list\n- not a mapping", encoding="utf-8")
        with pytest.raises(ValueError, match="root must be a mapping"):
            load_afg_yaml(p)


class TestCompileAfgYamlToExport:
    def test_valid_compile(self):
        data = {
            "name": "MyAgent",
            "description": "desc",
            "model_config": {"provider": "ollama", "model": "llama3.2", "temperature": 0.7},
            "graph_definition": {
                "nodes": [{"id": "n1", "type": "llm", "config": {}}],
                "entry_point": "n1",
            },
        }
        export = compile_afg_yaml_to_export(data)
        assert export["name"] == "MyAgent"
        assert "graph_definition" in export
        assert export["graph_definition"]["entry_point"] == "n1"

    def test_model_config_preserved(self):
        data = {
            "model_config": {"provider": "ollama", "model": "llama3.2", "temperature": 0.5},
            "graph_definition": {
                "nodes": [{"id": "n1", "config": {}}],
                "entry_point": "n1",
            },
        }
        export = compile_afg_yaml_to_export(data)
        assert export["model_config"]["provider"] == "ollama"

    def test_missing_graph_definition_raises(self):
        with pytest.raises(ValueError, match="graph_definition is required"):
            compile_afg_yaml_to_export({"name": "test"})

    def test_execution_policy_preserved(self):
        data = {
            "graph_definition": {
                "nodes": [{"id": "n1", "config": {}}],
                "entry_point": "n1",
            },
            "execution_policy": {"max_graph_steps": 10},
        }
        export = compile_afg_yaml_to_export(data)
        assert export["execution_policy"]["max_graph_steps"] == 10

    def test_optional_fields_omitted_when_none(self):
        data = {
            "graph_definition": {
                "nodes": [{"id": "n1", "config": {}}],
                "entry_point": "n1",
            },
        }
        export = compile_afg_yaml_to_export(data)
        assert "name" not in export
        assert "description" not in export

    def test_round_trip_from_file(self, tmp_path):
        p = tmp_path / "agent.afg.yaml"
        p.write_text(VALID_YAML_CONTENT, encoding="utf-8")
        raw = load_afg_yaml(p)
        export = compile_afg_yaml_to_export(raw)
        assert export["name"] == "TestAgent"
        assert export["model_config"]["provider"] == "ollama"
        assert export["graph_definition"]["nodes"][0]["id"] == "chat"
