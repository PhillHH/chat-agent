
import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Set env var before importing app (to enable admin routes)
os.environ["ENABLE_ADMIN_BACKEND"] = "true"

from app.main import app
from app.core.db_sqla import get_db, ChatSession, ChatMessage

# Mock DB Session
mock_db_session = MagicMock()

def override_get_db():
    try:
        yield mock_db_session
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_admin_sessions_list():
    # Setup mock return
    mock_session = MagicMock()
    mock_session.id = "sess_123"
    mock_session.created_at = "2023-01-01T12:00:00"
    mock_session.notes = "Test Note"

    # Mock query chain
    mock_query = mock_db_session.query.return_value
    mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_session]

    response = client.get("/admin/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "sess_123"

def test_admin_session_detail():
    mock_session = MagicMock()
    mock_session.id = "sess_123"
    mock_msg = MagicMock()
    mock_msg.role = "user"
    mock_msg.content = "Hello"
    mock_msg.timestamp = "2023-01-01T12:00:01"
    mock_session.messages = [mock_msg]

    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session

    response = client.get("/admin/sessions/sess_123")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "sess_123"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"

def test_admin_disabled():
    # Test with disabled backend
    with patch.dict(os.environ, {"ENABLE_ADMIN_BACKEND": "false"}):
        # We need to re-import or simulate the logic.
        # Since the route logic checks the env var at runtime inside the function:
        # We patch the variable locally for the check.
        # Note: app/routers/admin.py reads os.getenv at MODULE level.
        # So changing os.environ here won't affect the variable ADMIN_ENABLED in admin.py
        # unless we reload the module or patch the module variable.

        with patch("app.routers.admin.ADMIN_ENABLED", False):
            response = client.get("/admin/sessions")
            assert response.status_code == 403
