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


class InvalidGraphDefinitionError(DomainError):
    pass


class ExecutionNotResumableError(DomainError):
    pass
