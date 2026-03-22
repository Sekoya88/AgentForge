from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttachedSkillBinding:
    """Runtime view of a registry skill attached to an agent (matched by skill name)."""

    name: str
    source_code: str
    security_validated: bool
