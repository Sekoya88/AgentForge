"""Tests for ASR/TTS node builder methods."""

from agentforge.builder import AgentBuilder


def test_asr_node_adds_correct_type():
    agent = (
        AgentBuilder("VoiceAgent")
        .asr_node("transcribe", provider="openai_whisper", language="fr")
        .build()
    )
    nodes = agent.graph_definition.nodes
    assert len(nodes) == 1
    assert nodes[0].type == "asr"
    assert nodes[0].config["provider"] == "openai_whisper"
    assert nodes[0].config["language"] == "fr"


def test_tts_node_adds_correct_type():
    agent = (
        AgentBuilder("VoiceAgent")
        .tts_node("speak", provider="openai_tts", voice="shimmer")
        .build()
    )
    nodes = agent.graph_definition.nodes
    assert nodes[0].type == "tts"
    assert nodes[0].config["voice"] == "shimmer"


def test_asr_node_sets_entry_point():
    agent = (
        AgentBuilder("VoiceAgent")
        .asr_node("transcribe")
        .llm_node("reason")
        .edge("transcribe", "reason")
        .build()
    )
    assert agent.graph_definition.entry_point == "transcribe"


def test_tts_node_defaults():
    agent = AgentBuilder("V").tts_node("speak").build()
    cfg = agent.graph_definition.nodes[0].config
    assert cfg.get("provider") == "openai_tts"
    assert cfg.get("voice") == "nova"


def test_asr_node_defaults():
    agent = AgentBuilder("V").asr_node("transcribe").build()
    cfg = agent.graph_definition.nodes[0].config
    assert cfg.get("provider") == "openai_whisper"


def test_full_voice_pipeline_graph():
    agent = (
        AgentBuilder("VoiceAssistant")
        .model("openai", "gpt-4o")
        .asr_node("transcribe", provider="openai_whisper", language="fr")
        .llm_node("reason", system_prompt="Tu es un assistant vocal.")
        .tts_node("speak", provider="openai_tts", voice="nova")
        .edge("transcribe", "reason")
        .edge("reason", "speak")
        .build()
    )
    assert len(agent.graph_definition.nodes) == 3
    assert len(agent.graph_definition.edges) == 2
    types = [n.type for n in agent.graph_definition.nodes]
    assert types == ["asr", "llm", "tts"]
