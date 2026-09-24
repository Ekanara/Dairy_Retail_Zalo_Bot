"""
email_service.py — Gửi email xác nhận đơn hàng HTML template xanh-trắng.
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_GIFT_KEYWORDS = ["tặng", "gối", "bình", "túi", "khăn", "yếm", "balo", "hộp"]


def _qr_section_html(payment_qr_url: str) -> str:
    """Return QR payment HTML block, or empty string if no URL."""
    if not payment_qr_url:
        return ""
    return f'''
    <tr>
        <td style="padding:0 24px 20px">
            <div style="background:#fff8e1;border-radius:8px;padding:20px;text-align:center;border:1px solid #ffe082">
                <div style="font-size:15px;font-weight:700;color:#f57f17;margin-bottom:12px">
                    Ma QR Thanh Toan
                </div>
                <img src="{payment_qr_url}" alt="QR Thanh Toan" style="max-width:280px;border-radius:8px" />
                <div style="font-size:12px;color:#888;margin-top:8px">
                    Quet ma QR de thanh toan qua VietQR / Napas 247
                </div>
            </div>
        </td>
    </tr>'''


def _build_html_body(
    customer_name: str,
    product_name: str,
    price: int,
    quantity: int,
) -> str:
    total = price * quantity
    has_gift = any(kw in product_name.lower() for kw in _GIFT_KEYWORDS)

    gift_row = ""
    if has_gift:
        gift_row = """
        <tr>
            <td style="padding:12px 16px;color:#666">🎁 Quà kèm</td>
            <td style="padding:12px 16px;text-align:right;color:#2e7d32;font-weight:600">
                Xem chi tiết trong mô tả sản phẩm
            </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f7f6;font-family:'Segoe UI',Roboto,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7f6;padding:32px 0">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">

    <!-- Header -->
    <tr>
        <td style="background:linear-gradient(135deg,#1b8a5a,#2ecc71);padding:32px 24px;text-align:center">
            <div style="font-size:28px;font-weight:700;color:#fff;letter-spacing:-0.5px">
                🍼 {settings.SMTP_FROM_NAME}
            </div>
            <div style="font-size:14px;color:rgba(255,255,255,.85);margin-top:6px">
                Xác nhận đơn hàng thành công
            </div>
        </td>
    </tr>

    <!-- Greeting -->
    <tr>
        <td style="padding:28px 24px 12px">
            <div style="font-size:16px;color:#333">
                Chào <strong>{customer_name}</strong>,
            </div>
            <div style="font-size:14px;color:#666;margin-top:8px;line-height:1.6">
                Cảm ơn bạn đã đặt hàng! Đơn hàng của bạn đã được ghi nhận thành công. 🎉
            </div>
        </td>
    </tr>

    <!-- Order details -->
    <tr>
        <td style="padding:12px 24px 24px">
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e8f5e9;border-radius:8px;overflow:hidden">
                <tr style="background:#e8f5e9">
                    <td colspan="2" style="padding:12px 16px;font-weight:600;color:#2e7d32;font-size:14px">
                        📋 Chi tiết đơn hàng
                    </td>
                </tr>
                <tr style="border-bottom:1px solid #f0f0f0">
                    <td style="padding:12px 16px;color:#666">📦 Sản phẩm</td>
                    <td style="padding:12px 16px;text-align:right;font-weight:600;color:#333">{product_name}</td>
                </tr>
                <tr style="border-bottom:1px solid #f0f0f0">
                    <td style="padding:12px 16px;color:#666">💰 Đơn giá</td>
                    <td style="padding:12px 16px;text-align:right;color:#333">{price:,} VND</td>
                </tr>
                <tr style="border-bottom:1px solid #f0f0f0">
                    <td style="padding:12px 16px;color:#666">🛒 Số lượng</td>
                    <td style="padding:12px 16px;text-align:right;color:#333">{quantity}</td>
                </tr>{gift_row}
                <tr style="background:#f8fdf9">
                    <td style="padding:14px 16px;font-weight:700;color:#1b8a5a;font-size:15px">💵 Tổng tiền</td>
                    <td style="padding:14px 16px;text-align:right;font-weight:700;color:#1b8a5a;font-size:18px">{total:,} VND</td>
                </tr>
            </table>
        </td>
    </tr>

    <!-- Note -->
    <tr>
        <td style="padding:0 24px 28px">
            <div style="background:#f0f9f4;border-radius:8px;padding:16px;font-size:13px;color:#555;line-height:1.6;border-left:4px solid #2ecc71">
                Chúng tôi sẽ liên hệ xác nhận trong vòng <strong>24 giờ</strong>.
                Nếu cần hỗ trợ, bạn có thể nhắn tin trực tiếp cho chúng tôi qua Zalo.
            </div>
        </td>
    </tr>

    <!-- Footer -->
    <tr>
        <td style="background:#fafafa;padding:20px 24px;text-align:center;border-top:1px solid #eee">
            <div style="font-size:12px;color:#999">
                {settings.SMTP_FROM_NAME} — Đồng hành cùng sức khoẻ gia đình bạn 💚
            </div>
        </td>
    </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _build_plain_body(
    customer_name: str,
    product_name: str,
    price: int,
    quantity: int,
) -> str:
    total = price * quantity
    return (
        f"Chào {customer_name},\n\n"
        f"Cảm ơn bạn đã đặt hàng tại {settings.SMTP_FROM_NAME}! 🎉\n\n"
        f"📦 Sản phẩm : {product_name}\n"
        f"💰 Đơn giá  : {price:,} VND\n"
        f"🛒 Số lượng : {quantity}\n"
        f"💵 Tổng tiền: {total:,} VND\n\n"
        f"Chúng tôi sẽ liên hệ xác nhận trong vòng 24 giờ.\n\n"
        f"Trân trọng,\n{settings.SMTP_FROM_NAME} 🍼"
    )


async def send_confirmation_email(
    to_email: str,
    customer_name: str,
    product_name: str,
    price: int,
    quantity: int,
) -> bool:
    """
    Gửi email xác nhận đơn hàng (HTML + plain text fallback).

    Returns True nếu gửi thành công, False nếu gặp lỗi.
    """
    if not settings.EMAIL_ENABLED:
        logger.info("email_disabled", extra={"to": to_email})
        return False

    subject = f"✅ Xác nhận đơn hàng — {product_name[:40]}"

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.email_from_header
    msg["To"] = to_email
    msg["Subject"] = subject

    # Plain text fallback
    msg.attach(MIMEText(
        _build_plain_body(customer_name, product_name, price, quantity),
        "plain", "utf-8",
    ))
    # HTML primary
    msg.attach(MIMEText(
        _build_html_body(customer_name, product_name, price, quantity),
        "html", "utf-8",
    ))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("email_sent", extra={"to": to_email, "subject": subject})
        return True

    except aiosmtplib.SMTPAuthenticationError as exc:
        logger.error("email_auth_error", extra={"to": to_email, "error": str(exc)})
        return False

    except aiosmtplib.SMTPConnectError as exc:
        logger.error("email_connect_error", extra={
            "to": to_email, "smtp_host": settings.SMTP_HOST, "error": str(exc),
        })
        return False

    except aiosmtplib.SMTPException as exc:
        logger.error("email_smtp_error", extra={"to": to_email, "error": str(exc)})
        return False


def _build_multi_item_html_body(
    customer_name: str,
    order_items: List[Dict],
    total_amount: int,
    payment_qr_url: str = "",
) -> str:
    """Build HTML email body for multi-item orders."""

    # Build product rows
    product_rows = ""
    for idx, item in enumerate(order_items):
        has_gift = any(kw in item['product_name'].lower() for kw in _GIFT_KEYWORDS)
        gift_badge = ' 🎁' if has_gift else ''

        product_rows += f"""
        <tr style="border-bottom:1px solid #f0f0f0">
            <td style="padding:12px 16px;color:#333;font-weight:600">
                {item['product_name']}{gift_badge}
            </td>
            <td style="padding:12px 16px;text-align:center;color:#666">
                {item['unit_price']:,}
            </td>
            <td style="padding:12px 16px;text-align:center;color:#666">
                {item['quantity']}
            </td>
            <td style="padding:12px 16px;text-align:right;color:#333;font-weight:500">
                {item['unit_price'] * item['quantity']:,} VND
            </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f7f6;font-family:'Segoe UI',Roboto,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7f6;padding:32px 0">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">

    <!-- Header -->
    <tr>
        <td style="background:linear-gradient(135deg,#1b8a5a,#2ecc71);padding:32px 24px;text-align:center">
            <div style="font-size:28px;font-weight:700;color:#fff;letter-spacing:-0.5px">
                🍼 {settings.SMTP_FROM_NAME}
            </div>
            <div style="font-size:14px;color:rgba(255,255,255,.85);margin-top:6px">
                Xác nhận đơn hàng thành công
            </div>
        </td>
    </tr>

    <!-- Greeting -->
    <tr>
        <td style="padding:28px 24px 12px">
            <div style="font-size:16px;color:#333">
                Chào <strong>{customer_name}</strong>,
            </div>
            <div style="font-size:14px;color:#666;margin-top:8px;line-height:1.6">
                Cảm ơn bạn đã đặt hàng! Đơn hàng của bạn với {len(order_items)} sản phẩm đã được ghi nhận thành công. 🎉
            </div>
        </td>
    </tr>

    <!-- Order details -->
    <tr>
        <td style="padding:12px 24px 24px">
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e8f5e9;border-radius:8px;overflow:hidden">
                <tr style="background:#e8f5e9">
                    <td style="padding:12px 16px;font-weight:600;color:#2e7d32;font-size:14px">
                        📦 Sản phẩm
                    </td>
                    <td style="padding:12px 16px;text-align:center;font-weight:600;color:#2e7d32;font-size:14px">
                        💰 Đơn giá
                    </td>
                    <td style="padding:12px 16px;text-align:center;font-weight:600;color:#2e7d32;font-size:14px">
                        🛒 SL
                    </td>
                    <td style="padding:12px 16px;text-align:right;font-weight:600;color:#2e7d32;font-size:14px">
                        Thành tiền
                    </td>
                </tr>
                {product_rows}
                <tr style="background:#f8fdf9">
                    <td colspan="3" style="padding:14px 16px;font-weight:700;color:#1b8a5a;font-size:15px">
                        Tong cong
                    </td>
                    <td style="padding:14px 16px;text-align:right;font-weight:700;color:#1b8a5a;font-size:18px">
                        {total_amount:,} VND
                    </td>
                </tr>
            </table>
        </td>
    </tr>

    {_qr_section_html(payment_qr_url)}

    <!-- Note -->
    <tr>
        <td style="padding:0 24px 28px">
            <div style="background:#f0f9f4;border-radius:8px;padding:16px;font-size:13px;color:#555;line-height:1.6;border-left:4px solid #2ecc71">
                Chung toi se lien he xac nhan trong vong <strong>24 gio</strong>.
                Neu can ho tro, ban co the nhan tin truc tiep cho chung toi qua Zalo.
            </div>
        </td>
    </tr>

    <!-- Footer -->
    <tr>
        <td style="background:#fafafa;padding:20px 24px;text-align:center;border-top:1px solid #eee">
            <div style="font-size:12px;color:#999">
                {settings.SMTP_FROM_NAME} — Dong hanh cung suc khoe gia dinh ban
            </div>
        </td>
    </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _build_multi_item_plain_body(
    customer_name: str,
    order_items: List[Dict],
    total_amount: int,
) -> str:
    """Build plain text email body for multi-item orders."""

    items_text = "\n".join([
        f"  - {item['product_name']}: {item['quantity']} x {item['unit_price']:,} = {item['unit_price'] * item['quantity']:,} VND"
        for item in order_items
    ])

    return (
        f"Chào {customer_name},\n\n"
        f"Cảm ơn bạn đã đặt hàng tại {settings.SMTP_FROM_NAME}! 🎉\n\n"
        f"📦 Danh sách sản phẩm:\n{items_text}\n\n"
        f"💵 Tổng cộng: {total_amount:,} VND\n\n"
        f"Chúng tôi sẽ liên hệ xác nhận trong vòng 24 giờ.\n\n"
        f"Trân trọng,\n{settings.SMTP_FROM_NAME} 🍼"
    )


async def send_confirmation_email_multi(
    to_email: str,
    customer_name: str,
    order_items: List[Dict],
    total_amount: int,
    payment_qr_url: str = "",
) -> bool:
    """
    Gửi email xác nhận đơn hàng nhiều sản phẩm.

    Args:
        to_email: Email người nhận
        customer_name: Tên khách hàng
        order_items: Danh sách sản phẩm [{"product_name", "unit_price", "quantity"}, ...]
        total_amount: Tổng tiền đơn hàng

    Returns:
        True nếu gửi thành công, False nếu gặp lỗi.
    """
    if not settings.EMAIL_ENABLED:
        logger.info("email_disabled", extra={"to": to_email})
        return False

    # Create subject with first product name
    first_product = order_items[0]['product_name'][:30] if order_items else "Đơn hàng"
    item_count = len(order_items)
    subject = f"✅ Xác nhận đơn hàng — {first_product} và {item_count-1} sp khác" if item_count > 1 else f"✅ Xác nhận đơn hàng — {first_product}"

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.email_from_header
    msg["To"] = to_email
    msg["Subject"] = subject

    # Plain text fallback
    msg.attach(MIMEText(
        _build_multi_item_plain_body(customer_name, order_items, total_amount),
        "plain", "utf-8",
    ))
    # HTML primary
    msg.attach(MIMEText(
        _build_multi_item_html_body(customer_name, order_items, total_amount, payment_qr_url),
        "html", "utf-8",
    ))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("email_sent", extra={"to": to_email, "subject": subject, "item_count": item_count})
        return True

    except aiosmtplib.SMTPAuthenticationError as exc:
        logger.error("email_auth_error", extra={"to": to_email, "error": str(exc)})
        return False

    except aiosmtplib.SMTPConnectError as exc:
        logger.error("email_connect_error", extra={
            "to": to_email, "smtp_host": settings.SMTP_HOST, "error": str(exc),
        })
        return False

    except aiosmtplib.SMTPException as exc:
        logger.error("email_smtp_error", extra={"to": to_email, "error": str(exc)})
        return False
