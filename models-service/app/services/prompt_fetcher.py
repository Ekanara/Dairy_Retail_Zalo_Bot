"""
prompt_fetcher — fetches per-user rendered system prompt from prompt-service.

GET {PROMPT_SERVICE_URL}/prompts/{user_id}

Response schema expected:
    {"system_prompt": "<rendered Jinja2 string>"}
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

async def fetch_system_prompt(user_id: str) -> str:
    """
    Fetch the personalised system prompt for *user_id* from prompt-service.

    Returns rendered system prompt.

    Raises RuntimeError when prompt-service is unavailable or response is invalid.
    """
    url = f"{settings.PROMPT_SERVICE_URL}/prompts/{user_id}"

    async with httpx.AsyncClient(timeout=settings.PROMPT_SERVICE_TIMEOUT) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data: dict = response.json()
            system_prompt: str = data["system_prompt"]
            logger.info(
                "prompt_fetched",
                extra={
                    "user_id": user_id,
                    "prompt_len": len(system_prompt),
                    "status_code": response.status_code,
                },
            )
            return system_prompt

        except httpx.HTTPStatusError as exc:
            logger.error(
                "prompt_fetch_http_error",
                extra={
                    "user_id": user_id,
                    "url": url,
                    "status_code": exc.response.status_code,
                    "detail": exc.response.text[:200],
                },
            )
            raise RuntimeError("prompt_fetch_http_error") from exc

        except httpx.ConnectError as exc:
            logger.error(
                "prompt_service_unreachable",
                extra={"user_id": user_id, "url": url, "error": str(exc)},
            )
            raise RuntimeError("prompt_service_unreachable") from exc

        except httpx.TimeoutException as exc:
            logger.error(
                "prompt_service_timeout",
                extra={
                    "user_id": user_id,
                    "url": url,
                    "timeout_seconds": settings.PROMPT_SERVICE_TIMEOUT,
                    "error": str(exc),
                },
            )
            raise RuntimeError("prompt_service_timeout") from exc

        except KeyError:
            logger.error(
                "prompt_response_missing_key",
                extra={"user_id": user_id, "url": url},
            )
            raise RuntimeError("prompt_response_missing_key")
