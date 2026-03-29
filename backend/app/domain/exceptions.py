class DomainError(Exception):
    """Base domain error."""


class UserAlreadyExistsError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class UserNotFoundError(DomainError):
    pass


class AgentNotFoundError(DomainError):
    pass


class ExecutionNotFoundError(DomainError):
    pass


class StreamingNotAvailableError(DomainError):
    """Redis or streaming backend not configured."""

    pass


class CampaignNotFoundError(DomainError):
    pass


class SkillNotFoundError(DomainError):
    pass


class FinetuneJobNotFoundError(DomainError):
    pass


class ModalNotInstalledError(DomainError):
    """MODAL_ENABLED is true but the ``modal`` package is not installed."""

    pass


class InvalidGraphDefinitionError(DomainError):
    pass


class InvalidAgentSkillsError(DomainError):
    """Attached skill IDs are invalid, invisible, or malformed."""

    pass


class ExecutionNotResumableError(DomainError):
    pass
