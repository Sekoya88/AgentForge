from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AgentNotFoundError,
    CampaignNotFoundError,
    DomainError,
    ExecutionNotFoundError,
    ExecutionNotResumableError,
    FinetuneJobNotFoundError,
    InvalidAgentSkillsError,
    InvalidCredentialsError,
    InvalidGraphDefinitionError,
    InvalidScheduleCronError,
    InvalidSpeechFinetuneJobError,
    ModalNotInstalledError,
    ScheduleNotFoundError,
    SkillNotFoundError,
    StreamingNotAvailableError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


def _err(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    rid = getattr(request.state, "correlation_id", "")
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": rid}},
    )


def register_exception_handlers(app) -> None:
    @app.exception_handler(UserAlreadyExistsError)
    async def user_exists(request: Request, exc: UserAlreadyExistsError) -> JSONResponse:
        return _err(request, "USER_ALREADY_EXISTS", "User already exists", status.HTTP_409_CONFLICT)

    @app.exception_handler(InvalidCredentialsError)
    async def bad_creds(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        return _err(
            request, "INVALID_CREDENTIALS", "Invalid credentials", status.HTTP_401_UNAUTHORIZED
        )

    @app.exception_handler(UserNotFoundError)
    async def user_not_found(request: Request, exc: UserNotFoundError) -> JSONResponse:
        return _err(request, "USER_NOT_FOUND", "User not found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(AgentNotFoundError)
    async def agent_not_found(request: Request, exc: AgentNotFoundError) -> JSONResponse:
        return _err(request, "AGENT_NOT_FOUND", "Agent not found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(InvalidGraphDefinitionError)
    async def bad_graph(request: Request, exc: InvalidGraphDefinitionError) -> JSONResponse:
        return _err(
            request, "INVALID_GRAPH_DEFINITION", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(InvalidAgentSkillsError)
    async def bad_agent_skills(request: Request, exc: InvalidAgentSkillsError) -> JSONResponse:
        return _err(request, "INVALID_AGENT_SKILLS", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(ExecutionNotResumableError)
    async def not_resumable(request: Request, exc: ExecutionNotResumableError) -> JSONResponse:
        return _err(request, "EXECUTION_NOT_RESUMABLE", str(exc), status.HTTP_409_CONFLICT)

    @app.exception_handler(SkillNotFoundError)
    async def skill_not_found(request: Request, exc: SkillNotFoundError) -> JSONResponse:
        return _err(request, "SKILL_NOT_FOUND", "Skill not found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(FinetuneJobNotFoundError)
    async def finetune_not_found(request: Request, exc: FinetuneJobNotFoundError) -> JSONResponse:
        return _err(
            request, "FINETUNE_JOB_NOT_FOUND", "Fine-tune job not found", status.HTTP_404_NOT_FOUND
        )

    @app.exception_handler(InvalidSpeechFinetuneJobError)
    async def speech_finetune_invalid(
        request: Request, exc: InvalidSpeechFinetuneJobError
    ) -> JSONResponse:
        return _err(
            request,
            "INVALID_SPEECH_FINETUNE_JOB",
            str(exc) or "Invalid speech fine-tune job",
            status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(CampaignNotFoundError)
    async def campaign_not_found(request: Request, exc: CampaignNotFoundError) -> JSONResponse:
        return _err(request, "CAMPAIGN_NOT_FOUND", "Campaign not found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(ExecutionNotFoundError)
    async def exec_not_found(request: Request, exc: ExecutionNotFoundError) -> JSONResponse:
        return _err(
            request, "EXECUTION_NOT_FOUND", "Execution not found", status.HTTP_404_NOT_FOUND
        )

    @app.exception_handler(ScheduleNotFoundError)
    async def schedule_not_found(request: Request, exc: ScheduleNotFoundError) -> JSONResponse:
        return _err(request, "SCHEDULE_NOT_FOUND", "Schedule not found", status.HTTP_404_NOT_FOUND)

    @app.exception_handler(InvalidScheduleCronError)
    async def bad_schedule_cron(request: Request, exc: InvalidScheduleCronError) -> JSONResponse:
        return _err(
            request, "INVALID_SCHEDULE_CRON", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(StreamingNotAvailableError)
    async def no_streaming(request: Request, exc: StreamingNotAvailableError) -> JSONResponse:
        return _err(
            request,
            "STREAMING_NOT_AVAILABLE",
            "Streaming requires Redis",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @app.exception_handler(ModalNotInstalledError)
    async def modal_missing(request: Request, exc: ModalNotInstalledError) -> JSONResponse:
        return _err(
            request,
            "MODAL_NOT_INSTALLED",
            str(exc)
            or (
                "Modal is enabled but the modal package is missing."
                " Run: cd backend && uv pip install -e ."
            ),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @app.exception_handler(DomainError)
    async def domain(request: Request, exc: DomainError) -> JSONResponse:
        return _err(request, "DOMAIN_ERROR", str(exc), status.HTTP_400_BAD_REQUEST)
