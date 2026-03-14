"""Tests for mail module."""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_list_messages_empty(test_db):
    """Empty inbox should return empty list."""
    with patch("app.mail.service.get_db") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=test_db)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.mail.service import list_messages
        messages = await list_messages()
        assert messages == []


@pytest.mark.asyncio
async def test_get_unread_count_empty(test_db):
    """Empty inbox should have 0 unread."""
    with patch("app.mail.service.get_db") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=test_db)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.mail.service import get_unread_count
        count = await get_unread_count()
        assert count == 0
