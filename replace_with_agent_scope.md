# AgentScope Migration Guide

> **Mục tiêu:** Thay thế `pydantic-ai` + `pydantic-ai-skills` bằng `agentscope` để hỗ trợ native Skills tốt hơn.

---

## 1. Tổng quan so sánh

| Tính năng | pydantic-ai (hiện tại) | agentscope (thay thế) |
|---|---|---|
| Agent runner | `Agent` (pydantic-ai) | `ReActAgent` (agentscope) |
| MCP client | `MCPServerStreamableHTTP` | `HttpStatelessClient` / `HttpStatefulClient` |
| Skills | `SkillsToolset` (pydantic-ai-skills, 3rd party) | `toolkit.register_agent_skill()` (built-in) |
| Tool registration | `toolsets=[...]` trong `Agent()` | `Toolkit + toolkit.register_tool_function()` |
| Conversation history | `ModelRequest` / `ModelResponse` objects | `Msg` list (InMemoryMemory) |
| Streaming | `agent.run_stream()` | `agent.run_stream()` (tương tự) |
| Model | `OpenAIChatModel` + `OpenAIProvider` | `OpenAIChatModel` (agentscope) |
| User ID injection | `RunContext[dict]` + `process_tool_call` hook | Custom tool wrapper / middleware |

---

## 2. Hướng dẫn AgentScope: Skills & Tools

### 2.1 Cài đặt

```bash
pip install agentscope
# Hoặc nếu cần MCP support
pip install "agentscope[mcp]"
```

### 2.2 Toolkit — Đăng ký Tool Function

Tool functions là **plain async Python functions** với docstring rõ ràng.  
AgentScope tự động trích xuất signature và docstring thành JSON schema cho LLM.

```python
from agentscope.tool import Toolkit

toolkit = Toolkit()

# Đăng ký một hàm Python thường làm tool
async def search_products(query: str, limit: int = 5) -> list[dict]:
    """Tìm sản phẩm theo từ khoá (ILIKE). Rút gọn query thành 2-4 keyword."""
    results = await search_keyword_impl(query, limit)
    return [r.model_dump() for r in results]

toolkit.register_tool_function(search_products)

# Hoặc dùng built-in tools
from agentscope.tool import execute_shell_command, view_text_file
toolkit.register_tool_function(execute_shell_command)
toolkit.register_tool_function(view_text_file)
```

### 2.3 Agent Skill — Cách AgentScope đọc Skill

**Cấu trúc một skill folder:**

```
skills/
└── sales-conversion/
    ├── SKILL.md          ← Mô tả skill + hướng dẫn cho agent
    └── resources/
        ├── 01-opening.md
        ├── 02-discovery.md
        ├── 03-support.md
        ├── 04-objection-handling.md
        └── 05-closing.md
```

**`SKILL.md` cần có YAML frontmatter:**

```markdown
---
name: sales-conversion
description: Kịch bản bán sữa theo từng bước hội thoại
---

## Cách dùng
- Gọi view_text_file('resources/01-opening.md') để đọc kịch bản opening
- Gọi view_text_file('resources/02-discovery.md') để khai thác nhu cầu
...
```

**Đăng ký skill vào Toolkit:**

```python
from agentscope.tool import Toolkit, view_text_file

toolkit = Toolkit()

# BẮT BUỘC: Agent cần có tool đọc file để dùng skill
toolkit.register_tool_function(view_text_file)

# Đăng ký skill folder — AgentScope tự đọc SKILL.md và inject vào system prompt
toolkit.register_agent_skill("./skills/sales-conversion")
```

> **Lưu ý quan trọng:** Skill trong AgentScope = một folder chứa `SKILL.md`.
> Agent sẽ tự đọc `SKILL.md` khi cần, sau đó dùng `view_text_file` để đọc các file resource.
> Không cần `load_skill` hay `read_skill_resource` riêng biệt như pydantic-ai-skills.

### 2.4 MCP Client — Kết nối FastMCP server

AgentScope cung cấp 2 loại MCP client:

| Client | Khi dùng |
|---|---|
| `HttpStatelessClient` | Mỗi request là độc lập, không giữ session (phù hợp nhất cho microservice) |
| `HttpStatefulClient` | Giữ 1 session lâu dài (dùng khi MCP server cần state giữa các lần gọi) |

**Cách dùng HttpStatelessClient:**

```python
from agentscope.mcp import HttpStatelessClient
from agentscope.tool import Toolkit

toolkit = Toolkit()

# Kết nối tới mcp-service (FastMCP server)
mcp_client = HttpStatelessClient(
    name="magic-sale-mcp",
    transport="streamable_http",
    url="http://localhost:8006/mcp",
)

# Option A: Add toàn bộ tools từ MCP server vào toolkit
await toolkit.add_mcp_tools(mcp_client)

# Option B: Chỉ lấy một tool cụ thể
search_func = await mcp_client.get_callable_function("search_keyword")
result = await search_func(query="sữa cho bé", limit=5)
toolkit.register_tool_function(search_func)
```

### 2.5 Tạo ReActAgent

```python
import os
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit, view_text_file
from agentscope.mcp import HttpStatelessClient

async def build_agent(system_prompt: str) -> ReActAgent:
    toolkit = Toolkit()

    # 1. Skill: yêu cầu view_text_file để agent đọc skill resources
    toolkit.register_tool_function(view_text_file)
    toolkit.register_agent_skill("./skills/sales-conversion")

    # 2. MCP tools từ mcp-service
    mcp_client = HttpStatelessClient(
        name="magic-sale-mcp",
        transport="streamable_http",
        url="http://localhost:8006/mcp",
    )
    await toolkit.add_mcp_tools(mcp_client)

    # 3. Model (OpenAI-compatible)
    model = OpenAIChatModel(
        config_name="openai-compatible",
        model_name=os.environ["MODEL_NAME"],
        api_key=os.environ["API_KEY"],
        client_args={"base_url": os.environ["BASE_URL"]},
        generate_args={"temperature": 0.3},
    )

    # 4. Agent
    agent = ReActAgent(
        name="MagicSaleBot",
        sys_prompt=system_prompt,
        model=model,
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )
    return agent


async def chat(agent: ReActAgent, user_message: str) -> str:
    msg = Msg("user", user_message, role="user")
    response = await agent(msg)
    return response.content
```

### 2.6 Streaming

```python
async def chat_stream(agent: ReActAgent, user_message: str):
    """Yield text chunks từ agent response."""
    msg = Msg("user", user_message, role="user")
    async for chunk in agent.run_stream(msg):
        if chunk.content:
            yield chunk.content
```

### 2.7 User ID Injection (thay thế `_inject_user_id_hook`)

AgentScope không có `process_tool_call` hook như pydantic-ai.
Cách đúng: **tạo wrapper function** inject `user_id` tại thời điểm đăng ký tool.

```python
async def build_toolkit_with_user_id(user_id: str) -> Toolkit:
    """Tạo Toolkit với user_id đã được baked-in cho mỗi request."""
    toolkit = Toolkit()

    # Lấy callable function từ MCP
    mcp_client = HttpStatelessClient(
        name="magic-sale-mcp",
        transport="streamable_http",
        url="http://localhost:8006/mcp",
    )
    create_order_raw = await mcp_client.get_callable_function("create_order")
    view_profile_raw = await mcp_client.get_callable_function("view_personal_profile")
    edit_profile_raw = await mcp_client.get_callable_function("edit_personal_profile")

    # Wrap để inject user_id
    async def create_order(items: list, customer_name: str, customer_email: str, customer_phone: str) -> dict:
        """Tạo đơn hàng với nhiều sản phẩm + gửi email xác nhận."""
        return await create_order_raw(user_id=user_id, items=items,
                                     customer_name=customer_name,
                                     customer_email=customer_email,
                                     customer_phone=customer_phone)

    async def view_personal_profile(file_name: str) -> dict:
        """Xem nội dung file cá nhân user. BẮT BUỘC gọi trước str_replace/delete."""
        return await view_profile_raw(user_id=user_id, file_name=file_name)

    async def edit_personal_profile(file_name: str, command: str,
                                    content: str = "", old_str: str = None, new_str: str = None) -> dict:
        """Chỉnh sửa file cá nhân user."""
        return await edit_profile_raw(user_id=user_id, file_name=file_name,
                                      command=command, content=content,
                                      old_str=old_str, new_str=new_str)

    toolkit.register_tool_function(create_order)
    toolkit.register_tool_function(view_personal_profile)
    toolkit.register_tool_function(edit_personal_profile)

    # Thêm các tools khác không cần user_id
    await toolkit.add_mcp_tools(mcp_client,
        exclude=["create_order", "view_personal_profile", "edit_personal_profile"])

    return toolkit
```

---

## 3. Kế hoạch Migration — Code cần đổi

### 3.1 Sơ đồ kiến trúc hiện tại vs mới

```
HIỆN TẠI (pydantic-ai)          →  MỚI (agentscope)
─────────────────────────────       ─────────────────────────────
models-service/
  app/clients/model_client.py       app/clients/model_client.py  ← THAY ĐỔI CHÍNH
    Agent (pydantic-ai)               ReActAgent (agentscope)
    MCPServerStreamableHTTP           HttpStatelessClient
    SkillsToolset                     toolkit.register_agent_skill()
    OpenAIChatModel + OpenAIProvider  OpenAIChatModel (agentscope)
    _inject_user_id_hook              wrapper functions per request

  app/services/model_service.py      app/services/model_service.py  ← SỬA NHỎ
    ModelMessage, ModelRequest        Msg list (InMemoryMemory)
    ModelResponse, TextPart           agent.memory.add(msg)
    agent.run() / run_stream()        agent(msg) / agent.run_stream()
    result.usage().input_tokens       (xem note)
    result.output                     response.content

requirements.txt (models-service)    requirements.txt  ← ĐỔI PACKAGE
  pydantic-ai>=1.0.0                  agentscope
  pydantic-ai-skills                  (không cần thêm gì)
```

### 3.2 File cần thay đổi

#### `models-service/app/clients/model_client.py` — **THAY HOÀN TOÀN**

| Dòng hiện tại | Thay bằng |
|---|---|
| `from pydantic_ai import Agent, RunContext` | `from agentscope.agent import ReActAgent` |
| `from pydantic_ai.mcp import MCPServerStreamableHTTP` | `from agentscope.mcp import HttpStatelessClient` |
| `from pydantic_ai.models.openai import OpenAIChatModel` | `from agentscope.model import OpenAIChatModel` |
| `from pydantic_ai.providers.openai import OpenAIProvider` | (bỏ — đưa vào OpenAIChatModel config) |
| `from pydantic_ai_skills import SkillsToolset` | `from agentscope.tool import Toolkit, view_text_file` |
| `MCPServerStreamableHTTP(url=..., process_tool_call=hook)` | `HttpStatelessClient(name=..., url=...)` |
| `SkillsToolset(directories=[...])` | `toolkit.register_agent_skill("./skills/sales-conversion")` |
| `Agent(model=..., toolsets=[...])` | `ReActAgent(name=..., model=..., toolkit=..., memory=...)` |
| `@agent.instructions` → inject skills | (built-in trong AgentScope) |
| Class `ModelClient.build_agent()` | Async `build_agent(system_prompt, user_id)` |

**Lưu ý thiết kế:** Vì AgentScope không có context deps như pydantic-ai, `ModelClient` phải thay đổi `build_agent()` thành `async` và nhận thêm `user_id` để tạo wrapper tools.

#### `models-service/app/services/model_service.py` — **SỬA CÁC PHẦN QUAN TRỌNG**

| Thành phần | Hiện tại | Thay bằng |
|---|---|---|
| Imports | `from pydantic_ai.messages import ModelMessage, ModelRequest,...` | `from agentscope.message import Msg` |
| `_build_message_history()` | Tạo `ModelRequest`/`ModelResponse` | Tạo list `Msg` để nạp vào `agent.memory` |
| `agent.run(user_prompt, message_history=..., deps=...)` | Như cũ | `await agent(Msg("user", user_prompt))` với memory đã load sẵn |
| `agent.run_stream(...)` | Context manager | `async for chunk in agent.run_stream(msg)` |
| `result.output` | String | `response.content` |
| `result.usage().input_tokens` | pydantic-ai UsageInfo | Tuỳ model — có thể không có trực tiếp |
| `result.all_messages()` → log tool calls | pydantic-ai messages | `agent.memory.get_memory()` |

#### `models-service/requirements.txt` — **XOÁ/THÊM PACKAGE**

```diff
- pydantic-ai>=1.0.0
- pydantic-ai-skills
+ agentscope
```

#### Không cần thay đổi

| File/Service | Lý do |
|---|---|
| `mcp-service/app/server.py` | Vẫn dùng FastMCP — agentscope kết nối qua `HttpStatelessClient` |
| `mcp-service/app/tools/*.py` | Tool implementations không đổi |
| `chat-service/` | Không liên quan |
| `zalo-service/` | Không liên quan |
| `prompt-service/` | Không liên quan |

### 3.3 Thứ tự thực hiện migration

```
Bước 1: Cài đặt agentscope
   pip install agentscope

Bước 2: Viết lại model_client.py
   - Xoá pydantic-ai imports
   - Thêm agentscope imports
   - Đổi ModelClient.__init__() để tạo OpenAIChatModel (agentscope style)
   - Đổi ModelClient.build_agent() thành async, nhận thêm user_id
   - Tạo Toolkit với skill + MCP tools + user_id injection wrappers

Bước 3: Sửa model_service.py
   - Xoá pydantic_ai.messages imports
   - Đổi _build_message_history() → load vào agent.memory
   - Đổi agent.run() → await agent(Msg(...))
   - Đổi agent.run_stream() → async for chunk in agent.run_stream(msg)
   - Đổi result.output → response.content
   - Đổi result.usage() → None hoặc custom tracking

Bước 4: Update requirements.txt
   - Xoá pydantic-ai, pydantic-ai-skills
   - Thêm agentscope

Bước 5: Kiểm tra SKILL.md trong skills/sales-conversion/
   - Đảm bảo có YAML frontmatter (name, description)
   - Đảm bảo có nội dung hướng dẫn agent dùng view_text_file

Bước 6: Test
   curl -X POST http://localhost:8000/chat \
     -d '{"user_id": "test_user", "messages": [{"role": "user", "content": "Xin chào"}]}'
```

### 3.4 Điểm rủi ro cần chú ý

| Rủi ro | Chi tiết | Giải pháp |
|---|---|---|
| Token usage tracking | agentscope không expose `usage()` giống pydantic-ai | Dùng model callbacks hoặc bỏ tracking tạm thời |
| Streaming format | agentscope streaming khác pydantic-ai | Test kỹ SSE format yield ra |
| Memory management | agentscope `InMemoryMemory` giữ memory trong object → per-request agent phải tạo mới mỗi lần | Tạo `new ReActAgent()` mỗi request hoặc clear memory trước mỗi chat |
| SKILL.md format | AgentScope yêu cầu YAML frontmatter cụ thể | Kiểm tra và cập nhật `skills/sales-conversion/SKILL.md` |
| `add_mcp_tools` async | Phải `await` khi build toolkit → `build_agent()` phải là `async` | Đổi toàn bộ call chain thành async |

---

## 4. Tham khảo AgentScope

- **GitHub:** https://github.com/agentscope-ai/agentscope
- **Skill example:** `examples/functionality/agent_skill/main.py`
- **MCP example:** `from agentscope.mcp import HttpStatelessClient`
- **ReActAgent:** `from agentscope.agent import ReActAgent`
- **Toolkit:** `from agentscope.tool import Toolkit`
