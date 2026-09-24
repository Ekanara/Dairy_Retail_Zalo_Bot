"""
Zalo Bot SDK client wrapper (compatible with trash/app_fake flow).

Uses `zalo_bot` SDK methods:
  - get_update(timeout=...)
  - send_message(chat_id=..., text=...)
"""

import inspect
from typing import Any

from app.core.config import settings
from app.core.logger import get_logger, mask_token

logger = get_logger("zalo-client")


class ZaloClient:
    """Thin async wrapper around the `zalo_bot` SDK."""

    def __init__(self) -> None:
        from zalo_bot import Bot

        self._bot = self._build_bot(
            bot_cls=Bot,
            token=settings.ZALO_BOT_TOKEN,
            base_url=settings.ZALO_BASE_URL,
        )

    @staticmethod
    def _build_bot(bot_cls: type, token: str, base_url: str) -> Any:
        params = inspect.signature(bot_cls.__init__).parameters
        kwargs: dict[str, Any] = {}

        if "token" in params:
            kwargs["token"] = token
        elif "bot_token" in params:
            kwargs["bot_token"] = token
        else:
            return bot_cls(token)

        if "base_url" in params:
            kwargs["base_url"] = base_url

        return bot_cls(**kwargs)

    async def get_updates(self, timeout: int = 10) -> list[dict[str, Any]]:
        """Fetch updates from bot API and normalize into list[dict]."""
        try:
            raw = await self._bot.get_update(timeout=timeout)
            return self._coerce_updates(raw)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "zalo_get_updates_error",
                extra={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "token_masked": mask_token(settings.ZALO_BOT_TOKEN),
                },
            )
            return []

    async def send_photo(self, user_id: str, image_url: str, caption: str = "") -> bool:
        """Send an image via bot SDK."""
        try:
            await self._bot.send_photo(chat_id=user_id, photo=image_url, caption=caption)
            logger.info(
                "photo_sent",
                extra={"user_id": user_id, "caption_len": len(caption)},
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "zalo_send_photo_error",
                extra={
                    "user_id": user_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            return False

    async def send_message(self, user_id: str, text: str) -> bool:
        """Send text via bot SDK using chat_id=user_id for compatibility."""
        try:
            await self._bot.send_message(chat_id=user_id, text=text)
            logger.info(
                "message_sent",
                extra={
                    "user_id": user_id,
                    "text_len": len(text),
                    "token_masked": mask_token(settings.ZALO_BOT_TOKEN),
                },
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "zalo_send_error",
                extra={
                    "user_id": user_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "token_masked": mask_token(settings.ZALO_BOT_TOKEN),
                },
            )
            return False

    @staticmethod
    def _coerce_updates(raw: Any) -> list[dict[str, Any]]:
        if raw is None:
            return []

        if hasattr(raw, "to_dict") and callable(raw.to_dict):
            raw = raw.to_dict()

        if isinstance(raw, list):
            output: list[dict[str, Any]] = []
            for item in raw:
                if hasattr(item, "to_dict") and callable(item.to_dict):
                    item = item.to_dict()
                if isinstance(item, dict):
                    output.append(item)
            return output

        if isinstance(raw, dict):
            if isinstance(raw.get("result"), list):
                output: list[dict[str, Any]] = []
                for item in raw["result"]:
                    if hasattr(item, "to_dict") and callable(item.to_dict):
                        item = item.to_dict()
                    if isinstance(item, dict):
                        output.append(item)
                return output
            if isinstance(raw.get("updates"), list):
                output = []
                for item in raw["updates"]:
                    if hasattr(item, "to_dict") and callable(item.to_dict):
                        item = item.to_dict()
                    if isinstance(item, dict):
                        output.append(item)
                return output
            return [raw]

        return []


# Module-level singleton — re-used across all requests
zalo_client = ZaloClient()
