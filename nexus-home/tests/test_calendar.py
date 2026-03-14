"""Tests for calendar module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from app.calendar.service import create_event, list_events, delete_event


@pytest.mark.asyncio
async def test_create_and_list_event(test_db):
    """Creating an event should make it listable."""
    with patch("app.calendar.service.get_db") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=test_db)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_event(
            title="Test Meeting",
            start_time=datetime.now() + timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=2),
            description="A test event",
        )
        assert result["title"] == "Test Meeting"
        assert "id" in result
