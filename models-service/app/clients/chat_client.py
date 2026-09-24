"""
HTTP client for chat-service (conversation history).

Provides async methods to:
- Load top-K conversation history for a user
- Save user messages
- Save assistant responses

Handles timeouts and connection pooling via httpx.AsyncClient.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logger import get_logger
from app.schemas.request import Message

logger = get_logger(__name__)


class ChatClient:
    """Async client for chat-service conversation history."""

    def __init__(self) -> None:
        self.base_url = settings.CHAT_SERVICE_URL
        self.timeout = settings.CHAT_SERVICE_TIMEOUT
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init HTTP client with connection pooling."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client (call during shutdown)."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("chat_client.closed")

    async def load_history(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """
        Load top-K conversation history for a user.

        Parameters
        ----------
        user_id : Zalo user ID (window_id)
        limit   : Max messages to fetch (default 50)

        Returns
        -------
        List of Message objects (oldest first, ready for message_history).

        Notes
        -----
        - Uses window_id (Zalo user ID) as the lookup key
        - Returns messages in DESC order from API, then reverses to ASC
        - Filters out 'system' messages (only keep 'user' and 'assistant')
        - Returns empty list on error (non-fatal)
        """
        client = await self._get_client()
        try:
            response = await client.get(
                "/chat/messages",
                params={"window_id": user_id, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()

            # Convert to Message objects, filter out system messages
            messages = [
                Message(role=msg["role"], content=msg["content"])
                for msg in data["messages"]
                if msg["role"] in ("user", "assistant")
            ]

            # Reverse to chronological order (API returns DESC)
            messages.reverse()

            logger.info(
                "chat_client.load_history",
                user_id=user_id,
                count=len(messages),
                from_cache=data.get("from_cache", False),
            )
            return messages

        except httpx.HTTPError as exc:
            logger.warning(
                "chat_client.load_history_failed",
                user_id=user_id,
                error=str(exc),
            )
            return []  # Non-fatal: continue without history

    async def save_message(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> bool:
        """
        Save a single message to chat history.

        Parameters
        ----------
        user_id  : Zalo user ID (window_id)
        role     : 'user', 'assistant', or 'system'
        content  : Message text
        metadata : Optional metadata dict

        Returns
        -------
        True if saved successfully, False on error.
        """
        client = await self._get_client()
        try:
            response = await client.post(
                "/chat/messages",
                json={
                    "window_id": user_id,
                    "role": role,
                    "content": content,
                    "metadata": metadata or {},
                },
            )
            response.raise_for_status()

            logger.info(
                "chat_client.save_message",
                user_id=user_id,
                role=role,
                content_len=len(content),
            )
            return True

        except httpx.HTTPError as exc:
            logger.error(
                "chat_client.save_message_failed",
                user_id=user_id,
                role=role,
                error=str(exc),
            )
            return False  # Non-fatal: continue even if save fails


# Global singleton instance
chat_client = ChatClient()
