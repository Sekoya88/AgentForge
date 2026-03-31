import json
import pytest
from agentforge.builder import Agent, AgentBuilder, AgentPolicy
from agentforge.types import AgentDefinition, PolicyConfig


class TestAgentBuilderModel:
    def test_default_model(self):
        agent = Agent("test").llm_node("n1").build()
        assert agent.llm_model_config.provider == "openai"
        assert agent.llm_model_config.model == "gpt-4o"

    def test_ollama_model(self):
        agent = (
            Agent("test")
            .model("ollama", "llama3.2", base_url="http://localhost:11434")
            .llm_node("n1")
            .build()
        )
        assert agent.llm_model_config.provider == "ollama"
        assert agent.llm_model_config.model == "llama3.2"
        assert agent.llm_model_config.base_url == "http://localhost:11434"

    def test_ollama_model_with_options(self):
        agent = (
            Agent("test")
            .model("ollama", "llama3.2", options={"num_ctx": 8192})
            .llm_node("n1")
            .build()
        )
        assert agent.llm_model_config.options["num_ctx"] == 8192

    def test_model_chainable(self):
        builder = Agent("test").model("ollama", "llama3.2")
        assert isinstance(builder, AgentBuilder)


class TestAgentBuilderNodes:
    def test_llm_node(self):
        agent = Agent("test").llm_node("chat", system_prompt="Be helpful").build()
        assert len(agent.graph_definition.nodes) == 1
        node = agent.graph_definition.nodes[0]
        assert node.id == "chat"
        assert node.type == "llm"
        assert node.config["system_prompt"] == "Be helpful"

    def test_tool_node(self):
        agent = Agent("test").tool_node("search", tool_name="web_search").build()
        node = agent.graph_definition.nodes[0]
        assert node.type == "tool"
        assert node.config["tool_name"] == "web_search"

    def test_subagent_node(self):
        agent = Agent("test").subagent_node("delegate", agent_id="uuid-123").build()
        node = agent.graph_definition.nodes[0]
        assert node.type == "subagent"
        assert node.config["agent_id"] == "uuid-123"

    def test_custom_node(self):
        agent = Agent("test").custom_node("step1", "my_type", {"key": "val"}).build()
        node = agent.graph_definition.nodes[0]
        assert node.type == "my_type"
        assert node.config["key"] == "val"

    def test_first_node_becomes_entry_point(self):
        agent = (
            Agent("test")
            .llm_node("first")
            .tool_node("second", tool_name="search")
            .build()
        )
        assert agent.graph_definition.entry_point == "first"

    def test_multiple_nodes(self):
        agent = (
            Agent("test")
            .llm_node("n1")
            .tool_node("n2", tool_name="t")
            .llm_node("n3")
            .build()
        )
        assert len(agent.graph_definition.nodes) == 3

    def test_asr_finetuned_whisper_config(self):
        agent = (
            Agent("voice")
            .asr_node(
                "listen",
                provider="finetuned_whisper",
                endpoint_url="https://example.modal.run/transcribe",
                job_id="550e8400-e29b-41d4-a716-446655440000",
                headers={"Authorization": "Bearer x"},
            )
            .build()
        )
        node = agent.graph_definition.nodes[0]
        assert node.type == "asr"
        assert node.config["provider"] == "finetuned_whisper"
        assert node.config["endpoint_url"] == "https://example.modal.run/transcribe"
        assert node.config["finetune_job_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert node.config["headers"]["Authorization"] == "Bearer x"

    def test_tts_finetuned_config(self):
        agent = (
            Agent("voice")
            .tts_node(
                "speak",
                provider="finetuned_tts",
                voice="nova",
                voice_id="deployed-voice-1",
                endpoint_url="https://example.modal.run/synth",
            )
            .build()
        )
        node = agent.graph_definition.nodes[0]
        assert node.type == "tts"
        assert node.config["provider"] == "finetuned_tts"
        assert node.config["voice_id"] == "deployed-voice-1"
        assert node.config["endpoint_url"] == "https://example.modal.run/synth"


class TestAgentBuilderEdges:
    def test_simple_edge(self):
        agent = (
            Agent("test")
            .llm_node("a")
            .llm_node("b")
            .edge("a", "b")
            .build()
        )
        assert len(agent.graph_definition.edges) == 1
        edge = agent.graph_definition.edges[0]
        assert edge.from_ == "a"
        assert edge.to == "b"

    def test_conditional_edge(self):
        agent = (
            Agent("test")
            .llm_node("a")
            .llm_node("b")
            .edge("a", "b", condition="yes", condition_type="contains")
            .build()
        )
        edge = agent.graph_definition.edges[0]
        assert edge.condition == "yes"
        assert edge.condition_type == "contains"

    def test_parallel_nodes(self):
        agent = (
            Agent("test")
            .llm_node("a")
            .llm_node("b")
            .parallel_nodes("a", "b")
            .build()
        )
        assert "a" in agent.graph_definition.parallel_nodes
        assert "b" in agent.graph_definition.parallel_nodes


class TestAgentBuilderSkills:
    def test_add_skill_instruction(self):
        agent = (
            Agent("test")
            .llm_node("n1")
            .skill("summarizer", skill_type="instruction", instructions="Summarize")
            .build()
        )
        assert len(agent.skills) == 1
        assert agent.skills[0].name == "summarizer"
        assert agent.skills[0].skill_type == "instruction"

    def test_add_skill_code(self):
        agent = (
            Agent("test")
            .llm_node("n1")
            .skill("calc", skill_type="code", source_code="def run(x): return x")
            .build()
        )
        assert agent.skills[0].skill_type == "code"


class TestAgentBuilderExportJson:
    def test_export_json_round_trip(self, tmp_path):
        filepath = str(tmp_path / "agent.json")
        (
            Agent("MyBot")
            .model("ollama", "llama3.2")
            .llm_node("chat", system_prompt="Hello")
            .build_and_export(filepath)
        )
        with open(filepath) as f:
            data = json.load(f)
        assert data["name"] == "MyBot"
        assert data["model_config"]["provider"] == "ollama"
        assert data["graph_definition"]["nodes"][0]["id"] == "chat"

    def test_build_returns_agent_definition(self):
        result = Agent("test").llm_node("n").build()
        assert isinstance(result, AgentDefinition)
