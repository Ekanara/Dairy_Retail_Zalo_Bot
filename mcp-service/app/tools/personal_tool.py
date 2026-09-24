"""
personal_tool.py — MCP Tool: view + edit USER.md / SOUL.md / MEMORY.md per-user
                   thông qua prompt-service API.

Supports 4 commands (inspired by Claude Code's Edit tool):
  - view        → đọc nội dung hiện tại (có đánh số dòng)
  - str_replace → tìm old_str (exact, unique), thay bằng new_str
  - append      → thêm nội dung vào cuối file
  - delete      → tìm old_str (exact, unique), xóa đoạn đó
"""
import time
from typing import Literal

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_TOOL_NAME = "edit_personal_profile"

# Mapping tên file → path segment trong prompt-service API
_FILE_TO_ENDPOINT: dict[str, str] = {
    "USER.md": "user",
    "SOUL.md": "soul",
    "MEMORY.md": "memory",
}


class ProfileEditResult(BaseModel):
    """Kết quả trả về sau khi view/edit file cá nhân."""
    status: Literal["success", "error"]
    command: str
    file_name: str
    message: str
    content: str | None = None
    line_count: int | None = None


async def view_profile_impl(
    user_id: str,
    file_name: Literal["USER.md", "SOUL.md", "MEMORY.md"],
) -> ProfileEditResult:
    """Đọc nội dung hiện tại của file, trả kèm line numbers."""
    t0 = time.monotonic()
    endpoint = _FILE_TO_ENDPOINT.get(file_name)
    if endpoint is None:
        return ProfileEditResult(
            status="error", command="view", file_name=file_name,
            message=f"Unknown file_name '{file_name}'. Expected: USER.md, SOUL.md, MEMORY.md",
        )

    url = f"{settings.PROMPT_SERVICE_URL}/prompts/{user_id}/{endpoint}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("profile_view_http_error", extra={
                "tool_name": _TOOL_NAME, "user_id": user_id,
                "file_name": file_name, "status_code": exc.response.status_code,
            })
            return ProfileEditResult(
                status="error", command="view", file_name=file_name,
                message=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.RequestError as exc:
            logger.error("profile_view_request_error", extra={
                "tool_name": _TOOL_NAME, "user_id": user_id,
                "file_name": file_name, "error": str(exc),
            })
            raise

    data = resp.json()
    content_numbered = data.get("content_numbered", "")
    line_count = data.get("line_count", 0)

    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info("profile_view_done", extra={
        "tool_name": _TOOL_NAME, "user_id": user_id,
        "file_name": file_name, "line_count": line_count,
        "duration_ms": duration_ms,
    })

    return ProfileEditResult(
        status="success", command="view", file_name=file_name,
        message=f"Showing {file_name} ({line_count} lines)",
        content=content_numbered,
        line_count=line_count,
    )


async def edit_profile_impl(
    user_id: str,
    file_name: Literal["USER.md", "SOUL.md", "MEMORY.md"],
    command: Literal["str_replace", "append", "delete"],
    content: str = "",
    old_str: str | None = None,
    new_str: str | None = None,
) -> ProfileEditResult:
    """Chỉnh sửa file cá nhân: str_replace, append, hoặc delete."""
    t0 = time.monotonic()
    endpoint = _FILE_TO_ENDPOINT.get(file_name)
    if endpoint is None:
        return ProfileEditResult(
            status="error", command=command, file_name=file_name,
            message=f"Unknown file_name '{file_name}'. Expected: USER.md, SOUL.md, MEMORY.md",
        )

    # Build PATCH payload
    payload: dict[str, str | None] = {"mode": command}
    if command == "append":
        payload["content"] = content
    elif command == "str_replace":
        payload["old_str"] = old_str
        payload["new_str"] = new_str
    elif command == "delete":
        payload["old_str"] = old_str

    url = f"{settings.PROMPT_SERVICE_URL}/prompts/{user_id}/{endpoint}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.patch(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            logger.error("profile_edit_http_error", extra={
                "tool_name": _TOOL_NAME, "user_id": user_id,
                "file_name": file_name, "command": command,
                "status_code": exc.response.status_code,
                "response_body": detail,
            })
            return ProfileEditResult(
                status="error", command=command, file_name=file_name,
                message=detail,
            )
        except httpx.RequestError as exc:
            logger.error("profile_edit_request_error", extra={
                "tool_name": _TOOL_NAME, "user_id": user_id,
                "file_name": file_name, "command": command,
                "error": str(exc),
            })
            raise

    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info("profile_edit_done", extra={
        "tool_name": _TOOL_NAME, "user_id": user_id,
        "file_name": file_name, "command": command,
        "duration_ms": duration_ms,
    })

    return ProfileEditResult(
        status="success", command=command, file_name=file_name,
        message=f"Successfully applied '{command}' to {file_name}",
    )
