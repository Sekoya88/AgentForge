# agentforge-sdk

Python SDK for [AgentForge](https://github.com/your/agentforge) — embed AI agents in any project.

## Installation

```bash
pip install agentforge-sdk
```

## Quick Start

```python
from agentforge_sdk import AgentForgeClient

client = AgentForgeClient(
    base_url="https://your-agentforge.com",
    api_key="your-api-key",
)

# Run an agent synchronously
result = client.agents.run(agent_id="your-agent-id", message="Hello!")
print(result.output)

# Stream tokens in real-time
for token in client.agents.stream(agent_id="your-agent-id", message="Tell me about AI"):
    print(token, end="", flush=True)

# Persistent conversation (maintains context across messages)
conv = client.conversations.create(agent_id="your-agent-id")
r1 = client.agents.run(agent_id="your-agent-id", message="My name is Alice", thread_id=conv.thread_id)
r2 = client.agents.run(agent_id="your-agent-id", message="What's my name?", thread_id=conv.thread_id)
# r2.output will reference Alice

# Export and import agents
bundle = client.agents.export(agent_id="your-agent-id")
new_agent = client.agents.import_bundle(bundle)
```

## API Reference

### `AgentForgeClient(base_url, api_key, timeout=60.0)`

### `client.agents.list()` → `list[Agent]`
### `client.agents.run(agent_id, message, thread_id=None)` → `ExecutionResult`
### `client.agents.stream(agent_id, message, thread_id=None)` → `Generator[str]`
### `client.agents.export(agent_id)` → `dict`
### `client.agents.import_bundle(bundle)` → `Agent`
### `client.conversations.create(agent_id, title=None)` → `Conversation`
### `client.conversations.list(agent_id)` → `list[Conversation]`
