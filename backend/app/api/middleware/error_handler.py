from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AgentNotFoundError,
    CampaignNotFoundError,
    DomainError,
    ExecutionNotFoundError,
    ExecutionNotResumableError,
    FinetuneJobNotFoundError,
    InvalidCredentialsError,
    InvalidGraphDefinitionError,
    SkillNotFoundError,
    StreamingNotAvailableError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


def register_exception_handlers(app) -> None:
    @app.exception_handler(UserAlreadyExistsError)
    async def user_exists(_: Request, __: UserAlreadyExistsError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "User already exists"},
        )

    @app.exception_handler(InvalidCredentialsError)
    async def bad_creds(_: Request, __: InvalidCredentialsError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid credentials"},
        )

    @app.exception_handler(UserNotFoundError)
    async def user_not_found(_: Request, __: UserNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "User not found"},
        )

    @app.exception_handler(AgentNotFoundError)
    async def agent_not_found(_: Request, __: AgentNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Agent not found"},
        )

    @app.exception_handler(InvalidGraphDefinitionError)
    async def bad_graph(_: Request, exc: InvalidGraphDefinitionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ExecutionNotResumableError)
    async def not_resumable(_: Request, exc: ExecutionNotResumableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(SkillNotFoundError)
    async def skill_not_found(_: Request, __: SkillNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Skill not found"},
        )

    @app.exception_handler(FinetuneJobNotFoundError)
    async def finetune_not_found(_: Request, __: FinetuneJobNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Fine-tune job not found"},
        )

    @app.exception_handler(CampaignNotFoundError)
    async def campaign_not_found(_: Request, __: CampaignNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Campaign not found"},
        )

    @app.exception_handler(ExecutionNotFoundError)
    async def exec_not_found(_: Request, __: ExecutionNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Execution not found"},
        )

    @app.exception_handler(StreamingNotAvailableError)
    async def no_streaming(_: Request, __: StreamingNotAvailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Streaming requires Redis"},
        )

    @app.exception_handler(DomainError)
    async def domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )
