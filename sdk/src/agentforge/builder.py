import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from agentforge.types import (
    AgentDefinition,
    GraphDefinition,
    NodeConfig,
    EdgeConfig,
    SkillSpec,
    PolicyConfig,
    AgentModelConfig,
)

class AgentPolicy:
    def __init__(self) -> None:
        self._policy = PolicyConfig()

    def allow_tools(self, *tools: str) -> "AgentPolicy":
        if self._policy.allowed_tools is None:
            self._policy.allowed_tools = []
        self._policy.allowed_tools.extend(tools)
        return self

    def deny_tool(self, *tools: str) -> "AgentPolicy":
        self._policy.denied_tools.extend(tools)
        return self

    def require_approval_for(self, *tools: str) -> "AgentPolicy":
        self._policy.require_human_approval_for.extend(tools)
        return self

    def deny_input_pattern(self, pattern: str) -> "AgentPolicy":
        self._policy.deny_patterns.append(pattern)
        return self

    def max_cost(self, cost: float, currency: str = "USD") -> "AgentPolicy":
        if currency.upper() != "USD":
            pass
        self._policy.max_cost_usd = cost
        return self

    def max_steps(self, steps: int) -> "AgentPolicy":
        self._policy.max_graph_steps = steps
        return self

    def allow_fetch_only(self, *urls: str) -> "AgentPolicy":
        if self._policy.allowed_fetch_url_prefixes is None:
            self._policy.allowed_fetch_url_prefixes = []
        self._policy.allowed_fetch_url_prefixes.extend(urls)
        return self

    def max_message_history(self, n: int) -> "AgentPolicy":
        self._policy.max_message_history = n
        return self

    def context_compression_threshold(self, tokens: int) -> "AgentPolicy":
        self._policy.context_compression_threshold = tokens
        return self

    def build(self) -> PolicyConfig:
        return self._policy


class AgentBuilder:
    def __init__(self, name: str = "My Agent"):
        self._name = name
        self._description = None
        self._nodes: List[NodeConfig] = []
        self._edges: List[EdgeConfig] = []
        self._entry_point = None
        self._skills: List[SkillSpec] = []
        self._policy: Optional[PolicyConfig] = None
        self._model_config = AgentModelConfig()
        self._parallel_nodes: List[str] = []

    def description(self, desc: str) -> "AgentBuilder":
        self._description = desc
        return self

    def model(
        self,
        provider: str,
        model: str,
        temperature: float = 0.7,
        base_url: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> "AgentBuilder":
        self._model_config = AgentModelConfig(
            provider=provider,
            model=model,
            temperature=temperature,
            base_url=base_url,
            options=options or {},
        )
        return self

    def llm_node(self, id: str, system_prompt: str = "") -> "AgentBuilder":
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(
            id=id,
            type="llm",
            config={"system_prompt": system_prompt}
        ))
        return self

    def tool_node(self, id: str, tool_name: str) -> "AgentBuilder":
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(
            id=id,
            type="tool",
            config={"tool_name": tool_name}
        ))
        return self

    def asr_node(
        self,
        id: str,
        provider: str = "openai_whisper",
        language: str | None = None,
        filename: str | None = None,
    ) -> "AgentBuilder":
        config: Dict[str, Any] = {"provider": provider}
        if language:
            config["language"] = language
        if filename:
            config["filename"] = filename
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(id=id, type="asr", config=config))
        return self

    def tts_node(
        self,
        id: str,
        provider: str = "openai_tts",
        voice: str = "nova",
    ) -> "AgentBuilder":
        config: Dict[str, Any] = {"provider": provider, "voice": voice}
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(id=id, type="tts", config=config))
        return self

    def subagent_node(self, id: str, agent_id: str) -> "AgentBuilder":
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(
            id=id,
            type="subagent",
            config={"agent_id": agent_id}
        ))
        return self

    def custom_node(self, id: str, node_type: str, config: Dict[str, Any]) -> "AgentBuilder":
        if not self._entry_point:
            self._entry_point = id
        self._nodes.append(NodeConfig(
            id=id,
            type=node_type,
            config=config
        ))
        return self

    def edge(self, from_: str, to: str, condition: Optional[str] = None, condition_type: str = "always") -> "AgentBuilder":
        self._edges.append(EdgeConfig(
            from_=from_,
            to=to,
            condition=condition,
            condition_type=condition_type
        ))
        return self

    def parallel_nodes(self, *node_ids: str) -> "AgentBuilder":
        self._parallel_nodes.extend(node_ids)
        return self

    def policy(self, policy: AgentPolicy | PolicyConfig) -> "AgentBuilder":
        if isinstance(policy, AgentPolicy):
            self._policy = policy.build()
        else:
            self._policy = policy
        return self

    def skill(self, name: str, skill_type: str = "instruction", source_code: str = "", instructions: str = "") -> "AgentBuilder":
        self._skills.append(SkillSpec(
            name=name,
            skill_type=skill_type,
            source_code=source_code,
            instructions=instructions
        ))
        return self

    def build(self) -> AgentDefinition:
        return AgentDefinition(
            name=self._name,
            description=self._description,
            graph_definition=GraphDefinition(
                nodes=self._nodes,
                edges=self._edges,
                entry_point=self._entry_point,
                parallel_nodes=list(self._parallel_nodes),
            ),
            model_config=self._model_config,
            skills=self._skills,
            execution_policy=self._policy
        )

    def export_json(self, filepath: str) -> None:
        agent_def = self.build()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(agent_def.model_dump_json(indent=2, by_alias=True))

    def build_and_export(self, filepath: str) -> None:
        """Alias of export_json."""
        self.export_json(filepath)

    def run(self, inputs: Dict[str, Any]) -> Any:
        from agentforge.agent import LocalAgent
        agent_def = self.build()
        agent = LocalAgent(agent_def.model_dump(by_alias=True))
        return agent.invoke(inputs)

    async def arun(self, inputs: Dict[str, Any]) -> Any:
        from agentforge.agent import LocalAgent
        agent_def = self.build()
        agent = LocalAgent(agent_def.model_dump(by_alias=True))
        return await agent.ainvoke(inputs)

def Agent(name: str = "My Agent") -> AgentBuilder:
    return AgentBuilder(name)
