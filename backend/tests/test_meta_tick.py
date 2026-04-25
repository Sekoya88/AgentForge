from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_meta_tick_skips_users_without_recent_executions():
    from app.infrastructure.scheduling.meta_tick import run_meta_tick_once

    with patch("app.infrastructure.scheduling.meta_tick.session_scope") as mock_scope:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        await run_meta_tick_once()
