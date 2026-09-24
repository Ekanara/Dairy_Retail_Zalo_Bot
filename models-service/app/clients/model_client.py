"""
AgentScope model client with AgentSkill framework.

Wraps `OpenAIChatModel` (agentscope) to support any OpenAI-compatible
inference endpoint (OpenAI, vLLM, LM Studio, Ollama …).

Uses the AgentSkill framework for dynamic skill discovery, invocation,
and session-state tracking via RuntimeContextMemory.
"""

from __future__ import annotations

import pathlib
from typing import Any

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.mcp import HttpStatelessClient
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit

from skill_tool import SkillTool
from skill_tool.todo import TodoWriteManager
from skill_tool.adapters import (
    make_agentscope_skill_tool,
    make_agentscope_read_skill_file_tool,
    make_agentscope_list_skill_files_tool,
    make_agentscope_todo_write_tool,
)
from memory.store import RuntimeContextStore
from memory.agentscope import RuntimeContextMemory

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Tools whose `user_id` arg must be force-overridden with the runtime value.
_TOOLS_WITH_USER_ID = frozenset({
    "create_order",
    "view_personal_profile",
    "edit_personal_profile",
})


def _normalize_mcp_url(raw: str) -> str:
    """Accept both `http://host:port` and `http://host:port/mcp`."""
    base = raw.rstrip("/")
    if base.endswith("/mcp"):
        return base
    return f"{base}/mcp"


class ModelClient:
    """
    Singleton-style client that holds the configured model, MCP client,
    and SkillTool instance.

    Call `build_agent(system_prompt, user_id)` per request to get a fresh
    `ReActAgent` bound to the user-specific system prompt and user_id.
    """

    def __init__(self) -> None:
        self._model = OpenAIChatModel(
            model_name=settings.MODEL_NAME,
            api_key=settings.API_KEY,
            stream=True,
            client_kwargs={"base_url": settings.BASE_URL},
            generate_kwargs={"temperature": settings.MODEL_TEMPERATURE},
        )

        self._mcp_client: HttpStatelessClient | None = None
        if settings.MCP_ENABLED:
            mcp_url = _normalize_mcp_url(settings.MCP_SERVICE_URL)
            self._mcp_client = HttpStatelessClient(
                name="magic-sale-mcp",
                transport="streamable_http",
                url=mcp_url,
            )

        # Detect skills directory
        self._skills_dir: pathlib.Path | None = None
        skills_dir = pathlib.Path(__file__).resolve().parents[2] / "skills"
        if skills_dir.is_dir():
            self._skills_dir = skills_dir
            logger.info("skills_dir_detected", extra={"skills_dir": str(skills_dir)})

        # Load SkillTool once (singleton, reusable across requests)
        self._skill_tool: SkillTool | None = None
        if self._skills_dir is not None:
            self._skill_tool = SkillTool().load_skills(
                self._skills_dir, location="project",
            )
            loaded = [s.name for s in self._skill_tool.skills]
            logger.info(
                "skill_tool_loaded",
                extra={"skills": loaded, "count": len(loaded)},
            )

        # Pre-expand default skill so it's always in the system prompt
        self._default_skill_prompt: str = ""
        if self._skill_tool is not None:
            try:
                self._default_skill_prompt = self._skill_tool.invoke("sales-conversion")
                logger.info("default_skill_expanded", extra={"skill": "sales-conversion", "len": len(self._default_skill_prompt)})
            except ValueError:
                pass

        logger.info(
            "model_client_initialised",
            extra={
                "model": settings.MODEL_NAME,
                "temperature": settings.MODEL_TEMPERATURE,
                "base_url": settings.BASE_URL,
                "mcp_enabled": settings.MCP_ENABLED,
                "skills_enabled": self._skill_tool is not None,
            },
        )

    async def build_agent(self, system_prompt: str, user_id: str) -> ReActAgent:
        """
        Create a new `ReActAgent` for a single request lifecycle.

        A new Agent is created per-request so that the `system_prompt` is
        injected fresh each time (personalised per user_id from prompt-service).
        The underlying model and SkillTool are reused across requests.

        Args:
            system_prompt: The personalised system prompt for this user.
            user_id: The Zalo user ID — baked into tool wrappers for security.
        """
        # Per-request session state
        todo_manager = TodoWriteManager()
        context_store = RuntimeContextStore(todo_manager)

        # Mark sales-conversion as already active
        if self._default_skill_prompt:
            context_store.on_skill_loaded("sales-conversion")

        toolkit = Toolkit()

        # Register AgentSkill tools (Skill, ReadSkillFile, ListSkillFiles, TodoWrite)
        if self._skill_tool is not None:
            toolkit.register_tool_function(
                make_agentscope_skill_tool(self._skill_tool, context_store),
            )
            toolkit.register_tool_function(
                make_agentscope_read_skill_file_tool(self._skill_tool, context_store),
            )
            toolkit.register_tool_function(
                make_agentscope_list_skill_files_tool(self._skill_tool),
            )
            toolkit.register_tool_function(
                make_agentscope_todo_write_tool(todo_manager),
            )

        # Register MCP tools with user_id injection (UNCHANGED)
        if self._mcp_client is not None:
            preset_kwargs: dict[str, dict[str, Any]] = {
                tool_name: {"user_id": user_id}
                for tool_name in _TOOLS_WITH_USER_ID
            }
            await toolkit.register_mcp_client(
                self._mcp_client,
                preset_kwargs_mapping=preset_kwargs,
            )
            logger.info(
                "mcp_tools_registered",
                extra={
                    "user_id": user_id,
                    "injected_tools": list(_TOOLS_WITH_USER_ID),
                    "all_tools": list(toolkit.tools.keys()),
                },
            )

        # Build full system prompt: auto-inject sales-conversion skill
        # so the model ALWAYS follows the consultation pipeline.
        full_prompt = system_prompt
        if self._default_skill_prompt:
            full_prompt += (
                "\n\n"
                "=== QUY TRÌNH BÁN HÀNG (BẮT BUỘC) ===\n"
                "Skill sales-conversion đã được load sẵn. LUÔN tuân theo quy trình dưới đây.\n"
                "Dùng ReadSkillFile(skill_name=\"sales-conversion\", file_path=\"resources/XX.md\") "
                "để đọc chi tiết từng phase.\n\n"
                f"{self._default_skill_prompt}\n\n"
                "=== KẾT THÚC QUY TRÌNH ===\n"
            )
        if self._skill_tool is not None:
            skill_description = self._skill_tool._build_description()
            full_prompt += f"\n\n{skill_description}"

        # Agent with RuntimeContextMemory for session state tracking
        agent = ReActAgent(
            name="MagicSaleBot",
            sys_prompt=full_prompt,
            model=self._model,
            formatter=OpenAIChatFormatter(),
            toolkit=toolkit,
            memory=RuntimeContextMemory(context_store),
            parallel_tool_calls=False,
            print_hint_msg=False,
        )

        return agent
