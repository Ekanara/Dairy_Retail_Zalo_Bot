"""
main.py — Entry point cho mcp-service.

Chạy FastMCP server ở HTTP transport mặc định cho models-service gọi qua URL.
Có thể đổi sang stdio nếu cần.

Usage:
    # HTTP (mặc định)
    python main.py

    # Ép transport
    MCP_TRANSPORT=http python main.py
    MCP_TRANSPORT=stdio python main.py
"""
import os

from app.core.logger import get_logger
from app.server import mcp

logger = get_logger("main")


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "http").strip().lower()
    host = os.getenv("MCP_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.getenv("MCP_PORT", "8004"))

    logger.info(
        "mcp_service_starting",
        extra={
            "event": "startup",
            "transport": transport,
            "host": host,
            "port": port,
        },
    )

    if transport in {"http", "streamable-http"}:
        mcp.run(transport="streamable-http", host=host, port=port)
    elif transport == "stdio":
        # stdio transport — Pydantic AI dùng subprocess + stdin/stdout
        mcp.run(transport="stdio")
    else:
        logger.warning(
            "mcp_invalid_transport_fallback_http",
            extra={"provided_transport": transport},
        )
        mcp.run(transport="streamable-http", host=host, port=port)
