from __future__ import annotations

import uuid
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from app.infrastructure.persistence.postgres.execution_feedback_repo import (
    ExecutionFeedbackRepository,
)
from app.infrastructure.persistence.postgres.meta_proposal_repo import MetaProposalRepository
from app.infrastructure.subagents.registry import SubAgentRegistry
from app.infrastructure.subagents.tools.execution_tools import make_execution_tools
from app.infrastructure.subagents.tools.proposal_tools import make_proposal_tools
from app.infrastructure.subagents.tools.skill_tools import make_skill_tools


class _SubAgentState(TypedDict):
    messages: list


_ALL_TOOL_FACTORIES = {
    "get_feedback_summary": "execution",
    "search_failed_executions": "execution",
    "create_proposal": "proposal",
    "search_skills": "skill",
}


class SubAgentRunner:
    def __init__(
        self,
        registry: SubAgentRegistry,
        session,
        user_id: uuid.UUID,
        anthropic_key: str | None = None,
    ) -> None:
        self._registry = registry
        self._session = session
        self._user_id = user_id
        self._anthropic_key = anthropic_key

    async def run(self, agent_name: str, task: str, context: dict | None = None) -> dict[str, Any]:
        definition = await self._registry.get(agent_name, user_id=self._user_id)
        return await self._invoke_graph(definition, task, context or {})

    async def _invoke_graph(self, definition, task: str, context: dict) -> dict[str, Any]:
        cfg = definition.model_config_json or {}
        provider = cfg.get("provider", "anthropic")
        model_name = cfg.get("model", "claude-haiku-4-5-20251001")
        temperature = cfg.get("temperature", 0.2)

        tools = self._build_tools(definition.tools)

        if provider == "anthropic":
            llm = ChatAnthropic(
                model=model_name,
                temperature=temperature,
                api_key=self._anthropic_key,
            ).bind_tools(tools)
        else:
            raise NotImplementedError(f"Provider '{provider}' not supported for sub-agents yet.")

        tool_node = ToolNode(tools)

        def _agent_node(state: _SubAgentState) -> _SubAgentState:
            response = llm.invoke(state["messages"])
            return {"messages": state["messages"] + [response]}

        def _should_continue(state: _SubAgentState) -> str:
            last = state["messages"][-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "tools"
            return END

        graph = StateGraph(_SubAgentState)
        graph.add_node("agent", _agent_node)
        graph.add_node("tools", tool_node)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        compiled = graph.compile()

        context_str = f"\n\nContext: {context}" if context else ""
        initial_messages = [
            SystemMessage(content=definition.system_prompt),
            HumanMessage(content=task + context_str),
        ]

        result = await compiled.ainvoke({"messages": initial_messages})
        last_msg = result["messages"][-1]
        summary = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        return {"summary": summary, "proposals": []}

    def _build_tools(self, tool_names: list[str]) -> list:
        proposal_repo = MetaProposalRepository(self._session)
        feedback_repo = ExecutionFeedbackRepository(self._session)

        all_tools: list = []
        categories_added: set[str] = set()

        for name in tool_names:
            category = _ALL_TOOL_FACTORIES.get(name)
            if category in categories_added:
                continue
            if category == "proposal":
                all_tools.extend(make_proposal_tools(self._user_id, proposal_repo))
                categories_added.add("proposal")
            elif category == "execution":
                all_tools.extend(make_execution_tools(self._user_id, feedback_repo, self._session))
                categories_added.add("execution")
            elif category == "skill":
                all_tools.extend(make_skill_tools(self._user_id, self._session))
                categories_added.add("skill")

        return all_tools
