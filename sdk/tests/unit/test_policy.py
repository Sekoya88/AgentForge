from agentforge.builder import Agent, AgentPolicy
from agentforge.types import PolicyConfig


class TestAgentPolicy:
    def test_empty_policy(self):
        policy = AgentPolicy().build()
        assert isinstance(policy, PolicyConfig)
        assert policy.denied_tools == []
        assert policy.allowed_tools is None

    def test_allow_tools(self):
        policy = AgentPolicy().allow_tools("web_search", "calc").build()
        assert "web_search" in policy.allowed_tools
        assert "calc" in policy.allowed_tools

    def test_deny_tool(self):
        policy = AgentPolicy().deny_tool("exec", "shell").build()
        assert "exec" in policy.denied_tools
        assert "shell" in policy.denied_tools

    def test_require_approval_for(self):
        policy = AgentPolicy().require_approval_for("send_email").build()
        assert "send_email" in policy.require_human_approval_for

    def test_deny_input_pattern(self):
        policy = AgentPolicy().deny_input_pattern("ignore previous").build()
        assert "ignore previous" in policy.deny_patterns

    def test_max_cost(self):
        policy = AgentPolicy().max_cost(0.50).build()
        assert policy.max_cost_usd == 0.50

    def test_max_steps(self):
        policy = AgentPolicy().max_steps(5).build()
        assert policy.max_graph_steps == 5

    def test_allow_fetch_only(self):
        policy = AgentPolicy().allow_fetch_only("https://api.example.com").build()
        assert "https://api.example.com" in policy.allowed_fetch_url_prefixes

    def test_max_message_history(self):
        policy = AgentPolicy().max_message_history(20).build()
        assert policy.max_message_history == 20

    def test_context_compression_threshold(self):
        policy = AgentPolicy().context_compression_threshold(4000).build()
        assert policy.context_compression_threshold == 4000

    def test_chaining(self):
        policy = (
            AgentPolicy()
            .max_cost(1.0)
            .max_steps(10)
            .deny_tool("exec")
            .allow_tools("search")
            .build()
        )
        assert policy.max_cost_usd == 1.0
        assert policy.max_graph_steps == 10
        assert "exec" in policy.denied_tools
        assert "search" in policy.allowed_tools

    def test_policy_passed_to_builder(self):
        policy = AgentPolicy().max_cost(0.1).max_steps(3)
        agent = Agent("test").llm_node("n1").policy(policy).build()
        assert agent.execution_policy is not None
        assert agent.execution_policy.max_cost_usd == 0.1
        assert agent.execution_policy.max_graph_steps == 3
