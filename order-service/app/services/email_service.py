"""
email_service — sends order & payment confirmation emails via SMTP.

Fire-and-forget: failures are logged but never propagate to the caller.
"""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.logger import logger


def _build_confirmation_email(order) -> EmailMessage:
    """Build a plain-text + HTML confirmation email from an OrderRead."""
    items_rows = ""
    for item in order.items:
        items_rows += (
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{item.product_name}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{int(item.subtotal):,}đ</td>"
            f"</tr>"
        )

    items_plain = "\n".join(
        f"  - {item.product_name} x{item.quantity}: {int(item.subtotal):,}đ"
        for item in order.items
    )

    short_id = str(order.order_id)[:8].upper()

    html = f"""\
<div style="font-family:sans-serif;max-width:600px;margin:auto">
  <h2 style="color:#2c6e49">Xác nhận đơn hàng #{short_id}</h2>
  <p>Chào <b>{order.customer_name}</b>,</p>
  <p>Cảm ơn bạn đã đặt hàng tại <b>Nhà Sữa</b>. Thông tin đơn hàng:</p>
  <table style="width:100%;border-collapse:collapse">
    <tr style="background:#f5f5f5">
      <th style="padding:8px;text-align:left">Sản phẩm</th>
      <th style="padding:8px;text-align:center">SL</th>
      <th style="padding:8px;text-align:right">Thành tiền</th>
    </tr>
    {items_rows}
    <tr>
      <td colspan="2" style="padding:8px;text-align:right"><b>Tổng cộng:</b></td>
      <td style="padding:8px;text-align:right"><b>{int(order.total_amount):,}đ</b></td>
    </tr>
  </table>
  <p><b>SĐT:</b> {order.customer_phone}</p>
  <p>Nhà Sữa sẽ liên hệ xác nhận đơn hàng sớm nhất. Cảm ơn bạn!</p>
</div>"""

    plain = (
        f"Xác nhận đơn hàng #{short_id}\n\n"
        f"Chào {order.customer_name},\n\n"
        f"Đơn hàng của bạn:\n{items_plain}\n\n"
        f"Tổng cộng: {int(order.total_amount):,}đ\n"
        f"SĐT: {order.customer_phone}\n\n"
        f"Nhà Sữa sẽ liên hệ xác nhận sớm nhất. Cảm ơn bạn!"
    )

    msg = EmailMessage()
    msg["Subject"] = f"Nhà Sữa - Xác nhận đơn hàng #{short_id}"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = order.customer_email
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    return msg


async def send_order_confirmation(order) -> None:
    """Send confirmation email. Logs errors but never raises."""
    if not settings.EMAIL_ENABLED:
        return

    if not order.customer_email:
        return

    try:
        msg = _build_confirmation_email(order)
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(
            "Confirmation email sent",
            extra={
                "event": "email_sent",
                "order_id": str(order.order_id),
                "to": order.customer_email,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to send confirmation email",
            extra={
                "event": "email_send_failed",
                "order_id": str(order.order_id),
                "to": order.customer_email,
                "error": str(exc),
            },
        )


# ──────────────────────────────────────────────────────────────
# Payment confirmation email
# ──────────────────────────────────────────────────────────────

def _build_payment_email(order, transfer_amount: int) -> EmailMessage:
    """Build payment confirmation email."""
    short_id = str(order.order_id)[:8].upper()

    items_rows = ""
    for item in order.items:
        items_rows += (
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{item.product_name}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{int(item.subtotal):,}đ</td>"
            f"</tr>"
        )

    html = f"""\
<div style="font-family:sans-serif;max-width:600px;margin:auto">
  <div style="background:linear-gradient(135deg,#1b8a5a,#2ecc71);padding:24px;text-align:center;border-radius:12px 12px 0 0">
    <div style="font-size:24px;font-weight:700;color:#fff">🍼 {settings.SMTP_FROM_NAME}</div>
    <div style="font-size:14px;color:rgba(255,255,255,.85);margin-top:4px">Xác nhận thanh toán thành công</div>
  </div>
  <div style="padding:24px;background:#fff;border:1px solid #e8f5e9;border-top:none;border-radius:0 0 12px 12px">
    <p>Chào <b>{order.customer_name}</b>,</p>
    <p>Chúng tôi đã nhận được thanh toán <b style="color:#1b8a5a">{transfer_amount:,.0f}đ</b> cho đơn hàng <b>#{short_id}</b>.</p>

    <div style="background:#f0f9f4;border-radius:8px;padding:16px;margin:16px 0;border-left:4px solid #2ecc71">
      <div style="font-size:14px;color:#2e7d32;font-weight:600">✅ Thanh toán thành công — Đơn hàng đã được xác nhận!</div>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr style="background:#e8f5e9">
        <th style="padding:8px;text-align:left;color:#2e7d32">Sản phẩm</th>
        <th style="padding:8px;text-align:center;color:#2e7d32">SL</th>
        <th style="padding:8px;text-align:right;color:#2e7d32">Thành tiền</th>
      </tr>
      {items_rows}
      <tr style="background:#f8fdf9">
        <td colspan="2" style="padding:10px 8px;text-align:right;font-weight:700;color:#1b8a5a">Tổng cộng:</td>
        <td style="padding:10px 8px;text-align:right;font-weight:700;color:#1b8a5a;font-size:16px">{int(order.total_amount):,}đ</td>
      </tr>
    </table>

    <p style="font-size:13px;color:#666">Đơn hàng của bạn đang được xử lý và sẽ được giao trong thời gian sớm nhất.</p>
    <p style="font-size:13px;color:#666">Nếu cần hỗ trợ, bạn có thể nhắn tin trực tiếp cho chúng tôi qua Zalo.</p>
  </div>
  <div style="text-align:center;padding:16px;font-size:12px;color:#999">
    {settings.SMTP_FROM_NAME} — Đồng hành cùng sức khoẻ gia đình bạn 💚
  </div>
</div>"""

    plain = (
        f"Xác nhận thanh toán đơn hàng #{short_id}\n\n"
        f"Chào {order.customer_name},\n\n"
        f"Chúng tôi đã nhận được thanh toán {transfer_amount:,.0f}đ "
        f"cho đơn hàng #{short_id}.\n\n"
        f"Đơn hàng đã được xác nhận và đang được xử lý.\n\n"
        f"Trân trọng,\n{settings.SMTP_FROM_NAME}"
    )

    msg = EmailMessage()
    msg["Subject"] = f"✅ Thanh toán thành công — Đơn hàng #{short_id}"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = order.customer_email
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    return msg


async def send_payment_confirmation(order, transfer_amount: int) -> None:
    """Send payment confirmation email. Logs errors but never raises."""
    if not settings.EMAIL_ENABLED:
        return

    if not order.customer_email:
        return

    try:
        msg = _build_payment_email(order, transfer_amount)
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(
            "Payment confirmation email sent",
            extra={
                "event": "payment_email_sent",
                "order_id": str(order.order_id),
                "to": order.customer_email,
                "amount": transfer_amount,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to send payment confirmation email",
            extra={
                "event": "payment_email_send_failed",
                "order_id": str(order.order_id),
                "to": order.customer_email,
                "error": str(exc),
            },
        )
