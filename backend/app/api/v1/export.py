"""Agent export endpoint — supports python, docker, and langgraph formats."""

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse

from app.dependencies import get_agent_repository, get_current_user
from app.domain.entities.user import User
from app.domain.ports.agent_repository import AgentRepository

router = APIRouter(prefix="/agents", tags=["export"])

_PYTHON_TEMPLATE = '''\
#!/usr/bin/env python3
"""
{agent_name} — exported from AgentForge
Generated: {date}
"""
import os
from openai import OpenAI

SYSTEM_PROMPT = """{system_prompt}"""


def main():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    history = [{{"role": "system", "content": SYSTEM_PROMPT}}]
    print(f"Chat with {agent_name}. Press Ctrl+C to exit.\\n")
    while True:
        user_input = input("You: ")
        history.append({{"role": "user", "content": user_input}})
        resp = client.chat.completions.create(model="gpt-4o", messages=history)
        reply = resp.choices[0].message.content
        history.append({{"role": "assistant", "content": reply}})
        print(f"Agent: {{reply}}\\n")


if __name__ == "__main__":
    main()
'''

_DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app
RUN pip install openai
COPY agent.py .
ENV OPENAI_API_KEY=""
CMD ["python", "agent.py"]
"""

_README_TEMPLATE = """\
# {agent_name} — AgentForge Docker Export

## Build

```bash
docker build -t {image_name} .
```

## Run

```bash
docker run -it -e OPENAI_API_KEY=your_key_here {image_name}
```

The container starts an interactive REPL. Press `Ctrl+C` to exit.
"""


def _extract_system_prompt(graph_def: dict) -> str:
    nodes = graph_def.get("nodes", [])
    for node in nodes:
        cfg = node.get("config", {})
        sp = cfg.get("system_prompt", "")
        if sp:
            return sp
    return "You are a helpful assistant."


def _build_python_script(agent_name: str, system_prompt: str) -> str:
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    return _PYTHON_TEMPLATE.format(
        agent_name=agent_name,
        date=date,
        system_prompt=system_prompt,
    )


@router.get("/{agent_id}/export")
async def export_agent(
    agent_id: UUID,
    format: Annotated[str, Query(pattern="^(python|docker|langgraph)$")] = "python",
    user: Annotated[User, Depends(get_current_user)] = None,
    repo: Annotated[AgentRepository, Depends(get_agent_repository)] = None,
) -> Response:
    agent = await repo.get_by_id(agent_id, user.id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    graph_def: dict = agent.graph_definition or {}
    system_prompt = _extract_system_prompt(graph_def)
    agent_name: str = agent.name or "agent"

    if format == "python":
        script = _build_python_script(agent_name, system_prompt)
        filename = f"{agent_name.lower().replace(' ', '_')}.py"
        return Response(
            content=script.encode(),
            media_type="text/x-python",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if format == "docker":
        script = _build_python_script(agent_name, system_prompt)
        image_name = agent_name.lower().replace(" ", "-")
        readme = _README_TEMPLATE.format(agent_name=agent_name, image_name=image_name)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("agent.py", script)
            zf.writestr("Dockerfile", _DOCKERFILE)
            zf.writestr("README.md", readme)
        buf.seek(0)

        filename = f"{image_name}.zip"
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # langgraph
    payload = {
        "agentforge_version": "1.0",
        "exported_at": datetime.now(UTC).isoformat(),
        "agent": {
            "name": agent_name,
            "description": agent.description or "",
            "graph_definition": graph_def,
        },
    }
    filename = f"{agent_name.lower().replace(' ', '_')}_langgraph.json"
    return Response(
        content=json.dumps(payload, indent=2).encode(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
