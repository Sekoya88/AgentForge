from uuid import uuid4

from app.api.schemas.agent_schemas import ExecutionResponse


def test_execution_response_coerces_list_content_to_text():
    raw = {
        "id": uuid4(),
        "agent_id": uuid4(),
        "user_id": uuid4(),
        "thread_id": "t1",
        "status": "completed",
        "input_messages": [],
        "output_messages": [
            {"role": "assistant", "content": [{"type": "text", "text": "Bonjour"}]},
        ],
        "interrupt_state": None,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
        "token_usage": None,
        "duration_ms": 1,
    }
    m = ExecutionResponse.model_validate(raw)
    assert m.output_messages is not None
    assert m.output_messages[0]["content"] == "Bonjour"
