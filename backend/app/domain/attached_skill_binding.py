from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttachedSkillBinding:
    """Runtime view of a registry skill attached to an agent (matched by skill name)."""

    name: str
    skill_type: str  # "code" or "instruction"
    source_code: str
    instructions: str | None
    security_validated: bool
