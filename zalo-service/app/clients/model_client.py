"""
HTTP client for models-service.

Calls POST /chat on models-service and returns the AI reply text.
All errors are caught specifically — never bare except — and a
Vietnamese fallback string is returned so the user always gets a reply.
"""

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("model-client")

# models-service can be slow when running a local GPU model
_REQUEST_TIMEOUT = 60.0


class ModelServiceClient:
    """Async HTTP client that calls models-service POST /chat."""

    async def chat(self, user_id: str, messages: list[dict]) -> str:
        """
        Send *messages* for *user_id* to models-service and return the
        assistant reply text.

        On any error a Vietnamese fallback message is returned so the
        downstream caller (chat_service) can still reply to the user.
        """
        url = f"{settings.MODEL_SERVICE_URL}/chat"
        request_body = {
            "user_id": user_id,
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(url, json=request_body)
                response.raise_for_status()
                data = response.json()
                # Expected shape: {"message": {"role": "assistant", "content": "..."}}
                return data["message"]["content"]

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "model_service_http_error",
                    extra={
                        "user_id": user_id,
                        "status_code": exc.response.status_code,
                        "response_body": exc.response.text[:200],
                        "url": url,
                    },
                )
                return "Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau."

            except httpx.TimeoutException as exc:
                logger.error(
                    "model_service_timeout",
                    extra={
                        "user_id": user_id,
                        "timeout_seconds": _REQUEST_TIMEOUT,
                        "error": str(exc),
                    },
                )
                return "Xin lỗi, hệ thống đang xử lý quá lâu. Vui lòng thử lại sau."

            except httpx.ConnectError as exc:
                logger.error(
                    "model_service_unreachable",
                    extra={
                        "user_id": user_id,
                        "url": url,
                        "error": str(exc),
                    },
                )
                return "Xin lỗi, dịch vụ tạm thời không khả dụng. Vui lòng thử lại sau."

            except KeyError as exc:
                logger.error(
                    "model_service_response_malformed",
                    extra={
                        "user_id": user_id,
                        "missing_key": str(exc),
                    },
                )
                return "Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau."


# Module-level singleton
model_client = ModelServiceClient()
