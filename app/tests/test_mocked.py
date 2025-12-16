import sys
from unittest.mock import MagicMock

# Mock app.core.database BEFORE importing anything else that depends on it
mock_database = MagicMock()
mock_database.redis_client = MagicMock()
sys.modules["app.core.database"] = mock_database

import logging
import pytest
from unittest.mock import patch

# Now import the modules that depend on app.core.database
from app.core.scanner import PIIScanner
from app.core.assistant import AIAssistant
from app.core.vault import PIIVault

# Mock Redis Connection (though handled by sys.modules, we want control)
@pytest.fixture
def mock_redis():
    return mock_database.redis_client

# Mock Vault
@pytest.fixture
def mock_vault(mock_redis):
    # Vault imports default_redis_client from database, which is now our mock
    # But we want to ensure we are testing logic, so we instantiate normally
    # passing the mock explicitly if the constructor allows, or patching the class

    # Reload vault module to ensure it uses the mocked database if needed,
    # but since we patched sys.modules, it should use the mock.

    # However, Scanner imports 'vault' (instance) from app.core.vault.
    # We need to control that instance.

    # Let's create a fresh vault instance with our mock redis
    vault_instance = PIIVault(mock_redis)
    vault_instance.store = MagicMock(side_effect=lambda text, label: f"<{label}_{text}>")
    vault_instance.get = MagicMock(side_effect=lambda placeholder: placeholder.split('_')[1].strip('>'))
    vault_instance.get_status = MagicMock(return_value="AI")
    return vault_instance

# Test PII Scanner Logging
def test_pii_scanner_logging(mock_vault, caplog):
    scanner = PIIScanner(mock_vault)
    # The scanner uses self.model which loads GLiNER. This might be slow/downloading.
    # We should mock the GLiNER model too to speed up tests and avoid network.
    scanner.model = MagicMock()
    # Mock entities return
    scanner.model.predict_entities.return_value = []
    # Or actually, we want to test that it calls store.
    # Let's mock predict_entities to return nothing for the generic test,
    # but rely on regex for email test.

    # Enable logging capture
    with caplog.at_level(logging.INFO):
        original_text = "My email is test@example.com"
        # Regex should catch email even if GLiNER is mocked to return nothing
        anonymized = scanner.clean(original_text)

        # Check if the log message was generated
        assert "PII Clean: Original='My email is test@example.com'" in caplog.text
        assert "Anonymized=" in caplog.text
        assert "<EMAIL_" in anonymized

# Test Assistant Logging
def test_assistant_escalation_logging(caplog):
    # Mock OpenAI
    with patch("app.core.assistant.OpenAI") as mock_openai:
        assistant = AIAssistant()

        # Mock OpenAI response for thread run retrieval
        mock_run = MagicMock()
        mock_run.status = "completed"
        assistant.client.beta.threads.runs.create.return_value = mock_run
        assistant.client.beta.threads.runs.retrieve.return_value = mock_run

        # Mock message listing
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=MagicMock(value="ESKALATION_NOETIG"))]
        mock_messages = MagicMock()
        mock_messages.data = [mock_msg]
        assistant.client.beta.threads.messages.list.return_value = mock_messages

        with caplog.at_level(logging.INFO):
            response, escalated = assistant.ask_assistant("session_1", "Help me")

            assert escalated is True
            assert "Escalation triggered by AI response" in caplog.text

# Test Full History Retrieval
def test_get_thread_history():
    with patch("app.core.assistant.OpenAI") as mock_openai:
        assistant = AIAssistant()
        assistant._threads["session_1"] = "thread_123"

        # Mock messages list
        msg1 = MagicMock()
        msg1.role = "user"
        msg1.content = [MagicMock(text=MagicMock(value="Hello"))]

        msg2 = MagicMock()
        msg2.role = "assistant"
        msg2.content = [MagicMock(text=MagicMock(value="Hi there"))]

        mock_list = MagicMock()
        mock_list.data = [msg1, msg2]

        assistant.client.beta.threads.messages.list.return_value = mock_list

        history = assistant.get_thread_history("session_1")

        assert len(history) == 2
        assert history[0] == "User: Hello"
        assert history[1] == "Assistant: Hi there"

        # Verify call arguments (order='asc' is crucial)
        assistant.client.beta.threads.messages.list.assert_called_with(
            thread_id="thread_123",
            order="asc",
            limit=100
        )
