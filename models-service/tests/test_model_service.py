"""Tests for model_service.py — AgentScope integration."""

import os
import sys
import unittest

# Add models-service root to path
MODELS_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, MODELS_SERVICE_DIR)

# API_KEY is required by app.core.config.Settings
os.environ.setdefault("API_KEY", "test-dummy-key")


class TestBuildMemoryMessages(unittest.TestCase):
    """Test _build_memory_messages conversion."""

    def test_user_message_conversion(self):
        """User messages are converted to Msg with role='user'."""
        from agentscope.message import Msg
        from app.schemas.request import Message
        from app.services.model_service import _build_memory_messages

        messages = [Message(role="user", content="Xin chào")]
        result = _build_memory_messages(messages)

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Msg)
        self.assertEqual(result[0].role, "user")
        self.assertEqual(result[0].content, "Xin chào")

    def test_assistant_message_conversion(self):
        """Assistant messages are converted to Msg with role='assistant'."""
        from agentscope.message import Msg
        from app.schemas.request import Message
        from app.services.model_service import _build_memory_messages

        messages = [Message(role="assistant", content="Chào bạn!")]
        result = _build_memory_messages(messages)

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Msg)
        self.assertEqual(result[0].role, "assistant")
        self.assertEqual(result[0].content, "Chào bạn!")

    def test_system_messages_skipped(self):
        """System messages are skipped."""
        from app.schemas.request import Message
        from app.services.model_service import _build_memory_messages

        messages = [
            Message(role="system", content="You are a bot"),
            Message(role="user", content="Hello"),
        ]
        result = _build_memory_messages(messages)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].role, "user")

    def test_multi_turn_conversation(self):
        """Multiple messages are converted in order."""
        from app.schemas.request import Message
        from app.services.model_service import _build_memory_messages

        messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
            Message(role="user", content="What products?"),
        ]
        result = _build_memory_messages(messages)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].role, "user")
        self.assertEqual(result[1].role, "assistant")
        self.assertEqual(result[2].role, "user")

    def test_empty_messages(self):
        """Empty message list returns empty result."""
        from app.services.model_service import _build_memory_messages

        result = _build_memory_messages([])
        self.assertEqual(result, [])


class TestExtractLastUserMessage(unittest.TestCase):
    """Test _extract_last_user_message helper."""

    def test_returns_last_user_message(self):
        from app.schemas.request import Message
        from app.services.model_service import _extract_last_user_message

        messages = [
            Message(role="user", content="First"),
            Message(role="assistant", content="Reply"),
            Message(role="user", content="Second"),
        ]
        self.assertEqual(_extract_last_user_message(messages), "Second")

    def test_returns_empty_when_no_user(self):
        from app.schemas.request import Message
        from app.services.model_service import _extract_last_user_message

        messages = [Message(role="assistant", content="Reply")]
        self.assertEqual(_extract_last_user_message(messages), "")

    def test_returns_empty_for_empty_list(self):
        from app.services.model_service import _extract_last_user_message

        self.assertEqual(_extract_last_user_message([]), "")


class TestExtractTextContent(unittest.TestCase):
    """Test _extract_text_content helper."""

    def test_string_content(self):
        from agentscope.message import Msg
        from app.services.model_service import _extract_text_content

        msg = Msg(name="bot", content="Hello world", role="assistant")
        self.assertEqual(_extract_text_content(msg), "Hello world")

    def test_list_with_text_blocks(self):
        from agentscope.message import Msg
        from app.services.model_service import _extract_text_content

        msg = Msg(
            name="bot",
            content=[{"type": "text", "text": "Part 1"}, {"type": "text", "text": " Part 2"}],
            role="assistant",
        )
        self.assertEqual(_extract_text_content(msg), "Part 1 Part 2")

    def test_list_with_string_blocks(self):
        from agentscope.message import Msg
        from app.services.model_service import _extract_text_content

        msg = Msg(name="bot", content=["Hello", " world"], role="assistant")
        self.assertEqual(_extract_text_content(msg), "Hello world")

    def test_empty_content(self):
        from agentscope.message import Msg
        from app.services.model_service import _extract_text_content

        msg = Msg(name="bot", content="", role="assistant")
        self.assertEqual(_extract_text_content(msg), "")


class TestShortConfirmationHandling(unittest.TestCase):
    """Test short-confirmation detection and prompt augmentation."""

    def test_detects_single_word_confirmation(self):
        from app.services.model_service import _is_short_confirmation

        self.assertTrue(_is_short_confirmation("lon"))
        self.assertTrue(_is_short_confirmation("ok"))

    def test_detects_phrase_confirmation(self):
        from app.services.model_service import _is_short_confirmation

        self.assertTrue(_is_short_confirmation("tôi chọn lon"))
        self.assertTrue(_is_short_confirmation("em lấy hộp"))

    def test_rejects_non_confirmation_question(self):
        from app.services.model_service import _is_short_confirmation

        self.assertFalse(_is_short_confirmation("lon bao nhieu tien"))
        self.assertFalse(_is_short_confirmation("ensure gold co hang khong"))

    def test_prepare_prompt_adds_hint_when_context_exists(self):
        from app.schemas.request import Message
        from app.services.model_service import _prepare_user_prompt_for_agent

        history = [
            Message(role="assistant", content="Anh/chị chọn lon hay hộp ạ?"),
            Message(role="user", content="lon"),
        ]
        prepared = _prepare_user_prompt_for_agent("lon", history)
        self.assertIn("HƯỚNG DẪN NỘI BỘ", prepared)

    def test_prepare_prompt_keeps_original_without_context(self):
        from app.services.model_service import _prepare_user_prompt_for_agent

        prepared = _prepare_user_prompt_for_agent("ok", [])
        self.assertEqual(prepared, "ok")


class TestInjectRuntimeUserId(unittest.TestCase):
    """Test _inject_runtime_user_id."""

    def test_appends_constraint(self):
        from app.services.model_service import _inject_runtime_user_id

        result = _inject_runtime_user_id("Base prompt", "user_abc")
        self.assertIn("RUNTIME TOOL CONSTRAINT", result)
        self.assertIn("user_abc", result)

    def test_preserves_original_prompt(self):
        from app.services.model_service import _inject_runtime_user_id

        base = "Original content."
        result = _inject_runtime_user_id(base, "u1")
        self.assertTrue(result.startswith(base))


class TestLogToolCalls(unittest.TestCase):
    """Test _log_tool_calls doesn't crash on various inputs."""

    def test_handles_empty_messages(self):
        """Should not crash on empty message list."""
        from app.services.model_service import _log_tool_calls

        _log_tool_calls([], "user123")  # Should not raise

    def test_handles_user_messages(self):
        """Should skip non-assistant messages."""
        from agentscope.message import Msg
        from app.services.model_service import _log_tool_calls

        msgs = [Msg(name="user", content="Hello", role="user")]
        _log_tool_calls(msgs, "user123")  # Should not raise


if __name__ == "__main__":
    unittest.main()
