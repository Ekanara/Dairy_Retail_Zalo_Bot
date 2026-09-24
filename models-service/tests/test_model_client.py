"""Tests for model_client.py — AgentScope ModelClient."""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add models-service root to path
MODELS_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, MODELS_SERVICE_DIR)

# API_KEY is required by app.core.config.Settings
os.environ.setdefault("API_KEY", "test-dummy-key")


class TestModelClientInit(unittest.TestCase):
    """Test ModelClient initialisation."""

    @patch("app.clients.model_client.OpenAIChatModel")
    def test_creates_openai_model(self, mock_model_cls):
        """ModelClient creates an OpenAIChatModel on init."""
        from app.clients.model_client import ModelClient

        client = ModelClient()

        mock_model_cls.assert_called_once()
        call_kwargs = mock_model_cls.call_args
        self.assertIn("model_name", call_kwargs.kwargs)
        self.assertIn("api_key", call_kwargs.kwargs)
        self.assertTrue(call_kwargs.kwargs.get("stream", False))

    @patch("app.clients.model_client.OpenAIChatModel")
    @patch("app.clients.model_client.HttpStatelessClient")
    def test_mcp_client_created_when_enabled(self, mock_mcp_cls, mock_model_cls):
        """MCP client is created when MCP_ENABLED is True."""
        from app.clients.model_client import ModelClient

        with patch("app.clients.model_client.settings") as mock_settings:
            mock_settings.MCP_ENABLED = True
            mock_settings.MCP_SERVICE_URL = "http://localhost:8004"
            mock_settings.MODEL_NAME = "test-model"
            mock_settings.MODEL_TEMPERATURE = 0.2
            mock_settings.API_KEY = "test-key"
            mock_settings.BASE_URL = "http://localhost:8000"

            client = ModelClient()

        mock_mcp_cls.assert_called_once()
        self.assertIsNotNone(client._mcp_client)

    @patch("app.clients.model_client.OpenAIChatModel")
    def test_skills_dir_detected(self, mock_model_cls):
        """Skills directory is detected when it exists."""
        from app.clients.model_client import ModelClient

        client = ModelClient()
        # skills/ directory exists in the project
        self.assertIsNotNone(client._skills_dir)


class TestModelClientBuildAgent(unittest.TestCase):
    """Test ModelClient.build_agent()."""

    @patch("app.clients.model_client.OpenAIChatModel")
    def test_build_agent_returns_react_agent(self, mock_model_cls):
        """build_agent returns a ReActAgent instance."""
        from agentscope.agent import ReActAgent
        from app.clients.model_client import ModelClient

        client = ModelClient()
        # Disable MCP for this test
        client._mcp_client = None

        agent = asyncio.run(
            client.build_agent("Test system prompt", "user123")
        )

        self.assertIsInstance(agent, ReActAgent)

    @patch("app.clients.model_client.OpenAIChatModel")
    def test_build_agent_injects_system_prompt(self, mock_model_cls):
        """build_agent passes system_prompt to the agent."""
        from app.clients.model_client import ModelClient

        client = ModelClient()
        client._mcp_client = None

        prompt = "You are NutriBot, a milk sales assistant."
        agent = asyncio.run(
            client.build_agent(prompt, "user123")
        )

        self.assertIn(prompt, agent.sys_prompt)

    @patch("app.clients.model_client.OpenAIChatModel")
    def test_build_agent_registers_view_text_file(self, mock_model_cls):
        """build_agent registers view_text_file tool in toolkit."""
        from app.clients.model_client import ModelClient

        client = ModelClient()
        client._mcp_client = None

        agent = asyncio.run(
            client.build_agent("prompt", "user123")
        )

        self.assertIn("view_text_file", agent.toolkit.tools)

    @patch("app.clients.model_client.OpenAIChatModel")
    def test_build_agent_is_async(self, mock_model_cls):
        """build_agent is an async method."""
        import inspect
        from app.clients.model_client import ModelClient

        self.assertTrue(inspect.iscoroutinefunction(ModelClient.build_agent))


class TestNormalizeMcpUrl(unittest.TestCase):
    """Test _normalize_mcp_url helper."""

    def test_appends_mcp_path(self):
        from app.clients.model_client import _normalize_mcp_url

        self.assertEqual(
            _normalize_mcp_url("http://localhost:8004"),
            "http://localhost:8004/mcp",
        )

    def test_preserves_existing_mcp_path(self):
        from app.clients.model_client import _normalize_mcp_url

        self.assertEqual(
            _normalize_mcp_url("http://localhost:8004/mcp"),
            "http://localhost:8004/mcp",
        )

    def test_strips_trailing_slash(self):
        from app.clients.model_client import _normalize_mcp_url

        self.assertEqual(
            _normalize_mcp_url("http://localhost:8004/"),
            "http://localhost:8004/mcp",
        )


if __name__ == "__main__":
    unittest.main()
