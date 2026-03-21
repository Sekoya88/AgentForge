from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.domain.value_objects import GeneratedAgent, GeneratedSkill


class GenerationService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _get_llm(self) -> ChatOpenAI:
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for AI generation")
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=self._settings.openai_api_key,
            temperature=0.2,
        )

    async def generate_agent(self, prompt: str) -> GeneratedAgent:
        llm = self._get_llm().with_structured_output(GeneratedAgent)
        sys_prompt = """You are an AI architect. Given a user request, design an autonomous agent.
Output valid JSON ONLY with these keys:
- "name": A catchy name for the agent
- "description": Short description
- "model_config": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2}
- "graph_definition": The LangGraph representation.

LangGraph definition format:
{
  "entry_point": "node_id",
  "nodes": [
     {"id": "n1", "type": "llm", "config": {"prompt": "system prompt"}},
     {"id": "n2", "type": "tool", "config": {"tool_name": "fetch"}},
     {"id": "n3", "type": "subagent", "config": {"subagent_name": "Reviewer"}}
  ],
  "edges": [
     {"from": "n1", "to": "n2", "condition": "fetch_needed"}
  ]
}
Make it practical and logical."""
        return await llm.ainvoke([SystemMessage(content=sys_prompt), HumanMessage(content=prompt)])

    async def generate_skill(self, prompt: str) -> GeneratedSkill:
        llm = self._get_llm().with_structured_output(GeneratedSkill)
        sys_prompt = """You are a senior Python software engineer.
Given a user request, write a Python skill (tool) for an AI agent.
Output valid JSON ONLY with these keys:
- "name": Tool name (snake_case)
- "description": Short description
- "source_code": The Python code implementing the tool (should be a standalone function).
- "parameters_schema": JSON Schema of the arguments it takes.
- "permissions": Array of required permissions, e.g. ["network", "fs"].

Example source code:
"def my_tool(input_text: str) -> str:\n    '''Does something'''\n    return input_text.upper()"
"""
        return await llm.ainvoke([SystemMessage(content=sys_prompt), HumanMessage(content=prompt)])
