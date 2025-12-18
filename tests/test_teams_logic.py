
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from app.routers import teams
from app.core.connection_manager import ConnectionManager
from botbuilder.schema import Activity

# Mock settings
with patch("app.core.config.Settings") as MockSettings:
    MockSettings.return_value.teams_app_id = "test_id"
    MockSettings.return_value.teams_app_password = "test_password"

    app = FastAPI()
    app.include_router(teams.router)
    client = TestClient(app)

@pytest.mark.asyncio
async def test_connection_manager():
    manager = ConnectionManager()
    ws_mock = AsyncMock()

    # Test Connect
    await manager.connect("session_1", ws_mock)
    assert "session_1" in manager.active_connections

    # Test Teams Reference
    ref_mock = MagicMock()
    ref_mock.conversation.id = "conv_1"
    manager.set_teams_reference("session_1", ref_mock)
    assert manager.get_teams_reference("session_1") == ref_mock
    assert manager.get_session_by_conversation("conv_1") == "session_1"

    # Test Disconnect
    manager.disconnect("session_1")
    assert "session_1" not in manager.active_connections

@pytest.mark.asyncio
async def test_teams_connect_command():
    # Setup mocks
    mock_response = Response(status_code=202)

    # We need to mock the bot logic inside process_activity, but that's hard because it's a callback.
    # Instead, we test the bot_logic function directly or mock the adapter to call the callback.

    # Approach: Import bot_logic and test it directly
    from app.routers.teams import bot_logic

    # Mock TurnContext
    mock_context = MagicMock()
    mock_context.activity.type = "message"
    mock_context.activity.text = "connect sess_123"
    mock_context.activity.conversation.id = "conv_123"
    mock_context.send_activity = AsyncMock()
    mock_context.activity.get_conversation_reference = MagicMock(return_value="ref_123")

    # Mock Connection Manager (it's a global singleton, so we patch the module attribute)
    with patch("app.routers.teams.manager") as mock_manager:
        mock_manager.set_teams_reference = MagicMock()
        mock_manager.send_personal_message = AsyncMock()

        # Run logic
        await bot_logic(mock_context)

        # Verify
        mock_manager.set_teams_reference.assert_called_with("sess_123", "ref_123")
        mock_context.send_activity.assert_called() # Should send confirmation
        mock_manager.send_personal_message.assert_called() # Should notify WS
