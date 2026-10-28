"""
services/email_service.py
Đáp ứng CLO2 (Email trong ứng dụng Web Flask):
- Sử dụng `smtplib` và `email.message.EmailMessage` của Python để gửi email xác nhận
  Đơn hàng và Lịch hẹn Spa cho khách hàng với giao diện HTML chuẩn Brand Meow & Woof.
- Đồng thời lưu bản ghi vào bảng `email_logs` trong SQLite để giảng viên/người học có thể
  kiểm tra trực tiếp nội dung email được sinh ra ngay trên giao diện Quản trị (`/admin`)
  kể cả khi máy tính chưa cấu hình tài khoản SMTP thực tế.
"""

from email.message import EmailMessage
import json
import os
import smtplib
from typing import Any, Dict, Optional
from models.email_log import EmailLog


def get_smtp_credentials() -> Dict[str, Any]:
    """Lấy thông tin tài khoản SMTP từ Environment, file .env hoặc file data/smtp_config.json."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except (ValueError, TypeError):
        port = 587
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()

    # 1. Đọc từ file .env nếu chưa có trong biến môi trường
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
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
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

    # 2. Đọc từ data/smtp_config.json nếu đã lưu từ giao diện Quản trị Admin
    if not user or not pwd:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "smtp_config.json")
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
    """Lưu cấu hình SMTP vào file data/smtp_config.json và cập nhật biến môi trường tức thì."""
    cfg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, "smtp_config.json")
    clean_pass = smtp_pass.strip().replace(" ", "")
    data = {
        "smtp_host": smtp_host.strip() or "smtp.gmail.com",
        "smtp_port": int(smtp_port) if smtp_port else 587,
        "smtp_user": smtp_user.strip(),
        "smtp_pass": clean_pass,
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Cập nhật biến môi trường bộ nhớ để có hiệu lực ngay
    os.environ["SMTP_USER"] = data["smtp_user"]
    os.environ["SMTP_PASS"] = clean_pass
    os.environ["SMTP_HOST"] = data["smtp_host"]
    os.environ["SMTP_PORT"] = str(data["smtp_port"])


def get_admin_notification_email() -> str:
    """Lấy địa chỉ Email nhận thông báo của Admin (có thể tùy chỉnh trong trang Quản trị)."""
    admin_mail = os.environ.get("ADMIN_NOTIFICATION_EMAIL", "").strip()
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "admin_settings.json")
    if not admin_mail and os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                admin_mail = data.get("admin_notification_email", "").strip()
        except Exception:
            pass
    if not admin_mail:
        creds = get_smtp_credentials()
        admin_mail = creds.get("smtp_user") or "admin@meowandwoof.vn"
    return admin_mail


def set_admin_notification_email(email_addr: str) -> None:
    """Lưu địa chỉ Email nhận thông báo của Admin vào file data/admin_settings.json."""
    clean_mail = email_addr.strip()
    cfg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, "admin_settings.json")
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

    os.environ["ADMIN_NOTIFICATION_EMAIL"] = clean_mail


def send_test_email(recipient: str) -> Dict[str, Any]:
    """Gửi email HTML kiểm tra kết nối SMTP tới Gmail của người dùng."""
    subject = "[Meow & Woof] Kiểm tra kết nối SMTP gửi Email thành công! 🎉"
    body = (
        f"Xin chào,\n\n"
        f"Chúc mừng bạn! Máy chủ SMTP của Meow & Woof Pet House đã kết nối thành công và gửi được email tới {recipient}.\n"
        f"Kể từ bây giờ, mọi lịch hẹn Spa và đơn mua hàng tại website sẽ tự động gửi email xác nhận trực tiếp về Gmail của bạn!\n\n"
        f"Trân trọng,\nĐội ngũ Meow & Woof"
    )
    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <div style="background:linear-gradient(135deg, #10b981 0%, #3b82f6 100%); border-radius:24px 24px 0 0; padding:32px 24px; text-align:center;">
    <div style="display:inline-block; width:52px; height:52px; border-radius:16px; background:#ffffff; line-height:52px; font-size:26px; margin-bottom:12px;">✅</div>
    <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff;">KẾT NỐI SMTP THÀNH CÔNG!</h1>
    <p style="margin:6px 0 0; font-size:13.5px; color:#dbeafe; font-weight:700;">HỆ THỐNG EMAIL TỰ ĐỘNG ĐÃ SẴN SÀNG HOẠT ĐỘNG</p>
  </div>
  <div style="background:#15102d; border:1px solid rgba(59,130,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:28px 24px;">
    <p style="margin:0 0 16px; font-size:14.5px; color:#e2e8f0; line-height:1.6;">
      Xin chào Admin Meow &amp; Woof,<br>
      Email này được gửi thử nghiệm thành công tới <strong>{recipient}</strong>. Cấu hình gửi mail qua máy chủ Google SMTP của bạn đã hoàn tất chuẩn chỉnh 100%!
    </p>
    <div style="background:#1d173e; border-radius:16px; padding:16px; margin:18px 0; font-size:13px; color:#cbd5e1; line-height:1.6;">
      <div>🐾 <strong>Đơn hàng mới:</strong> Tự động gửi hóa đơn và mã vận chuyển đến khách.</div>
      <div>🐾 <strong>Lịch hẹn Spa:</strong> Tự động gửi vé điện tử 5 sao kèm mã giữ chỗ.</div>
    </div>
    <div style="text-align:center; margin-top:20px; font-size:12px; color:#94a3b8;">
      Meow &amp; Woof Pet House &amp; Spa Chó Mèo
    </div>
  </div>
</div>
</body>
</html>"""
    return send_and_log_email(recipient, subject, body, html_body=html_body)



def build_booking_html_email(booking_dict: Dict[str, Any]) -> str:
    """Tạo giao diện HTML Email vé hẹn Spa mang phong cách Gen Z Dark Glass chuẩn Brand Meow & Woof."""
    b_id = booking_dict.get("id", "")
    cust_name = booking_dict.get("customer_name", "Quý khách")
    pet_name = booking_dict.get("pet_name", "Bé cưng")
    pet_type = booking_dict.get("pet_type", "Thú cưng")
    pet_weight = booking_dict.get("pet_weight_kg", "4.0")
    service_name = booking_dict.get("service_name", "Spa Chăm Sóc")
    app_date = booking_dict.get("appointment_date", "")
    app_time = booking_dict.get("appointment_time", "")
    total_price = f"{booking_dict.get('total_price', 0):,.0f}"
    note = booking_dict.get("note", "") or "Không có dặn dò đặc biệt"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vé Hẹn Spa #{b_id} - Meow &amp; Woof</title>
</head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <!-- Header Card -->
  <div style="background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 50%, #ff5d73 100%); border-radius:24px 24px 0 0; padding:32px 24px; text-align:center;">
    <div style="display:inline-block; width:52px; height:52px; border-radius:16px; background:#ffffff; line-height:52px; font-size:26px; margin-bottom:12px; box-shadow:0 8px 20px rgba(0,0,0,0.25);">🐾</div>
    <h1 style="margin:0; font-size:24px; font-weight:800; color:#ffffff; letter-spacing:-0.5px;">Meow &amp; Woof Pet House &amp; Spa</h1>
    <p style="margin:6px 0 0; font-size:13.5px; color:#fde047; font-weight:700;">✨ VÉ XÁC NHẬN LỊCH HẸN SPA HOÀNG GIA 5 SAO ✨</p>
  </div>

  <!-- Body Card -->
  <div style="background:#15102d; border:1px solid rgba(139,92,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:28px 24px; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
    <p style="margin:0 0 16px; font-size:15px; color:#e2e8f0; line-height:1.6;">
      Xin chào <strong>{cust_name}</strong>,<br>
      Meow &amp; Woof đã nhận được yêu cầu đặt lịch hẹn chăm sóc cho bé <strong>{pet_name}</strong>. Kỹ thuật viên Spa đang sẵn sàng đón tiếp bé với liệu trình chuẩn quốc tế!
    </p>

    <!-- Ticket Box -->
    <div style="background:#1d173e; border:1.5px dashed #8b5cf6; border-radius:18px; padding:20px; margin:20px 0;">
      <div style="display:flex; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:12px; margin-bottom:12px;">
        <span style="font-size:12px; color:#a39ecb; text-transform:uppercase; font-weight:700;">MÃ LỊCH HẸN</span>
        <span style="font-size:14px; color:#38bdf8; font-weight:800;">#{b_id}</span>
      </div>
      <table style="width:100%; border-collapse:collapse; font-size:13.5px; color:#e2e8f0;">
        <tr>
          <td style="padding:6px 0; color:#94a3b8; width:130px;">Dịch vụ đăng ký:</td>
          <td style="padding:6px 0; font-weight:700; color:#ffffff;">{service_name}</td>
        </tr>
        <tr>
          <td style="padding:6px 0; color:#94a3b8;">Bé thú cưng:</td>
          <td style="padding:6px 0; font-weight:700; color:#ffffff;">{pet_name} ({pet_type} - {pet_weight} kg)</td>
        </tr>
        <tr>
          <td style="padding:6px 0; color:#94a3b8;">Thời gian hẹn:</td>
          <td style="padding:6px 0; font-weight:700; color:#facc15;">📅 {app_date} lúc ⏰ {app_time}</td>
        </tr>
        <tr>
          <td style="padding:6px 0; color:#94a3b8;">Chi phí tạm tính:</td>
          <td style="padding:6px 0; font-weight:800; font-size:17px; color:#34d399;">{total_price} đ</td>
        </tr>
        <tr>
          <td style="padding:6px 0; color:#94a3b8;">Ghi chú của bạn:</td>
          <td style="padding:6px 0; color:#cbd5e1; font-style:italic;">{note}</td>
        </tr>
      </table>
    </div>

    <!-- Reminder Box -->
    <div style="background:rgba(16,185,129,0.1); border-left:4px solid #10b981; border-radius:10px; padding:12px 16px; margin:20px 0; font-size:13px; color:#cbd5e1; line-height:1.5;">
      💡 <strong>Lưu ý nhỏ:</strong> Bạn vui lòng đưa bé đến trước giờ hẹn <strong>10 phút</strong> để bác sĩ kiểm tra da lông miễn phí và làm quen với bé trước khi tắm sấy nhé!
    </div>

    <!-- CTA Button -->
    <div style="text-align:center; margin:28px 0 16px;">
      <a href="https://chomeo.vercel.app/spa" style="display:inline-block; padding:12px 30px; background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:800; font-size:14px; box-shadow:0 6px 20px rgba(139,92,246,0.4);">🐾 Mở Website Meow &amp; Woof</a>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:18px; margin-top:20px; font-size:12px; color:#94a3b8; text-align:center; line-height:1.6;">
      Meow &amp; Woof Pet House &amp; Spa Chó Mèo<br>
      ⏰ Giờ mở cửa: 08:00 – 21:00 hàng ngày • 📞 Hotline: 0905.123.456<br>
      Địa chỉ: Cửa hàng thú cưng &amp; Spa 5 sao Meow &amp; Woof toàn quốc.
    </div>
  </div>
</div>
</body>
</html>"""


def build_order_html_email(order_dict: Dict[str, Any]) -> str:
    """Tạo giao diện HTML Email xác nhận đơn mua hàng chuẩn Brand Meow & Woof."""
    order_id = order_dict.get("id", "")
    cust_name = order_dict.get("customer_name", "Quý khách")
    phone = order_dict.get("phone", "")
    address = order_dict.get("address", "")
    created_at = order_dict.get("created_at", "")
    total_amount = f"{order_dict.get('total_amount', 0):,.0f}"

    rows_html = ""
    for item in order_dict.get("items", []):
        sub = f"{item['subtotal']:,.0f}"
        pr = f"{item['price']:,.0f}"
        rows_html += f"""
        <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
          <td style="padding:10px 0; color:#ffffff; font-weight:700;">{item['name']}</td>
          <td style="padding:10px 0; text-align:center; color:#cbd5e1;">x{item['quantity']}</td>
          <td style="padding:10px 0; text-align:right; color:#34d399; font-weight:700;">{sub} đ</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Đơn hàng #{order_id} - Meow &amp; Woof</title>
</head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <!-- Header Card -->
  <div style="background:linear-gradient(135deg, #10b981 0%, #3b82f6 100%); border-radius:24px 24px 0 0; padding:32px 24px; text-align:center;">
    <div style="display:inline-block; width:52px; height:52px; border-radius:16px; background:#ffffff; line-height:52px; font-size:26px; margin-bottom:12px; box-shadow:0 8px 20px rgba(0,0,0,0.25);">🛍️</div>
    <h1 style="margin:0; font-size:24px; font-weight:800; color:#ffffff;">Cảm Ơn Bạn Đã Mua Sắm!</h1>
    <p style="margin:6px 0 0; font-size:13.5px; color:#dbeafe; font-weight:700;">ĐƠN HÀNG #{order_id} ĐÃ ĐƯỢC XÁC NHẬN THÀNH CÔNG</p>
  </div>

  <!-- Body Card -->
  <div style="background:#15102d; border:1px solid rgba(59,130,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:28px 24px; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
    <p style="margin:0 0 16px; font-size:15px; color:#e2e8f0; line-height:1.6;">
      Xin chào <strong>{cust_name}</strong>,<br>
      Meow &amp; Woof đang chuẩn bị đóng gói cẩn thận các món đồ cho bé cưng của bạn. Đơn hàng sẽ được chuyển tới đơn vị vận chuyển hỏa tốc trong thời gian sớm nhất!
    </p>

    <!-- Info Box -->
    <div style="background:#1d173e; border-radius:16px; padding:16px 20px; margin:18px 0; font-size:13px; color:#cbd5e1; line-height:1.6;">
      <div><strong>Người nhận:</strong> {cust_name} ({phone})</div>
      <div><strong>Địa chỉ giao:</strong> {address}</div>
      <div><strong>Thời gian đặt:</strong> {created_at}</div>
    </div>

    <!-- Products Table -->
    <table style="width:100%; border-collapse:collapse; font-size:13.5px; margin:20px 0;">
      <thead>
        <tr style="border-bottom:1.5px solid rgba(255,255,255,0.15); color:#94a3b8; font-size:12px; text-transform:uppercase;">
          <th style="text-align:left; padding-bottom:8px;">Sản phẩm</th>
          <th style="text-align:center; padding-bottom:8px;">SL</th>
          <th style="text-align:right; padding-bottom:8px;">Thành tiền</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="2" style="padding-top:14px; font-weight:800; font-size:15px; color:#ffffff;">TỔNG THANH TOÁN:</td>
          <td style="padding-top:14px; text-align:right; font-weight:800; font-size:18px; color:#34d399;">{total_amount} đ</td>
        </tr>
      </tfoot>
    </table>

    <div style="text-align:center; margin:28px 0 16px;">
      <a href="https://chomeo.vercel.app/" style="display:inline-block; padding:12px 30px; background:linear-gradient(135deg, #10b981 0%, #3b82f6 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:800; font-size:14px;">🛍️ Khám Phá Thêm Sản Phẩm Khác</a>
    </div>

    <div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:18px; margin-top:20px; font-size:12px; color:#94a3b8; text-align:center; line-height:1.6;">
      Meow &amp; Woof Pet House &amp; Spa Chó Mèo<br>
      Hotline hỗ trợ đơn hàng: 0905.123.456 • Email: support@meowandwoof.vn
    </div>
  </div>
</div>
</body>
</html>"""


def build_marketing_html_email(recipient: str, subject: str, body: str) -> str:
    """Tạo giao diện HTML Email ưu đãi / tri ân khách hàng chuẩn Brand Meow & Woof."""
    paragraphs = "".join(
        f"<p style='margin:0 0 12px; font-size:14.5px; color:#e2e8f0; line-height:1.6;'>{p.strip()}</p>"
        for p in body.split("\n")
        if p.strip()
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
</head>
<body style="margin:0; padding:0; background-color:#0b081d; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#ffffff;">
<div style="max-width:600px; margin:0 auto; padding:24px 16px;">
  <!-- Header Card -->
  <div style="background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 50%, #f59e0b 100%); border-radius:24px 24px 0 0; padding:32px 24px; text-align:center;">
    <div style="display:inline-block; width:52px; height:52px; border-radius:16px; background:#ffffff; line-height:52px; font-size:26px; margin-bottom:12px; box-shadow:0 8px 20px rgba(0,0,0,0.25);">🎁</div>
    <h1 style="margin:0; font-size:24px; font-weight:800; color:#ffffff; letter-spacing:-0.5px;">Meow &amp; Woof Pet House &amp; Spa</h1>
    <p style="margin:6px 0 0; font-size:13.5px; color:#fef08a; font-weight:700;">✨ ĐẶC QUYỀN TRI ÂN DÀNH CHO KHÁCH HÀNG THÂN THIẾT ✨</p>
  </div>

  <!-- Body Card -->
  <div style="background:#15102d; border:1px solid rgba(139,92,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:28px 24px; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
    <div style="margin-bottom:20px;">
      {paragraphs}
    </div>

    <!-- Special Promo Code Box -->
    <div style="background:linear-gradient(135deg, rgba(139,92,246,0.18) 0%, rgba(245,158,11,0.15) 100%); border:1.5px dashed #f59e0b; border-radius:18px; padding:18px; text-align:center; margin:22px 0;">
      <div style="font-size:12px; color:#fde047; font-weight:800; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px;">MÃ ƯU ĐÃI ĐẶC QUYỀN VIP</div>
      <div style="font-size:24px; font-weight:900; color:#ffffff; letter-spacing:2px; font-family:monospace; background:rgba(0,0,0,0.35); padding:8px 18px; border-radius:10px; display:inline-block; border:1px solid rgba(255,255,255,0.2);">MEOWWOOF-VIP20</div>
      <div style="font-size:12.5px; color:#cbd5e1; margin-top:8px;">Giảm ngay 20% cho toàn bộ dịch vụ Spa &amp; phụ kiện chó mèo khi đặt tại website!</div>
    </div>

    <!-- CTA Button -->
    <div style="text-align:center; margin:28px 0 16px;">
      <a href="https://chomeo.vercel.app/" style="display:inline-block; padding:12px 32px; background:linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:800; font-size:14px; box-shadow:0 6px 20px rgba(139,92,246,0.4);">🐾 Nhận Ngay Ưu Đãi Tại Shop</a>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:18px; margin-top:20px; font-size:12px; color:#94a3b8; text-align:center; line-height:1.6;">
      Meow &amp; Woof Pet House &amp; Spa Chó Mèo<br>
      ⏰ Giờ mở cửa: 08:00 – 21:00 hàng ngày • 📞 Hotline: 0905.123.456<br>
      Cửa hàng thú cưng &amp; Spa 5 sao Meow &amp; Woof toàn quốc.
    </div>
  </div>
</div>
</body>
</html>"""



def send_and_log_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gửi email qua giao thức SMTP (hỗ trợ cả nội dung Plain Text và HTML phong cách Meow & Woof)
    và lưu lịch sử vào bảng `email_logs`.
    """
    recipient_addr = recipient.strip() if recipient and recipient.strip() else "khachhang@petshop.local"
    creds = get_smtp_credentials()
    smtp_host = creds["smtp_host"]
    smtp_port = creds["smtp_port"]
    smtp_user = creds["smtp_user"]
    smtp_pass = creds["smtp_pass"]

    status = "Đã lưu vào hộp thư hệ thống (Chưa cấu hình tài khoản gửi Gmail SMTP)"

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

    # 1. Gửi trực tiếp về Email của Admin
    admin_res = send_and_log_email(admin_email, subject_admin, body_admin, html_body=html_body)

    # 2. Nếu khách có nhập email và khác email admin thì gửi thêm cho khách
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

    subject_admin = f"🔔 [LỊCH HẸN SPA MỚI #{booking_dict.get('id')}] Bé {booking_dict.get('pet_name')} - {booking_dict.get('customer_name')} ({booking_dict.get('appointment_date')} {booking_dict.get('appointment_time')})"
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
        f"📝 Ghi chú: {booking_dict.get('note') or 'Không có'}\n"
    )
    html_body = build_booking_html_email(booking_dict)

    # 1. Gửi trực tiếp về Email của Admin
    admin_res = send_and_log_email(admin_email, subject_admin, body_admin, html_body=html_body)

    # 2. Nếu khách có nhập email và khác email admin thì gửi thêm cho khách
    if cust_email and cust_email.lower() != admin_email.lower():
        subject_cust = f"[Meow & Woof Spa] Vé hẹn Spa #{booking_dict.get('id')} cho bé {booking_dict.get('pet_name')}"
        body_cust = (
            f"Xin chào {booking_dict.get('customer_name')},\n\n"
            f"Lịch hẹn chăm sóc thú cưng của bạn tại Meow & Woof Spa đã được ghi nhận:\n"
            f"  - Mã lịch hẹn: #{booking_dict.get('id')}\n"
            f"  - Thú cưng: {booking_dict.get('pet_name')} ({booking_dict.get('pet_type')} - {booking_dict.get('pet_weight_kg')}kg)\n"
            f"  - Gói dịch vụ: {booking_dict.get('service_name')}\n"
            f"  - Ngày giờ hẹn: {booking_dict.get('appointment_date')} lúc {booking_dict.get('appointment_time')}\n"
            f"  - Chi phí dự kiến: {total_fmt} VNĐ\n"
        )
        send_and_log_email(cust_email, subject_cust, body_cust, html_body=html_body)

    return admin_res


