"""
Pydantic schemas for outbound Zalo messages.

Reference outbound payload sent to Zalo API:
{
  "recipient": { "user_id": "zalo_user_abc123" },
  "message":   { "text": "Chào bạn! Bé mấy tháng tuổi ạ?" }
}
"""

from pydantic import BaseModel


class ZaloRecipient(BaseModel):
    user_id: str


class ZaloTextContent(BaseModel):
    text: str


class ZaloSendPayload(BaseModel):
    recipient: ZaloRecipient
    message: ZaloTextContent

    @classmethod
    def build(cls, user_id: str, text: str) -> "ZaloSendPayload":
        """Convenience constructor to avoid boilerplate at call sites."""
        return cls(
            recipient=ZaloRecipient(user_id=user_id),
            message=ZaloTextContent(text=text),
        )
