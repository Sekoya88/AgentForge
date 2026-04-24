import uuid

from app.infrastructure.persistence.postgres.models import (
    ExecutionFeedbackModel,
    ForgeSubAgentModel,
    MetaProposalModel,
)


def test_execution_feedback_model_instantiation():
    m = ExecutionFeedbackModel(
        execution_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        score=0.3,
        comment="too slow",
        category="quality",
    )
    assert m.score == 0.3
    assert m.category == "quality"


def test_meta_proposal_model_instantiation():
    m = MetaProposalModel(
        user_id=uuid.uuid4(),
        proposal_type="CREATE_SKILL",
        title="Add web_fetch skill",
        body="## Why\nhttp_request fails 80% of the time",
        payload={"name": "web_fetch", "source_code": "def web_fetch(): pass"},
        status="pending",
        source="on_demand",
    )
    assert m.status == "pending"
    assert m.agent_id is None


def test_forge_subagent_model_instantiation():
    m = ForgeSubAgentModel(
        name="skill_builder",
        display_name="Skill Builder Agent",
        system_prompt="You build skills.",
        tools=["search_skills", "create_skill_draft"],
        model_config_json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
        is_system=True,
        version=1,
    )
    assert m.name == "skill_builder"
    assert m.user_id is None
