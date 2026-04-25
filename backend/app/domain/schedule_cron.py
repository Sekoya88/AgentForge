"""Cron helpers for agent schedules (croniter, UTC)."""

from datetime import UTC, datetime

from croniter import croniter
from croniter.croniter import CroniterBadCronError

from app.domain.exceptions import InvalidScheduleCronError


def next_fire_after(cron_expression: str, after: datetime) -> datetime:
    """Next cron fire strictly after `after` (timezone-aware UTC)."""
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    itr = croniter(cron_expression, after)
    nxt: datetime = itr.get_next(datetime)
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=UTC)
    return nxt


def validate_cron_expression(cron_expression: str) -> None:
    try:
        next_fire_after(cron_expression, datetime.now(UTC))
    except (CroniterBadCronError, KeyError, ValueError) as e:
        raise InvalidScheduleCronError(f"Invalid cron expression: {e!s}") from e
