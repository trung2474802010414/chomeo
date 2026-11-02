"""
services/email_service.py
Đáp ứng CLO2 (Email trong ứng dụng Web Flask):
- Quản lý gửi email tự động xác nhận Đơn hàng / Lịch hẹn Spa qua SMTP.
- Tự động ghi nhật ký gửi thư vào bảng `email_logs`.
- Giao diện HTML email được tách sang `services.email_templates`.
- Cấu hình SMTP & Admin Email được tách sang `services.email_config`.
"""

from email.message import EmailMessage
import smtplib
from typing import Any, Dict, Optional
from models.email_log import EmailLog
from services.email_config import (
    get_admin_notification_email,
    get_smtp_credentials,
    save_smtp_credentials,
    set_admin_notification_email,
)
from services.email_templates import (
    build_booking_html_email,
    build_marketing_html_email,
    build_order_html_email,
)

__all__ = [
    "get_smtp_credentials",
    "save_smtp_credentials",
    "get_admin_notification_email",
    "set_admin_notification_email",
    "send_test_email",
    "send_and_log_email",
    "send_order_confirmation_email",
    "send_booking_confirmation_email",
    "build_booking_html_email",
    "build_order_html_email",
    "build_marketing_html_email",
]


def send_and_log_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> Dict[str, Any]:
    """Gửi email qua giao thức SMTP và lưu lịch sử vào bảng `email_logs`."""
    recipient_addr = recipient.strip() if recipient and recipient.strip() else "khachhang@petshop.local"
    creds = get_smtp_credentials()
    smtp_host = creds["smtp_host"]
    smtp_port = creds["smtp_port"]
    smtp_user = creds["smtp_user"]
    smtp_pass = creds["smtp_pass"]

    status = f"Đã gửi thông báo & lưu vào Hộp thư Admin ({recipient_addr})"

    if smtp_user and smtp_pass and "@petshop.local" not in recipient_addr:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"Meow & Woof Pet House <{smtp_user}>"
            msg["To"] = recipient_addr
            msg.set_content(body)
            if html_body:
                msg.add_alternative(html_body, subtype="html")

            with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            status = f"Đã gửi SMTP thành công tới {recipient_addr}"
        except Exception as exc:
            status = f"Lỗi gửi SMTP: {exc}"

    log_entry = EmailLog(
        recipient=recipient_addr,
        subject=subject,
        body=body,
        delivery_status=status,
    )
    log_entry.save()
    return log_entry.to_dict()


def send_test_email(recipient: str) -> Dict[str, Any]:
    """Gửi email HTML kiểm tra kết nối SMTP tới Gmail của người dùng."""
    subject = "[Meow & Woof] Kiểm tra kết nối SMTP gửi Email thành công! 🎉"
    body = (
        f"Xin chào,\n\n"
        f"Chúc mừng bạn! Máy chủ SMTP của Meow & Woof Pet House đã kết nối thành công và gửi được email tới {recipient}.\n"
        f"Trân trọng,\nĐội ngũ Meow & Woof"
    )
    html_body = build_marketing_html_email(
        recipient,
        "KẾT NỐI SMTP THÀNH CÔNG!",
        f"Xin chào Admin Meow & Woof,\nEmail này được gửi thử nghiệm thành công tới {recipient}. Cấu hình đã sẵn sàng!",
    )
    return send_and_log_email(recipient, subject, body, html_body=html_body)


def send_order_confirmation_email(order_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Soạn và gửi email xác nhận đơn mua hàng (Gửi trực tiếp cho Admin & Khách hàng)."""
    items_lines = "\n".join(
        f"  - {item['name']} (SL: {item['quantity']} x {item['price']:,.0f}đ) = {item['subtotal']:,.0f}đ"
        for item in order_dict.get("items", [])
    )
    admin_email = get_admin_notification_email()
    cust_email = (order_dict.get("email") or "").strip()
    total_fmt = f"{order_dict.get('total_amount', 0):,.0f}"

    subject_admin = f"🔔 [ĐƠN HÀNG MỚI #{order_dict.get('id')}] Khách {order_dict.get('customer_name')} ({order_dict.get('phone')}) - {total_fmt}đ"
    body_admin = (
        f"🔔 THÔNG BÁO QUẢN TRỊ VIÊN:\n"
        f"Có đơn hàng mới #{order_dict.get('id')} vừa được đặt trên website Meow & Woof!\n\n"
        f"👤 Khách hàng: {order_dict.get('customer_name')}\n"
        f"📞 Điện thoại: {order_dict.get('phone')}\n"
        f"✉️ Email khách: {cust_email or 'Không cung cấp'}\n"
        f"🏠 Địa chỉ nhận: {order_dict.get('address')}\n"
        f"⏰ Thời gian: {order_dict.get('created_at')}\n\n"
        f"Chi tiết sản phẩm:\n{items_lines}\n\n"
        f"💰 TỔNG TIỀN: {total_fmt} VNĐ\n"
    )
    html_body = build_order_html_email(order_dict)

    admin_res = send_and_log_email(admin_email, subject_admin, body_admin, html_body=html_body)

    if cust_email and cust_email.lower() != admin_email.lower():
        subject_cust = f"[Meow & Woof] Xác nhận đơn hàng #{order_dict.get('id')} - {order_dict.get('customer_name')}"
        body_cust = (
            f"Xin chào {order_dict.get('customer_name')},\n\n"
            f"Cảm ơn bạn đã mua sắm tại Meow & Woof Pet Shop!\n"
            f"Mã đơn hàng: #{order_dict.get('id')}\n"
            f"Tổng thanh toán: {total_fmt} VNĐ\n\n"
            f"Chi tiết sản phẩm:\n{items_lines}\n"
        )
        send_and_log_email(cust_email, subject_cust, body_cust, html_body=html_body)

    return admin_res


def send_booking_confirmation_email(booking_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Soạn và gửi email xác nhận lịch hẹn Spa (Gửi trực tiếp cho Admin & Khách hàng)."""
    admin_email = get_admin_notification_email()
    cust_email = (booking_dict.get("email") or "").strip()
    total_fmt = f"{booking_dict.get('total_price', 0):,.0f}"

    subject_admin = f"🔔 [LỊCH HẸN SPA MỚI #{booking_dict.get('id')}] Bé {booking_dict.get('pet_name')} - {booking_dict.get('customer_name')}"
    body_admin = (
        f"🔔 THÔNG BÁO QUẢN TRỊ VIÊN:\n"
        f"Có khách vừa đặt lịch Spa chăm sóc thú cưng mới trên website Meow & Woof!\n\n"
        f"Mã lịch hẹn: #{booking_dict.get('id')}\n"
        f"👤 Chủ nuôi: {booking_dict.get('customer_name')} (SĐT: {booking_dict.get('phone')})\n"
        f"✉️ Email khách: {cust_email or 'Không cung cấp'}\n"
        f"🐾 Thú cưng: {booking_dict.get('pet_name')} ({booking_dict.get('pet_type')} - {booking_dict.get('pet_weight_kg')}kg)\n"
        f"🛁 Gói dịch vụ: {booking_dict.get('service_name')}\n"
        f"📅 Thời gian: {booking_dict.get('appointment_date')} lúc {booking_dict.get('appointment_time')}\n"
        f"💰 Chi phí tạm tính: {total_fmt} VNĐ\n"
    )
    html_body = build_booking_html_email(booking_dict)

    admin_res = send_and_log_email(admin_email, subject_admin, body_admin, html_body=html_body)

    if cust_email and cust_email.lower() != admin_email.lower():
        subject_cust = f"[Meow & Woof Spa] Vé hẹn Spa #{booking_dict.get('id')} cho bé {booking_dict.get('pet_name')}"
        body_cust = (
            f"Xin chào {booking_dict.get('customer_name')},\n\n"
            f"Lịch hẹn chăm sóc thú cưng của bạn tại Meow & Woof Spa đã được ghi nhận:\n"
            f"  - Mã lịch hẹn: #{booking_dict.get('id')}\n"
            f"  - Thú cưng: {booking_dict.get('pet_name')} ({booking_dict.get('pet_type')} - {booking_dict.get('pet_weight_kg')}kg)\n"
            f"  - Dịch vụ: {booking_dict.get('service_name')}\n"
            f"  - Ngày giờ hẹn: {booking_dict.get('appointment_date')} lúc {booking_dict.get('appointment_time')}\n"
            f"  - Chi phí dự kiến: {total_fmt} VNĐ\n"
        )
        send_and_log_email(cust_email, subject_cust, body_cust, html_body=html_body)

    return admin_res
