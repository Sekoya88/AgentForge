from datetime import UTC, datetime

import pytest

from app.domain.exceptions import InvalidScheduleCronError
from app.domain.schedule_cron import next_fire_after, validate_cron_expression


def test_next_fire_after_hourly() -> None:
    base = datetime(2026, 3, 31, 14, 30, tzinfo=UTC)
    nxt = next_fire_after("0 * * * *", base)
    assert nxt == datetime(2026, 3, 31, 15, 0, tzinfo=UTC)


def test_validate_cron_rejects_garbage() -> None:
    with pytest.raises(InvalidScheduleCronError):
        validate_cron_expression("not a cron")
