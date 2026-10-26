"""
services/email_service.py
Đáp ứng CLO2 (Email trong ứng dụng Web Flask):
- Sử dụng `smtplib` và `email.message.EmailMessage` của Python để gửi email xác nhận
  Đơn hàng và Lịch hẹn Spa cho khách hàng.
- Đồng thời lưu bản ghi vào bảng `email_logs` trong SQLite để giảng viên/người học có thể
  kiểm tra trực tiếp nội dung email được sinh ra ngay trên giao diện Quản trị (`/admin`)
  kể cả khi máy tính chưa cấu hình tài khoản SMTP thực tế.
"""

from email.message import EmailMessage
import os
import smtplib
from typing import Any, Dict
from models.email_log import EmailLog


def send_and_log_email(recipient: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Gửi email qua giao thức SMTP (nếu có cấu hình biến môi trường SMTP_USER & SMTP_PASS)
    và lưu lịch sử vào bảng `email_logs`.
    """
    recipient_addr = recipient.strip() if recipient and recipient.strip() else "khachhang@petshop.local"
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    status = "Đã lưu vào hộp thư hệ thống (Chế độ Local Demo)"

    if smtp_user and smtp_pass and "@petshop.local" not in recipient_addr:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = recipient_addr
            msg.set_content(body)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=8) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            status = f"Đã gửi SMTP thành công tới {recipient_addr}"
        except Exception as exc:
            status = f"Lưu hộp thư hệ thống (Lỗi SMTP: {exc})"

    log_entry = EmailLog(
        recipient=recipient_addr,
        subject=subject,
        body=body,
        delivery_status=status,
    )
    log_entry.save()
    return log_entry.to_dict()


def send_order_confirmation_email(order_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Soạn và gửi email xác nhận đơn mua hàng tại Meow & Woof Pet Shop."""
    items_lines = "\n".join(
        f"  - {item['name']} (SL: {item['quantity']} x {item['price']:,.0f}đ) = {item['subtotal']:,.0f}đ"
        for item in order_dict.get("items", [])
    )
    subject = f"[Meow & Woof] Xác nhận đơn hàng #{order_dict.get('id')} - {order_dict.get('customer_name')}"
    body = (
        f"Xin chào {order_dict.get('customer_name')},\n\n"
        f"Cảm ơn bạn đã mua sắm tại Meow & Woof Pet Shop!\n"
        f"Mã đơn hàng: #{order_dict.get('id')}\n"
        f"Số điện thoại nhận hàng: {order_dict.get('phone')}\n"
        f"Địa chỉ giao hàng: {order_dict.get('address')}\n\n"
        f"Chi tiết sản phẩm:\n{items_lines}\n\n"
        f"Tổng thanh toán: {order_dict.get('total_amount', 0):,.0f} VNĐ\n"
        f"Thời gian đặt: {order_dict.get('created_at')}\n\n"
        f"Trân trọng,\nĐội ngũ Meow & Woof Pet Shop & Spa"
    )
    return send_and_log_email(order_dict.get("email", ""), subject, body)


def send_booking_confirmation_email(booking_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Soạn và gửi email xác nhận lịch hẹn Spa cho thú cưng."""
    subject = f"[Meow & Woof Spa] Xác nhận lịch hẹn #{booking_dict.get('id')} cho bé {booking_dict.get('pet_name')}"
    body = (
        f"Xin chào {booking_dict.get('customer_name')},\n\n"
        f"Lịch hẹn chăm sóc thú cưng của bạn tại Meow & Woof Spa đã được ghi nhận:\n"
        f"  - Mã lịch hẹn: #{booking_dict.get('id')}\n"
        f"  - Thú cưng: {booking_dict.get('pet_name')} ({booking_dict.get('pet_type')} - {booking_dict.get('pet_weight_kg')}kg)\n"
        f"  - Gói dịch vụ: {booking_dict.get('service_name')}\n"
        f"  - Ngày giờ hẹn: {booking_dict.get('appointment_date')} lúc {booking_dict.get('appointment_time')}\n"
        f"  - Chi phí dự kiến: {booking_dict.get('total_price', 0):,.0f} VNĐ\n"
        f"  - Ghi chú: {booking_dict.get('note') or 'Không có'}\n\n"
        f"Vui lòng đưa bé đến trước giờ hẹn 10 phút để kỹ thuật viên đón tiếp chu đáo nhất.\n"
        f"Trân trọng,\nMeow & Woof Pet Shop & Spa"
    )
    return send_and_log_email(booking_dict.get("email", ""), subject, body)

