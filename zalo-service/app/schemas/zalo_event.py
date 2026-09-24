"""
Pydantic schemas for inbound Zalo events.

Reference inbound payload:
{
  "event_name": "user_send_text",
  "sender":     { "id": "zalo_user_abc123" },
  "message":    { "text": "Tư vấn sữa cho bé", "msg_id": "abc" },
  "timestamp":  1741879550000
}
"""

from pydantic import BaseModel
from typing import Optional


class ZaloSender(BaseModel):
    id: str


class ZaloMessage(BaseModel):
    text: Optional[str] = None
    msg_id: Optional[str] = None


class ZaloEvent(BaseModel):
    event_name: str
    sender: ZaloSender
    message: Optional[ZaloMessage] = None
    timestamp: Optional[int] = None

    @property
    def user_id(self) -> str:
        return self.sender.id

    @property
    def message_text(self) -> str:
        if self.message and self.message.text:
            return self.message.text
        return ""

    @property
    def is_text_message(self) -> bool:
        return self.event_name == "user_send_text" and bool(self.message_text)
