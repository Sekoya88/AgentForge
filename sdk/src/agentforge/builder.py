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
    def __init__(self):
        self._policy = PolicyConfig()

    def allow_tools(self, *tools: str) -> "AgentPolicy":
        if self._policy.allow_tools is None:
            self._policy.allow_tools = []
        self._policy.allow_tools.extend(tools)
        return self

    def deny_tool(self, *tools: str) -> "AgentPolicy":
        if self._policy.deny_tools is None:
            self._policy.deny_tools = []
        self._policy.deny_tools.extend(tools)
        return self

    def require_approval_for(self, *tools: str) -> "AgentPolicy":
        if self._policy.require_approval_for is None:
            self._policy.require_approval_for = []
        self._policy.require_approval_for.extend(tools)
        return self

    def deny_input_pattern(self, pattern: str) -> "AgentPolicy":
        self._policy.deny_input_pattern = pattern
        return self

    def max_cost(self, cost: float, currency: str = "USD") -> "AgentPolicy":
        # Only USD is supported right now, but keeping the signature
        self._policy.max_cost_usd = cost
        return self

    def max_steps(self, steps: int) -> "AgentPolicy":
        self._policy.max_steps = steps
        return self

    def allow_fetch_only(self, *urls: str) -> "AgentPolicy":
        if self._policy.allowed_urls is None:
            self._policy.allowed_urls = []
            self._policy.allowed_urls.extend(urls)
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

    def description(self, desc: str) -> "AgentBuilder":
        self._description = desc
        return self

    def model(self, provider: str, model: str, temperature: float = 0.7) -> "AgentBuilder":
        self._model_config = AgentModelConfig(
            provider=provider,
            model=model,
            temperature=temperature
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
                entry_point=self._entry_point
            ),
            model_config=self._model_config,
            skills=self._skills,
            execution_policy=self._policy
        )

    def export_json(self, filepath: str) -> None:
        agent_def = self.build()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(agent_def.model_dump_json(indent=2, by_alias=True))

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
