import pytest
from pydantic import ValidationError
from agentforge.types import (
    AgentModelConfig,
    NodeConfig,
    EdgeConfig,
    GraphDefinition,
    PolicyConfig,
    SkillSpec,
    AgentDefinition,
)


class TestAgentModelConfig:
    def test_defaults(self):
        cfg = AgentModelConfig()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.7
        assert cfg.base_url is None
        assert cfg.options == {}

    def test_ollama_config(self):
        cfg = AgentModelConfig(
            provider="ollama",
            model="llama3.2",
            base_url="http://localhost:11434",
            options={"num_ctx": 4096},
        )
        assert cfg.provider == "ollama"
        assert cfg.base_url == "http://localhost:11434"
        assert cfg.options["num_ctx"] == 4096

    def test_options_defaults_to_empty_dict(self):
        cfg = AgentModelConfig(provider="openai", model="gpt-4o", temperature=0.5)
        assert cfg.options == {}

    def test_temperature_range(self):
        cfg = AgentModelConfig(temperature=0.0)
        assert cfg.temperature == 0.0
        cfg2 = AgentModelConfig(temperature=2.0)
        assert cfg2.temperature == 2.0


class TestNodeConfig:
    def test_valid_node(self):
        n = NodeConfig(id="step1", type="llm", config={"system_prompt": "hello"})
        assert n.id == "step1"
        assert n.type == "llm"

    def test_id_min_length(self):
        with pytest.raises(ValidationError):
            NodeConfig(id="", type="llm", config={})

    def test_id_max_length(self):
        with pytest.raises(ValidationError):
            NodeConfig(id="x" * 129, type="llm", config={})

    def test_default_type(self):
        n = NodeConfig(id="n1", config={})
        assert n.type == "llm"

    def test_custom_type_allowed(self):
        n = NodeConfig(id="n1", type="my_custom_node", config={})
        assert n.type == "my_custom_node"


class TestEdgeConfig:
    def test_from_alias(self):
        e = EdgeConfig(**{"from": "a", "to": "b"})
        assert e.from_ == "a"
        assert e.to == "b"

    def test_from_field_name(self):
        e = EdgeConfig(from_="a", to="b")
        assert e.from_ == "a"

    def test_condition_type_default(self):
        e = EdgeConfig(from_="a", to="b")
        assert e.condition_type == "always"

    def test_invalid_condition_type(self):
        with pytest.raises(ValidationError):
            EdgeConfig(**{"from": "a", "to": "b", "condition_type": "unknown"})


class TestPolicyConfig:
    def test_defaults(self):
        p = PolicyConfig()
        assert p.allowed_tools is None
        assert p.denied_tools == []
        assert p.max_cost_usd is None
        assert p.max_graph_steps is None

    def test_set_values(self):
        p = PolicyConfig(max_cost_usd=0.5, max_graph_steps=10, denied_tools=["exec"])
        assert p.max_cost_usd == 0.5
        assert p.max_graph_steps == 10
        assert "exec" in p.denied_tools


class TestSkillSpec:
    def test_instruction_skill(self):
        s = SkillSpec(name="summarizer", skill_type="instruction", instructions="Summarize text")
        assert s.skill_type == "instruction"
        assert s.source_code is None

    def test_code_skill(self):
        s = SkillSpec(name="calc", skill_type="code", source_code="def run(x): return x")
        assert s.skill_type == "code"

    def test_invalid_skill_type(self):
        with pytest.raises(ValidationError):
            SkillSpec(name="bad", skill_type="unknown")


class TestAgentDefinition:
    def test_model_config_alias(self):
        from agentforge.types import GraphDefinition
        gd = GraphDefinition(
            nodes=[NodeConfig(id="n1", type="llm", config={})],
            edges=[],
            entry_point="n1",
        )
        ad = AgentDefinition(
            name="test",
            graph_definition=gd,
            model_config=AgentModelConfig(),
        )
        dumped = ad.model_dump(by_alias=True)
        assert "model_config" in dumped
