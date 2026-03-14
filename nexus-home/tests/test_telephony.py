"""Tests for telephony module."""

import pytest
from unittest.mock import patch, AsyncMock

from app.telephony.service import get_call_history, get_status


@pytest.mark.asyncio
async def test_get_status_unregistered():
    """Default status should be unregistered."""
    with patch("app.telephony.service.sip_client") as mock:
        mock.is_registered = False
        status = await get_status()
        assert status["registered"] is False


@pytest.mark.asyncio
async def test_call_history_empty(test_db):
    """Empty call history."""
    with patch("app.telephony.service.get_db") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=test_db)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        history = await get_call_history()
        assert history == []
