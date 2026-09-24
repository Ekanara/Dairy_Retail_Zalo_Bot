"""
model_service — core business logic for chat and streaming chat.

Flow
----
1. Fetch personalised system prompt from prompt-service (with fallback).
2. Build a per-request AgentScope ReActAgent injected with the system prompt.
3. Load conversation history into the agent's InMemoryMemory.
4. Run the agent (non-streaming OR streaming SSE generator).
5. Log structured JSON with user_id, model, latency_ms, token counts.

Conversation history mapping
-----------------------------
ChatRequest.messages    →  agentscope Msg objects loaded into agent.memory
role = "user"           →  Msg(name="user", content=..., role="user")
role = "assistant"      →  Msg(name="MagicSaleBot", content=..., role="assistant")
role = "system"         →  skipped (system prompt comes from prompt-service)

The *last* user message is passed to agent.reply(); all preceding messages
are loaded into the agent's memory for context.
"""

from __future__ import annotations

import asyncio
import json
import string
import time
import unicodedata
from typing import AsyncGenerator

from agentscope.message import Msg

from app.clients.model_client import ModelClient
from app.core.config import settings
from app.core.logger import get_logger
from app.schemas.request import ChatRequest, Message
from app.schemas.response import ChatResponse, UsageInfo

logger = get_logger(__name__)

# One ModelClient per process — reuses the underlying HTTP connection pool.
_model_client = ModelClient()


def _inject_runtime_user_id(system_prompt: str, user_id: str) -> str:
    """
    Attach a hard runtime constraint so tool calls use the exact Zalo user_id.
    """
    guard = (
        "\n\n"
        "RUNTIME TOOL CONSTRAINT:\n"
        f"- Current user_id is exactly: {user_id}\n"
        "- For ANY tool call that has a `user_id` argument (e.g. view_personal_profile, edit_personal_profile, create_order),\n"
        "  you MUST pass exactly this runtime user_id and nothing else.\n"
        "- Do NOT transform, shorten, hash, infer, or generate a custom user_id.\n"
        "- Do NOT use placeholders like 'user', 'guest', 'customer', 'unknown'.\n"
        "- NEVER use fallback ids such as 'default', 'user', 'unknown', or any display name.\n"
        "- Before sending a tool call, verify `tool_args.user_id` EXACTLY equals the runtime user_id above.\n"
        "- If you are not sure the user_id is exact, do not call the tool.\n"
    )
    return system_prompt + guard


# ── tool call logging ────────────────────────────────────────────────────────

_SKILL_TOOLS = {"Skill", "ReadSkillFile", "ListSkillFiles", "TodoWrite"}


def _iter_tool_calls(memory_messages: list[Msg]) -> list[dict]:
    """Extract tool_use blocks from assistant messages in memory."""
    calls: list[dict] = []
    for msg in memory_messages:
        if msg.role != "assistant":
            continue
        blocks = msg.get_content_blocks("tool_use") if hasattr(msg, "get_content_blocks") else []
        calls.extend(blocks)
    return calls



def _log_tool_calls(memory_messages: list[Msg], user_id: str) -> None:
    """Log all tool calls from agent memory for diagnostics."""
    for tool_call in _iter_tool_calls(memory_messages):
        tool_name = tool_call.get("name", "unknown")
        event_name = "skill_call" if tool_name in _SKILL_TOOLS else "tool_call"
        logger.info(
            event_name,
            extra={
                "user_id": user_id,
                "tool": tool_name,
                "tool_args": json.dumps(tool_call.get("input", {}), ensure_ascii=False),
            },
        )


# ── helpers ──────────────────────────────────────────────────────────────────

_SHORT_CONFIRM_KEYWORDS = frozenset({
    "ok",
    "oke",
    "okay",
    "vâng",
    "vang",
    "dạ",
    "da",
    "ừ",
    "uh",
    "uk",
    "được",
    "duoc",
    "chốt",
    "chot",
    "lấy",
    "lay",
    "lon",
    "hộp",
    "hop",
    "thùng",
    "thung",
    "nhỏ",
    "nho",
    "lớn",
    "lon",
})

_SHORT_CONFIRM_FILLER = frozenset({
    "tôi",
    "toi",
    "mình",
    "minh",
    "em",
    "anh",
    "chị",
    "chi",
    "chọn",
    "chon",
    "xin",
    "vậy",
    "vay",
    "nha",
    "nhé",
    "nhe",
    "ạ",
    "a",
})

_SHORT_CONFIRM_HINT = (
    "\n\n"
    "[HƯỚNG DẪN NỘI BỘ: Đây là phản hồi ngắn theo ngữ cảnh câu hỏi ngay trước đó. "
    "Hãy coi như khách đã xác nhận lựa chọn, không lặp lại phần tư vấn cũ. "
    "Chuyển ngay sang bước kế tiếp của flow closing hoặc gọi tool cần thiết; "
    "nếu thiếu dữ liệu thì chỉ hỏi đúng 1 thông tin còn thiếu.]"
)


def _normalize_user_text(text: str) -> str:
    """Normalize user text for short-confirmation detection."""
    cleaned = text.strip().lower()
    if not cleaned:
        return ""

    punctuation = string.punctuation + "“”‘’…"
    trans_table = str.maketrans({ch: " " for ch in punctuation})
    cleaned = cleaned.translate(trans_table)
    return " ".join(cleaned.split())


def _is_short_confirmation(user_prompt: str) -> bool:
    """Detect short contextual confirmations like 'ok', 'lon', 'tôi chọn lon'."""
    normalized = _normalize_user_text(user_prompt)
    if not normalized:
        return False

    tokens = normalized.split()
    if len(tokens) > 5:
        return False

    meaningful_tokens = [token for token in tokens if token not in _SHORT_CONFIRM_FILLER]
    if not meaningful_tokens:
        return False

    return all(token in _SHORT_CONFIRM_KEYWORDS for token in meaningful_tokens)


def _extract_last_assistant_message(messages: list[Message]) -> str:
    """Get the most recent assistant message content from conversation history."""
    for msg in reversed(messages):
        if msg.role == "assistant":
            return msg.content
    return ""


_HEALTH_QUESTION_KEYWORDS = [
    "biếng ăn", "bieng an", "kén ăn", "ken an", "ăn uống", "an uong",
    "ốm vặt", "om vat", "sức khỏe", "suc khoe", "bệnh", "benh",
    "mệt", "met", "mỏi", "moi", "khó ngủ", "kho ngu", "xương khớp",
    "xuong khop", "tiểu đường", "tieu duong", "huyết áp", "huyet ap",
]

_NEGATIVE_HEALTH_ANSWERS = {
    "không", "khong", "ko", "k", "hong", "hông",
    "bình thường", "binh thuong", "bt",
    "khỏe", "khoe", "tốt", "tot",
    "không có", "khong co", "không bị", "khong bi",
}

_HEALTH_NEGATIVE_HINT = (
    "\n\n[HƯỚNG DẪN NỘI BỘ: Khách vừa trả lời câu hỏi sức khỏe = KHÔNG CÓ VẤN ĐỀ GÌ, "
    "người dùng BÌNH THƯỜNG, mục tiêu = BỔ SUNG DINH DƯỠNG CHUNG. "
    "ĐÃ ĐỦ 3/3 dữ kiện (ai + tuổi + sức khỏe bình thường). "
    "BẮT BUỘC: Gọi search tool NGAY (search_by_age hoặc search_keyword với brand phù hợp) "
    "rồi recommend sản phẩm CỤ THỂ (tên + giá) trong turn này. "
    "KHÔNG kết thúc hội thoại. KHÔNG chào lại. KHÔNG hỏi thêm. "
    "Load resource 03-support.md.]"
)

_WANTS_ALL_HINT = (
    "\n\n[HƯỚNG DẪN NỘI BỘ: Khách muốn TẤT CẢ / TOÀN DIỆN, không muốn chọn 1 mục tiêu cụ thể. "
    "BẮT BUỘC: Gọi search tool NGAY và recommend sản phẩm dinh dưỡng TOÀN DIỆN nhất "
    "(tên + giá). KHÔNG bảo khách chọn 1 mục tiêu. Load resource 03-support.md.]"
)

_WANTS_ALL_KEYWORDS = [
    "tất cả", "tat ca", "tất cả luôn", "cái gì cũng", "cai gi cung",
    "đủ thứ", "du thu", "gì cũng cần", "gi cung can",
]

_DISCOVERY_FORCE_HEALTH_HINT = (
    "\n\n[HƯỚNG DẪN NỘI BỘ — ƯU TIÊN TUYỆT ĐỐI: "
    "Khách vừa cho biết ĐỐI TƯỢNG + TUỔI nhưng CHƯA nói về sức khỏe/tình trạng/mục tiêu cụ thể. "
    "BẮT BUỘC: HỎI VỀ SỨC KHỎE TRƯỚC. "
    "NGHIÊM CẤM gọi search tools (search_keyword, search_by_age, search_by_segment, rag_hybrid_search). "
    "NGHIÊM CẤM gợi ý/nhắc tên sản phẩm. "
    "CHỈ load resource 02-discovery.md và hỏi 1 câu về sức khỏe. "
    "Ví dụ: 'Mẹ mình dạo này sức khỏe sao ạ? Có hay mỏi chân tay, khó ngủ, ăn uống kém không ạ?']"
)

# Keywords indicating user provided WHO + AGE info
_AGE_KEYWORDS = [
    "tuổi", "tuoi", "tháng tuổi", "thang tuoi",
]

_WHO_KEYWORDS = [
    "mẹ", "me", "ba", "bố", "bo", "con", "bé", "be", "cháu", "chau",
    "ông", "ong", "bà", "ba", "vợ", "vo", "chồng", "chong",
    "em bé", "em be", "bản thân", "ban than",
]


def _has_age_and_who(text: str) -> bool:
    """Check if text contains both a target person and age info."""
    lower = text.lower()
    has_age = any(kw in lower for kw in _AGE_KEYWORDS)
    has_who = any(kw in lower for kw in _WHO_KEYWORDS)
    return has_age and has_who


def _conversation_has_health_info(messages: list) -> bool:
    """Check if the conversation already contains health-related discussion."""
    for msg in messages:
        content = msg.content.lower() if hasattr(msg, 'content') else ""
        # Bot already asked about health
        if hasattr(msg, 'role') and msg.role == "assistant" and _is_health_question(content):
            return True
        # User mentioned health conditions
        if hasattr(msg, 'role') and msg.role == "user":
            health_terms = [
                "biếng ăn", "bieng an", "kén ăn", "ken an", "ốm", "om",
                "tiểu đường", "tieu duong", "xương khớp", "xuong khop",
                "mệt", "met", "mỏi", "moi", "khó ngủ", "kho ngu",
                "bình thường", "binh thuong", "khỏe", "khoe",
                "ăn uống kém", "an uong kem", "hay ốm", "hay om",
                "tăng cân", "tang can", "chiều cao", "chieu cao",
                "bổ sung dinh dưỡng", "bo sung dinh duong",
            ]
            if any(t in content for t in health_terms):
                return True
    return False


def _is_health_question(assistant_msg: str) -> bool:
    """Check if the assistant message was asking about health."""
    msg_lower = assistant_msg.lower()
    return any(kw in msg_lower for kw in _HEALTH_QUESTION_KEYWORDS)


def _is_negative_health_answer(user_prompt: str) -> bool:
    """Check if user response is a negative answer to a health question."""
    normalized = _normalize_user_text(user_prompt)
    return normalized in _NEGATIVE_HEALTH_ANSWERS or any(
        normalized.startswith(ans) for ans in _NEGATIVE_HEALTH_ANSWERS
    )


def _is_wants_all(user_prompt: str) -> bool:
    """Check if user wants everything/all goals."""
    lower = user_prompt.lower()
    return any(kw in lower for kw in _WANTS_ALL_KEYWORDS)


def _prepare_user_prompt_for_agent(user_prompt: str, history_messages: list[Message]) -> str:
    """
    Add a hidden contextual hint for short confirmations so the model
    progresses to the next step instead of repeating support text.
    Also handles negative health answers and 'wants all' responses.
    """
    last_assistant = _extract_last_assistant_message(history_messages)

    # PRIORITY: If user just provided WHO + AGE but conversation has no health info yet,
    # force bot to ask about health before recommending anything
    if _has_age_and_who(user_prompt) and not _conversation_has_health_info(history_messages):
        logger.info(
            "discovery_force_health",
            extra={"user_prompt": user_prompt, "hint": "force_health_question"},
        )
        return user_prompt + _DISCOVERY_FORCE_HEALTH_HINT

    # Check if user is answering a health question with "Không" / "Bình thường"
    if last_assistant and _is_health_question(last_assistant):
        if _is_negative_health_answer(user_prompt):
            logger.info(
                "health_negative_detected",
                extra={"user_prompt": user_prompt, "hint": "negative_health"},
            )
            return user_prompt + _HEALTH_NEGATIVE_HINT
        if _is_wants_all(user_prompt):
            logger.info(
                "wants_all_detected",
                extra={"user_prompt": user_prompt, "hint": "wants_all"},
            )
            return user_prompt + _WANTS_ALL_HINT

    if not _is_short_confirmation(user_prompt):
        return user_prompt

    if not last_assistant:
        return user_prompt

    return user_prompt + _SHORT_CONFIRM_HINT


def _build_memory_messages(messages: list[Message]) -> list[Msg]:
    """
    Convert ChatRequest messages (all but the last user turn) into
    agentscope `Msg` objects for multi-turn context.

    Only "user" and "assistant" roles are mapped; "system" messages
    are ignored (the system prompt is injected via Agent's sys_prompt arg).
    """
    history: list[Msg] = []
    for msg in messages:
        if msg.role == "user":
            history.append(Msg(name="user", content=msg.content, role="user"))
        elif msg.role == "assistant":
            history.append(Msg(name="MagicSaleBot", content=msg.content, role="assistant"))
        # role == "system" → skipped intentionally
    return history


def _extract_last_user_message(messages: list[Message]) -> str:
    """
    Return the content of the final user message.

    If no user message exists (edge-case), return an empty string so the
    agent still runs rather than raising an unhandled error.
    """
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


def _extract_text_content(msg: Msg) -> str:
    """Extract text content from an agentscope Msg."""
    if isinstance(msg.content, str):
        return msg.content
    if isinstance(msg.content, list):
        # Extract text blocks from content list
        text_parts = []
        for block in msg.content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "".join(text_parts)
    return str(msg.content) if msg.content else ""  # pragma: no cover


_META_CAPABILITY_MARKERS = frozenset({
    "bạn",
    "ban",
    "em",
    "bot",
    "nutribot",
})

_META_CAPABILITY_INTENTS = frozenset({
    "chức năng",
    "chuc nang",
    "làm được gì",
    "lam duoc gi",
    "có thể làm gì",
    "co the lam gi",
    "hỗ trợ gì",
    "ho tro gi",
    "giúp được gì",
    "giup duoc gi",
    "khả năng",
    "kha nang",
})

_PRODUCT_QUERY_HINTS = frozenset({
    "sữa",
    "sua",
    "ensure",
    "glucerna",
    "pediasure",
    "similac",
    "abbott",
})


def _strip_diacritics(text: str) -> str:
    """Return a lower-risk ASCII-like string for intent matching."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _is_meta_capability_query(user_prompt: str) -> bool:
    """Detect meta questions about bot capabilities/role, not product intent."""
    normalized = _normalize_user_text(user_prompt)
    if not normalized:
        return False

    normalized_ascii = _normalize_user_text(_strip_diacritics(user_prompt))

    # If the user is asking about a concrete product, keep normal sales flow.
    if any(hint in normalized or hint in normalized_ascii for hint in _PRODUCT_QUERY_HINTS):
        return False

    has_intent = any(
        intent in normalized or intent in normalized_ascii
        for intent in _META_CAPABILITY_INTENTS
    )
    if not has_intent:
        return False

    has_actor = any(
        marker in normalized or marker in normalized_ascii
        for marker in _META_CAPABILITY_MARKERS
    )

    # Accept short standalone capability queries even when actor is omitted.
    return has_actor or len(normalized.split()) <= 5


def _build_capability_reply() -> str:
    """Consistent response for capability questions."""
    return (
        "Dạ em là NutriBot bên Abbott ạ. "
        "Em có thể tư vấn sữa theo độ tuổi và tình trạng sức khỏe, "
        "giải đáp thông tin sản phẩm và giá, so sánh lựa chọn phù hợp, "
        "và hỗ trợ lên đơn khi anh/chị cần."
    )


# ── public API ───────────────────────────────────────────────────────────────


async def chat(request: ChatRequest) -> ChatResponse:
    """
    Non-streaming chat: return full assistant reply + token usage.
    """
    from app.services.prompt_fetcher import fetch_system_prompt  # lazy to avoid circular
    from app.clients.chat_client import chat_client  # lazy import

    start = time.monotonic()
    user_prompt = _extract_last_user_message(request.messages)

    if _is_meta_capability_query(user_prompt):
        assistant_content = _build_capability_reply()
        latency_ms = int((time.monotonic() - start) * 1000)
        usage = UsageInfo(prompt_tokens=0, completion_tokens=0)

        if settings.CHAT_HISTORY_ENABLED:
            await chat_client.save_message(
                user_id=request.user_id,
                role="user",
                content=user_prompt,
            )
            await chat_client.save_message(
                user_id=request.user_id,
                role="assistant",
                content=assistant_content,
                metadata={
                    "model": settings.MODEL_NAME,
                    "latency_ms": latency_ms,
                    "tokens": usage.total_tokens,
                    "meta_route": "capability_query",
                },
            )

        logger.info(
            "chat_meta_capability_answered",
            extra={"user_id": request.user_id, "prompt_len": len(user_prompt)},
        )
        return ChatResponse(
            message=Message(role="assistant", content=assistant_content),
            usage=usage,
        )

    system_prompt = _inject_runtime_user_id(
        await fetch_system_prompt(request.user_id),
        request.user_id,
    )
    agent = await _model_client.build_agent(system_prompt, request.user_id)

    # ── Load conversation history from chat-service ───────────────────────────
    if settings.CHAT_HISTORY_ENABLED:
        # Save user message BEFORE calling AI
        await chat_client.save_message(
            user_id=request.user_id,
            role="user",
            content=user_prompt,
        )

        # Load full history from chat-service (auto-cached)
        history_messages = await chat_client.load_history(request.user_id, limit=10)
        memory_msgs = _build_memory_messages(history_messages)
        # Use request.messages for hint detection (has full context even for new sessions)
        hint_context = request.messages if len(request.messages) > len(history_messages) else history_messages
        effective_user_prompt = _prepare_user_prompt_for_agent(user_prompt, hint_context)
        logger.info(
            "chat_history_loaded",
            extra={"user_id": request.user_id, "history_turns": len(memory_msgs)},
        )
    else:
        # Fallback: use history from request (old behavior)
        preceding: list[Message] = []
        last_user_idx = -1
        for i in range(len(request.messages) - 1, -1, -1):
            if request.messages[i].role == "user":
                last_user_idx = i
                break
        if last_user_idx > 0:
            preceding = request.messages[:last_user_idx]
        memory_msgs = _build_memory_messages(preceding)
        effective_user_prompt = _prepare_user_prompt_for_agent(user_prompt, preceding)

    if effective_user_prompt != user_prompt:
        hint_type = ("health_negative" if _HEALTH_NEGATIVE_HINT in effective_user_prompt
                      else "wants_all" if _WANTS_ALL_HINT in effective_user_prompt
                      else "short_confirm")
        logger.info(
            "prompt_hint_applied",
            extra={"user_id": request.user_id, "user_prompt": user_prompt, "hint_type": hint_type},
        )

    # Load history into agent memory
    if memory_msgs:
        await agent.memory.add(memory_msgs)

    logger.info(
        "chat_request",
        extra={
            "user_id": request.user_id,
            "model": settings.MODEL_NAME,
            "history_turns": len(memory_msgs),
            "prompt_len": len(user_prompt),
        },
    )

    # Run agent
    user_msg = Msg(name="user", content=effective_user_prompt, role="user")
    result = await agent.reply(user_msg)
    assistant_content = _extract_text_content(result)
    all_messages = await agent.memory.get_memory()


    # Log tool calls for diagnostics
    _log_tool_calls(all_messages, request.user_id)

    latency_ms = int((time.monotonic() - start) * 1000)

    # Token usage — agentscope doesn't expose usage directly like pydantic-ai
    usage = UsageInfo(prompt_tokens=0, completion_tokens=0)

    # ── Save assistant response to chat-service ───────────────────────────────
    if settings.CHAT_HISTORY_ENABLED:
        await chat_client.save_message(
            user_id=request.user_id,
            role="assistant",
            content=assistant_content,
            metadata={
                "model": settings.MODEL_NAME,
                "latency_ms": latency_ms,
                "tokens": usage.total_tokens,
            },
        )

    logger.info(
        "chat_completed",
        extra={
            "user_id": request.user_id,
            "model": settings.MODEL_NAME,
            "latency_ms": latency_ms,
            "token_count": usage.total_tokens,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
        },
    )

    return ChatResponse(
        message=Message(role="assistant", content=assistant_content),
        usage=usage,
    )


async def chat_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Streaming chat: yields SSE-formatted chunks.

    Each yielded string is a complete SSE line:
        data: {"delta": "<text>"}\n\n

    The terminal sentinel is:
        data: [DONE]\n\n

    Uses agentscope's msg_queue to capture streaming chunks from the
    ReActAgent as they are produced by the underlying model.
    """
    from app.services.prompt_fetcher import fetch_system_prompt  # lazy import
    from app.clients.chat_client import chat_client  # lazy import

    start = time.monotonic()
    user_prompt = _extract_last_user_message(request.messages)

    if _is_meta_capability_query(user_prompt):
        assistant_content = _build_capability_reply()
        latency_ms = int((time.monotonic() - start) * 1000)

        if settings.CHAT_HISTORY_ENABLED:
            await chat_client.save_message(
                user_id=request.user_id,
                role="user",
                content=user_prompt,
            )
            await chat_client.save_message(
                user_id=request.user_id,
                role="assistant",
                content=assistant_content,
                metadata={
                    "model": settings.MODEL_NAME,
                    "latency_ms": latency_ms,
                    "tokens": 0,
                    "streaming": True,
                    "meta_route": "capability_query",
                },
            )

        logger.info(
            "chat_stream_meta_capability_answered",
            extra={"user_id": request.user_id, "prompt_len": len(user_prompt)},
        )
        yield f"data: {json.dumps({'delta': assistant_content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    system_prompt = _inject_runtime_user_id(
        await fetch_system_prompt(request.user_id),
        request.user_id,
    )
    agent = await _model_client.build_agent(system_prompt, request.user_id)

    # ── Load conversation history from chat-service ───────────────────────────
    if settings.CHAT_HISTORY_ENABLED:
        # Save user message BEFORE calling AI
        await chat_client.save_message(
            user_id=request.user_id,
            role="user",
            content=user_prompt,
        )

        # Load full history from chat-service (auto-cached)
        history_messages = await chat_client.load_history(request.user_id, limit=10)
        memory_msgs = _build_memory_messages(history_messages)
        # Use request.messages for hint detection (has full context even for new sessions)
        hint_context = request.messages if len(request.messages) > len(history_messages) else history_messages
        effective_user_prompt = _prepare_user_prompt_for_agent(user_prompt, hint_context)
        logger.info(
            "chat_history_loaded",
            extra={"user_id": request.user_id, "history_turns": len(memory_msgs)},
        )
    else:
        # Fallback: use history from request (old behavior)
        preceding: list[Message] = []
        last_user_idx = -1
        for i in range(len(request.messages) - 1, -1, -1):
            if request.messages[i].role == "user":
                last_user_idx = i
                break
        if last_user_idx > 0:
            preceding = request.messages[:last_user_idx]
        memory_msgs = _build_memory_messages(preceding)
        effective_user_prompt = _prepare_user_prompt_for_agent(user_prompt, preceding)

    if effective_user_prompt != user_prompt:
        hint_type = ("health_negative" if _HEALTH_NEGATIVE_HINT in effective_user_prompt
                      else "wants_all" if _WANTS_ALL_HINT in effective_user_prompt
                      else "short_confirm")
        logger.info(
            "prompt_hint_applied",
            extra={"user_id": request.user_id, "user_prompt": user_prompt, "hint_type": hint_type},
        )

    # Load history into agent memory
    if memory_msgs:
        await agent.memory.add(memory_msgs)

    logger.info(
        "chat_stream_request",
        extra={
            "user_id": request.user_id,
            "model": settings.MODEL_NAME,
            "history_turns": len(memory_msgs),
            "prompt_len": len(user_prompt),
        },
    )

    # Enable msg_queue for streaming output capture
    queue: asyncio.Queue = asyncio.Queue()
    agent.set_msg_queue_enabled(True, queue=queue)

    # Run agent.reply in background, consume queue for SSE chunks
    user_msg = Msg(name="user", content=effective_user_prompt, role="user")

    reply_task = asyncio.create_task(agent.reply(user_msg))

    total_chunks = 0
    streamed_content: list[str] = []
    prev_text = ""

    try:
        while True:
            try:
                # Wait for queue items with timeout to detect completion
                msg_item, is_last, _speech = await asyncio.wait_for(
                    queue.get(), timeout=0.1,
                )

                # Extract text from streaming msg
                current_text = _extract_text_content(msg_item)

                # Only yield the delta (new text since last chunk)
                if len(current_text) > len(prev_text):
                    delta = current_text[len(prev_text):]
                    prev_text = current_text
                    total_chunks += 1
                    streamed_content.append(delta)
                    yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"

                if is_last:
                    # Final message — check if reply_task is done
                    if reply_task.done():
                        break
            except asyncio.TimeoutError:
                if reply_task.done():
                    # Drain remaining items
                    while not queue.empty():
                        msg_item, is_last, _speech = queue.get_nowait()
                        current_text = _extract_text_content(msg_item)
                        if len(current_text) > len(prev_text):
                            delta = current_text[len(prev_text):]
                            prev_text = current_text
                            total_chunks += 1
                            streamed_content.append(delta)
                            yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
                    break
    except Exception:
        if not reply_task.done():
            reply_task.cancel()
        raise

    # Await the reply task to get the final result and propagate any errors
    result = await reply_task

    # If no chunks were streamed (e.g. non-streaming model), send full content
    if total_chunks == 0:
        full_text = _extract_text_content(result)
        if full_text:
            streamed_content.append(full_text)
            yield f"data: {json.dumps({'delta': full_text}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"

    # Log tool calls for diagnostics
    all_messages = await agent.memory.get_memory()
    _log_tool_calls(all_messages, request.user_id)

    latency_ms = int((time.monotonic() - start) * 1000)

    # Token usage — agentscope doesn't expose usage directly
    token_count = 0
    prompt_tokens = 0
    completion_tokens = 0

    # ── Save assistant response to chat-service ───────────────────────────────
    if settings.CHAT_HISTORY_ENABLED:
        assistant_content = "".join(streamed_content)
        await chat_client.save_message(
            user_id=request.user_id,
            role="assistant",
            content=assistant_content,
            metadata={
                "model": settings.MODEL_NAME,
                "latency_ms": latency_ms,
                "tokens": token_count,
                "streaming": True,
            },
        )

    logger.info(
        "chat_stream_completed",
        extra={
            "user_id": request.user_id,
            "model": settings.MODEL_NAME,
            "latency_ms": latency_ms,
            "total_chunks": total_chunks,
            "token_count": token_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    )
