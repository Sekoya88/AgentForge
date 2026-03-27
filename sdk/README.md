# AgentForge SDK

A lightweight Python SDK for loading and running agents exported from AgentForge.

## Installation

```bash
pip install agentforge-sdk
```

## Usage

```python
import asyncio
from agentforge import load_agent
from langchain_core.messages import HumanMessage

async def main():
    # Load your exported agent JSON
    agent = load_agent("my_exported_agent.json")

    # Run the agent locally
    result = await agent.ainvoke({
        "messages": [HumanMessage(content="Hello! Can you help me calculate 25 * 4?")]
    })

    # Print the final message
    print(result["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(main())
```

> **Note:** The SDK evaluates code blocks embedded in skills using local execution. Ensure you trust the exported agent JSON before running it locally!
