"""
services/email_service.py
Quản lý cấu hình Email của Admin, giao diện HTML Email và gửi thông báo đơn hàng / lịch hẹn Spa về Mail Admin.
"""

from email.message import EmailMessage
import json
import os
import smtplib
from typing import Any, Dict, Optional
from core.database import resolve_writable_json_path
from models.entities import EmailLog

FOOTER_HTML = """<div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:16px; margin-top:20px; font-size:12px; color:#94a3b8; text-align:center; line-height:1.6;">
  Meow &amp; Woof Pet House &amp; Spa Chó Mèo • Hotline: 0905.123.456<br>
  ⏰ Mở cửa: 08:00 – 21:00 hàng ngày • Cửa hàng &amp; Spa 5 sao toàn quốc.
</div>"""


def get_smtp_credentials() -> Dict[str, Any]:
    """Lấy thông tin tài khoản SMTP từ biến môi trường, .env hoặc data/smtp_config.json."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except (ValueError, TypeError):
        port = 587
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()

    if not user or not pwd:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for env_path in (os.path.join(base_dir, ".env"), os.path.join(os.path.dirname(base_dir), ".env")):
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip('"').strip("'")
                            if k == "SMTP_USER" and not user:
                                user = v
                            elif k == "SMTP_PASS" and not pwd:
                                pwd = v
                            elif k == "SMTP_HOST" and host == "smtp.gmail.com":
                                host = v
                            elif k == "SMTP_PORT":
                                try:
                                    port = int(v)
                                except ValueError:
                                    pass
                except Exception:
                    pass

    if not user or not pwd:
        cfg_path = resolve_writable_json_path("smtp_config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    user = user or cfg.get("smtp_user", "").strip()
                    pwd = pwd or cfg.get("smtp_pass", "").strip()
                    host = cfg.get("smtp_host", host) or host
                    port = int(cfg.get("smtp_port", port) or port)
            except Exception:
                pass

    return {
        "smtp_host": host or "smtp.gmail.com",
        "smtp_port": port or 587,
        "smtp_user": user,
        "smtp_pass": pwd.replace(" ", ""),
    }


def save_smtp_credentials(smtp_user: str, smtp_pass: str, smtp_host: str = "smtp.gmail.com", smtp_port: int = 587) -> None:
    """Lưu cấu hình SMTP an toàn (tương thích 100% với Vercel Serverless & Local)."""
    clean_pass = smtp_pass.strip().replace(" ", "")
    os.environ["SMTP_USER"] = smtp_user.strip()
    os.environ["SMTP_PASS"] = clean_pass
    os.environ["SMTP_HOST"] = smtp_host.strip() or "smtp.gmail.com"
    os.environ["SMTP_PORT"] = str(smtp_port)

    try:
        cfg_path = resolve_writable_json_path("smtp_config.json")
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        data = {
            "smtp_user": smtp_user.strip(),
            "smtp_pass": clean_pass,
            "smtp_host": smtp_host.strip() or "smtp.gmail.com",
            "smtp_port": smtp_port,
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_admin_notification_email() -> str:
    """Lấy địa chỉ Email nhận thông báo của Admin."""
    admin_mail = (
        os.environ.get("ADMIN_NOTIFICATION_EMAIL", "").strip()
        or os.environ.get("PETSHOP_ADMIN_NOTIFY_EMAIL", "").strip()
    )
    cfg_path = resolve_writable_json_path("admin_settings.json")
    if not admin_mail and os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                admin_mail = json.load(f).get("admin_notification_email", "").strip()
        except Exception:
            pass
    if not admin_mail:
        creds = get_smtp_credentials()
        admin_mail = creds.get("smtp_user") or "boss_admin@gmail.com"
    return admin_mail


def set_admin_notification_email(email_addr: str) -> None:
    """Lưu địa chỉ Email nhận thông báo của Admin an toàn (tương thích 100% với Vercel Serverless & Local)."""
    clean_mail = email_addr.strip()
    os.environ["ADMIN_NOTIFICATION_EMAIL"] = clean_mail
    os.environ["PETSHOP_ADMIN_NOTIFY_EMAIL"] = clean_mail
    try:
        cfg_path = resolve_writable_json_path("admin_settings.json")
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        data = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["admin_notification_email"] = clean_mail
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def build_booking_html_email(booking: Dict[str, Any]) -> str:
    """Tạo giao diện HTML Email vé hẹn Spa chuẩn Brand Meow & Woof."""
    b_id, cust = booking.get("id", ""), booking.get("customer_name", "Quý khách")
    pet_name, p_type = booking.get("pet_name", "Bé cưng"), booking.get("pet_type", "Thú cưng")
    weight = booking.get("pet_weight_kg", "4.0")
    service, app_d, app_t = booking.get("service_name", "Spa"), booking.get("appointment_date", ""), booking.get("appointment_time", "")
    price, note = f"{booking.get('total_price', 0):,.0f}", booking.get("note", "") or "Không có"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <div style="background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); border-radius:24px 24px 0 0; padding:28px 24px; text-align:center;">
    <div style="font-size:32px; margin-bottom:8px;">🐾</div>
    <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff;">Meow &amp; Woof Pet House &amp; Spa</h1>
    <p style="margin:4px 0 0; font-size:13px; color:#fde047; font-weight:700;">✨ VÉ XÁC NHẬN LỊCH HẸN SPA 5 SAO #{b_id} ✨</p>
  </div>
  <div style="background:#15102d; border:1px solid rgba(139,92,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:24px;">
    <p style="margin:0 0 14px; font-size:14.5px; color:#e2e8f0; line-height:1.5;">
      Xin chào <strong>{cust}</strong>,<br>Meow &amp; Woof đã nhận được yêu cầu đặt lịch hẹn cho bé <strong>{pet_name}</strong>.
    </p>
    <div style="background:#1d173e; border:1px dashed #8b5cf6; border-radius:16px; padding:16px; margin:16px 0; font-size:13px; color:#e2e8f0;">
      <div>🐾 <strong>Dịch vụ:</strong> {service}</div>
      <div style="margin-top:6px;">🐶 <strong>Bé cưng:</strong> {pet_name} ({p_type} - {weight} kg)</div>
      <div style="margin-top:6px;">📅 <strong>Thời gian:</strong> {app_d} lúc {app_t}</div>
      <div style="margin-top:6px;">💰 <strong>Chi phí tạm tính:</strong> <span style="color:#34d399; font-weight:800; font-size:16px;">{price} đ</span></div>
      <div style="margin-top:6px;">📝 <strong>Ghi chú:</strong> <em>{note}</em></div>
    </div>
    <div style="text-align:center; margin:22px 0 12px;">
      <a href="https://chomeo.vercel.app/spa" style="display:inline-block; padding:10px 28px; background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:700; font-size:13.5px;">🐾 Mở Website Meow &amp; Woof</a>
    </div>
    {FOOTER_HTML}
  </div>
</div></body></html>"""


def build_order_html_email(order: Dict[str, Any]) -> str:
    """Tạo giao diện HTML Email xác nhận đơn mua hàng."""
    o_id, cust = order.get("id", ""), order.get("customer_name", "Quý khách")
    phone, addr, cr_at = order.get("phone", ""), order.get("address", ""), order.get("created_at", "")
    total = f"{order.get('total_amount', 0):,.0f}"

    rows = "".join(
        f"<tr style='border-bottom:1px solid rgba(255,255,255,0.06);'><td style='padding:8px 0; color:#ffffff;'>{it['name']}</td><td style='padding:8px 0; text-align:center;'>x{it['quantity']}</td><td style='padding:8px 0; text-align:right; color:#34d399; font-weight:700;'>{it['subtotal']:,.0f} đ</td></tr>"
        for it in order.get("items", [])
    )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <div style="background:linear-gradient(135deg, #10b981 0%, #3b82f6 100%); border-radius:24px 24px 0 0; padding:28px 24px; text-align:center;">
    <div style="font-size:32px; margin-bottom:8px;">🛍️</div>
    <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff;">Thông Báo Đơn Hàng Mới #{o_id}</h1>
    <p style="margin:4px 0 0; font-size:13px; color:#dbeafe; font-weight:700;">ĐƠN HÀNG #{o_id} ĐÃ ĐƯỢC XÁC NHẬN THÀNH CÔNG</p>
  </div>
  <div style="background:#15102d; border:1px solid rgba(59,130,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:24px;">
    <p style="margin:0 0 14px; font-size:14.5px; color:#e2e8f0; line-height:1.5;">Khách hàng <strong>{cust}</strong> vừa đặt thành công đơn hàng #{o_id}!</p>
    <div style="background:#1d173e; border-radius:14px; padding:14px 18px; margin:14px 0; font-size:13px; color:#cbd5e1;">
      <div><strong>Người nhận:</strong> {cust} ({phone})</div>
      <div style="margin-top:4px;"><strong>Địa chỉ:</strong> {addr}</div>
      <div style="margin-top:4px;"><strong>Thời gian:</strong> {cr_at}</div>
    </div>
    <table style="width:100%; border-collapse:collapse; font-size:13px; margin:16px 0;">
      <thead><tr style="border-bottom:1.5px solid rgba(255,255,255,0.15); color:#94a3b8;"><th style="text-align:left; padding-bottom:6px;">Sản phẩm</th><th style="text-align:center; padding-bottom:6px;">SL</th><th style="text-align:right; padding-bottom:6px;">Thành tiền</th></tr></thead>
      <tbody>{rows}</tbody>
      <tfoot><tr><td colspan="2" style="padding-top:12px; font-weight:800; font-size:14px;">TỔNG THANH TOÁN:</td><td style="padding-top:12px; text-align:right; font-weight:800; font-size:17px; color:#34d399;">{total} đ</td></tr></tfoot>
    </table>
    <div style="text-align:center; margin:22px 0 12px;">
      <a href="https://chomeo.vercel.app/" style="display:inline-block; padding:10px 28px; background:linear-gradient(135deg, #10b981 0%, #3b82f6 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:700; font-size:13.5px;">🛍️ Mở Quản Trị Đơn Hàng</a>
    </div>
    {FOOTER_HTML}
  </div>
</div></body></html>"""


def build_marketing_html_email(recipient: str, subject: str, body: str) -> str:
    """Tạo giao diện HTML Email ưu đãi / tri ân khách hàng chuẩn Brand Meow & Woof."""
    p_html = "".join(f"<p style='margin:0 0 10px; font-size:14px; color:#e2e8f0; line-height:1.5;'>{p.strip()}</p>" for p in body.split("\n") if p.strip())
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <div style="background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 50%, #f59e0b 100%); border-radius:24px 24px 0 0; padding:28px 24px; text-align:center;">
    <div style="font-size:32px; margin-bottom:8px;">🎁</div>
    <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff;">Meow &amp; Woof Pet House &amp; Spa</h1>
    <p style="margin:4px 0 0; font-size:13px; color:#fef08a; font-weight:700;">✨ ĐẶC QUYỀN TRI ÂN DÀNH CHO KHÁCH HÀNG THÂN THIẾT ✨</p>
  </div>
  <div style="background:#15102d; border:1px solid rgba(139,92,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:24px;">
    {p_html}
    <div style="background:linear-gradient(135deg, rgba(139,92,246,0.2) 0%, rgba(245,158,11,0.2) 100%); border:1.5px dashed #f59e0b; border-radius:16px; padding:16px; text-align:center; margin:18px 0;">
      <div style="font-size:11px; color:#fde047; font-weight:800; text-transform:uppercase;">MÃ ƯU ĐÃI ĐẶC QUYỀN VIP</div>
      <div style="font-size:22px; font-weight:900; color:#ffffff; letter-spacing:2px; font-family:monospace; background:rgba(0,0,0,0.35); padding:6px 16px; border-radius:8px; display:inline-block; margin:6px 0;">MEOWWOOF-VIP20</div>
      <div style="font-size:12px; color:#cbd5e1;">Giảm ngay 20% cho toàn bộ dịch vụ Spa &amp; phụ kiện chó mèo!</div>
    </div>
    <div style="text-align:center; margin:22px 0 12px;">
      <a href="https://chomeo.vercel.app/" style="display:inline-block; padding:10px 28px; background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:700; font-size:13.5px;">🐾 Nhận Ngay Ưu Đãi Tại Shop</a>
    </div>
    {FOOTER_HTML}
  </div>
</div></body></html>"""


def send_and_log_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> Dict[str, Any]:
    """Gửi email thật tới hộp thư Admin (qua Google SMTP hoặc FormSubmit Relay) và lưu lịch sử vào bảng `email_logs`."""
    import urllib.request

    recipient_addr = recipient.strip() if recipient and recipient.strip() else get_admin_notification_email()
    creds = get_smtp_credentials()
    smtp_host = creds["smtp_host"]
    smtp_port = creds["smtp_port"]
    smtp_user = creds["smtp_user"] or recipient_addr
    smtp_pass = creds["smtp_pass"]

    status = f"Đã lưu vào Hộp thư Admin ({recipient_addr})"
    is_real_email = (
        "@" in recipient_addr
        and "@petshop.local" not in recipient_addr
        and "@example.com" not in recipient_addr
        and recipient_addr != "boss_admin@gmail.com"
    )

    if smtp_user and smtp_pass and "@petshop.local" not in recipient_addr and "@example.com" not in recipient_addr:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"Meow & Woof Pet House <{smtp_user}>"
            msg["To"] = recipient_addr
            msg.set_content(body)
            if html_body:
                msg.add_alternative(html_body, subtype="html")

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            status = f"Đã gửi Gmail SMTP thành công tới {recipient_addr}"
        except Exception as exc:
            status = f"Lỗi SMTP ({exc}) — Đã lưu bản sao tại Hộp thư Admin"
    elif is_real_email:
        # Gửi qua cổng chuyển tiếp FormSubmit AJAX không cần mật khẩu
        try:
            relay_url = f"https://formsubmit.co/ajax/{recipient_addr}"
            payload_bytes = json.dumps(
                {
                    "_subject": subject,
                    "He_Thong": "Meow & Woof Pet House & Spa",
                    "Thong_Bao_Chi_Tiet": body,
                    "_template": "box",
                    "_captcha": "false",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            req = urllib.request.Request(
                relay_url,
                data=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": "https://chomeo.vercel.app",
                    "Referer": "https://chomeo.vercel.app/",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                resp_json = json.loads(resp.read().decode("utf-8", errors="ignore"))
                msg_info = str(resp_json.get("message", ""))
                if resp_json.get("success") in (True, "true"):
                    status = f"Đã gửi thẳng tới Gmail {recipient_addr} (FormSubmit Relay)"
                elif "activate" in msg_info.lower() or "confirm" in msg_info.lower():
                    status = f"Chờ bấm Activate trong Gmail {recipient_addr} (Kiểm tra hộp thư/Spam)"
                else:
                    status = f"Đã gửi thông báo tới {recipient_addr}"
        except Exception:
            status = f"Đã lưu thông báo ({recipient_addr}) — Điền Mật khẩu ứng dụng Gmail để gửi thẳng SMTP"

    log_entry = EmailLog(
        recipient=recipient_addr[:145],
        subject=subject[:240],
        body=body[:14500],
        delivery_status=status[:240],
    )
    log_entry.save()
    return log_entry.to_dict()


def send_test_email(recipient: str) -> Dict[str, Any]:
    """Gửi email HTML kiểm tra kết nối tới địa chỉ Email của Admin."""
    subject = "[Meow & Woof] Đã lưu cấu hình Email Admin nhận thông báo đơn hàng! 🎉"
    body = (
        f"Xin chào Admin,\n\n"
        f"Hệ thống Meow & Woof Pet House đã cập nhật địa chỉ Email nhận thông báo đơn hàng là: {recipient}.\n"
        f"Khi khách hàng đặt mua thú cưng, phụ kiện hoặc đặt lịch Spa, thông báo chi tiết sẽ được gửi về đây.\n"
    )
    html_body = build_marketing_html_email(
        recipient,
        "CẬP NHẬT EMAIL ADMIN THÀNH CÔNG!",
        f"Xin chào Admin Meow & Woof,\nHệ thống đã lưu địa chỉ {recipient} làm hộp thư nhận thông báo đơn hàng!",
    )
    return send_and_log_email(recipient, subject, body, html_body=html_body)


def send_order_confirmation_email(order_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Soạn và gửi email thông báo đơn mua hàng mới trực tiếp về Email của Admin."""
    items_lines = "\n".join(
        f"  - {item['name']} (SL: {item['quantity']} x {item['price']:,.0f}đ) = {item['subtotal']:,.0f}đ"
        for item in order_dict.get("items", [])
    )
    admin_email = get_admin_notification_email()
    cust_email = (order_dict.get("email") or "").strip()
    total_fmt = f"{order_dict.get('total_amount', 0):,.0f}"

    subject_admin = f"🔔 [ĐƠN HÀNG MỚI #{order_dict.get('id')}] Khách {order_dict.get('customer_name')} ({order_dict.get('phone')}) - {total_fmt}đ"
    body_admin = (
        f"🔔 THÔNG BÁO ĐƠN HÀNG MỚI VỀ EMAIL ADMIN ({admin_email}):\n"
        f"Có đơn hàng mới #{order_dict.get('id')} vừa được đặt thành công trên website Meow & Woof!\n\n"
        f"👤 Khách hàng đặt: {order_dict.get('customer_name')}\n"
        f"📞 Số điện thoại: {order_dict.get('phone')}\n"
        f"✉️ Email khách hàng: {cust_email or 'Không cung cấp'}\n"
        f"🏠 Địa chỉ giao hàng: {order_dict.get('address')}\n"
        f"⏰ Thời gian đặt: {order_dict.get('created_at')}\n\n"
        f"Chi tiết sản phẩm đặt mua:\n{items_lines}\n\n"
        f"💰 TỔNG TIỀN THANH TOÁN: {total_fmt} VNĐ\n"
    )
    html_body = build_order_html_email(order_dict)

    return send_and_log_email(admin_email, subject_admin, body_admin, html_body=html_body)


def send_booking_confirmation_email(booking_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Soạn và gửi email thông báo lịch hẹn Spa mới trực tiếp về Email của Admin."""
    admin_email = get_admin_notification_email()
    cust_email = (booking_dict.get("email") or "").strip()
    total_fmt = f"{booking_dict.get('total_price', 0):,.0f}"

    subject_admin = f"🔔 [LỊCH HẸN SPA MỚI #{booking_dict.get('id')}] Bé {booking_dict.get('pet_name')} - Khách {booking_dict.get('customer_name')}"
    body_admin = (
        f"🔔 THÔNG BÁO LỊCH HẸN SPA MỚI VỀ EMAIL ADMIN ({admin_email}):\n"
        f"Có khách vừa đặt lịch Spa chăm sóc thú cưng mới trên website Meow & Woof!\n\n"
        f"Mã lịch hẹn: #{booking_dict.get('id')}\n"
        f"👤 Chủ nuôi: {booking_dict.get('customer_name')} (SĐT: {booking_dict.get('phone')})\n"
        f"✉️ Email khách hàng: {cust_email or 'Không cung cấp'}\n"
        f"🐾 Thú cưng: {booking_dict.get('pet_name')} ({booking_dict.get('pet_type')} - {booking_dict.get('pet_weight_kg')}kg)\n"
        f"🛁 Gói dịch vụ: {booking_dict.get('service_name')}\n"
        f"📅 Thời gian hẹn: {booking_dict.get('appointment_date')} lúc {booking_dict.get('appointment_time')}\n"
        f"💰 Chi phí tạm tính: {total_fmt} VNĐ\n"
    )
    html_body = build_booking_html_email(booking_dict)

    return send_and_log_email(admin_email, subject_admin, body_admin, html_body=html_body)
