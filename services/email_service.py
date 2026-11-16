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


# Mật khẩu cũ đã bị lộ/Google thu hồi không được dùng lại từ cookie/config cũ
_REVOKED_SMTP_PASSWORDS = {"trismoetogzmbgii"}

# Token FormSubmit mặc định sau khi Admin xác nhận email trên Vercel (tránh dùng naked email gây thư Activate)
_FORMSUBMIT_ALIASES = {
    "trungvt040106@gmail.com": "ca5afce49d988ba07deb8a95944c2875",
}


def is_revoked_smtp_password(pwd: str) -> bool:
    clean = (pwd or "").strip().replace(" ", "")
    return clean in _REVOKED_SMTP_PASSWORDS


def get_formsubmit_token_for_email(email_addr: str) -> str:
    """Trả về FormSubmit token đã kích hoạt tương ứng với email Admin (tránh dùng naked email)."""
    env_tok = os.environ.get("FORMSUBMIT_TOKEN", "").strip()
    if env_tok:
        return env_tok
    return _FORMSUBMIT_ALIASES.get((email_addr or "").strip().lower(), "")


def get_smtp_credentials() -> Dict[str, Any]:
    """Lấy thông tin tài khoản SMTP từ biến môi trường, .env hoặc data/smtp_config.json."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except (ValueError, TypeError):
        port = 587
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()
    if is_revoked_smtp_password(pwd):
        pwd = ""

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
                            elif k == "SMTP_PASS" and not pwd and not is_revoked_smtp_password(v):
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
                    cfg_pwd = cfg.get("smtp_pass", "").strip()
                    if not pwd and not is_revoked_smtp_password(cfg_pwd):
                        pwd = cfg_pwd
                    host = cfg.get("smtp_host", host) or host
                    port = int(cfg.get("smtp_port", port) or port)
            except Exception:
                pass

    DEFAULT_USER = "trungvt040106@gmail.com"
    if not user:
        user = DEFAULT_USER

    return {
        "smtp_host": host or "smtp.gmail.com",
        "smtp_port": port or 587,
        "smtp_user": user,
        "smtp_pass": pwd.replace(" ", ""),
    }


def save_smtp_credentials(smtp_user: str, smtp_pass: str, smtp_host: str = "smtp.gmail.com", smtp_port: int = 587) -> None:
    """Lưu cấu hình SMTP an toàn (tương thích 100% với Vercel Serverless & Local)."""
    clean_pass = smtp_pass.strip().replace(" ", "")
    if is_revoked_smtp_password(clean_pass):
        clean_pass = ""
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
        admin_mail = creds.get("smtp_user") or "trungvt040106@gmail.com"
    return admin_mail or "trungvt040106@gmail.com"


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
    """Tạo giao diện HTML Email thông báo lịch hẹn Spa 5 sao chuẩn Brand Meow & Woof."""
    from html import escape

    b_id = escape(str(booking.get("id", "")))
    cust = escape(str(booking.get("customer_name", "Quý khách")))
    phone = escape(str(booking.get("phone", "")))
    email_cust = escape(str(booking.get("email", "") or "Không cung cấp"))
    pet_name = escape(str(booking.get("pet_name", "Bé cưng")))
    p_type = escape(str(booking.get("pet_type", "Thú cưng")))
    weight = escape(str(booking.get("pet_weight_kg", "4.0")))
    service = escape(str(booking.get("service_name", "Spa")))
    app_d = escape(str(booking.get("appointment_date", "")))
    app_t = escape(str(booking.get("appointment_time", "")))
    price = f"{float(booking.get('total_price', 0) or 0):,.0f}"
    note = escape(str(booking.get("note", "") or "Không có ghi chú"))

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4efe6;font-family:'Segoe UI',Arial,sans-serif;color:#2b180d;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4efe6;padding:24px 12px;"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;border:1px solid #eadfca;overflow:hidden;box-shadow:0 12px 32px rgba(43,24,13,0.10);">
  <tr><td style="padding:0;"><div style="height:6px;background:linear-gradient(90deg,#8b5cf6,#ec4899,#f97316);"></div></td></tr>
  <tr><td align="center" style="padding:26px 28px 18px;background:linear-gradient(180deg,#fffaf3 0%,#ffffff 100%);border-bottom:1px solid #f1e6d6;">
    <div style="display:inline-block;padding:5px 14px;border-radius:999px;background:#f3e8ff;color:#7e22ce;font-size:11px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">🐾 THÔNG BÁO ĐẶT LỊCH SPA MỚI</div>
    <h1 style="margin:10px 0 4px;font-size:22px;font-weight:800;color:#2b180d;">Lịch Hẹn Spa #{b_id}</h1>
    <div style="font-size:13px;color:#786152;">Meow &amp; Woof Pet House &amp; Spa • Dịch vụ chăm sóc 5 sao</div>
  </td></tr>
  <tr><td style="padding:18px 28px 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#faf5ff 0%,#fff7ed 100%);border:1.5px solid #e9d5ff;border-radius:12px;">
      <tr>
        <td style="padding:14px 18px;">
          <div style="font-size:11px;font-weight:800;color:#7e22ce;text-transform:uppercase;letter-spacing:0.8px;">Chi phí tạm tính</div>
          <div style="font-size:24px;font-weight:900;color:#c2410c;margin-top:2px;">{price} đ</div>
        </td>
        <td align="right" style="padding:14px 18px;vertical-align:middle;">
          <div style="font-size:12px;color:#6e5444;font-weight:700;">📅 {app_d}</div>
          <div style="font-size:15px;font-weight:800;color:#2b180d;margin-top:2px;">⏰ {app_t}</div>
        </td>
      </tr>
    </table>
  </td></tr>
  <tr><td style="padding:12px 28px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fffdf9;border:1px solid #f0e6d8;border-radius:12px;font-size:13.5px;">
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;width:140px;font-weight:700;">👤 Chủ nuôi</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#2b180d;font-weight:700;">{cust}</td></tr>
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;font-weight:700;">📞 Điện thoại</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;"><a href="tel:{phone}" style="color:#ea580c;font-weight:800;text-decoration:none;">{phone}</a></td></tr>
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;font-weight:700;">✉️ Email</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#2b180d;">{email_cust}</td></tr>
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;font-weight:700;">🐾 Bé cưng</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#2b180d;font-weight:700;">{pet_name} ({p_type} • {weight} kg)</td></tr>
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;font-weight:700;">🛁 Gói dịch vụ</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#7e22ce;font-weight:700;">{service}</td></tr>
      <tr><td style="padding:10px 16px;color:#786152;font-weight:700;">📝 Ghi chú</td><td style="padding:10px 16px;color:#503829;">{note}</td></tr>
    </table>
  </td></tr>
  <tr><td align="center" style="padding:14px 28px 22px;">
    <a href="https://chomeo.vercel.app/admin?tab=bookings" style="display:inline-block;padding:12px 30px;background:linear-gradient(135deg,#8b5cf6 0%,#ec4899 100%);color:#ffffff;text-decoration:none;border-radius:999px;font-weight:800;font-size:14px;">🛁 Mở Quản Lý Lịch Hẹn Spa &rarr;</a>
  </td></tr>
  <tr><td align="center" style="padding:16px 28px 22px;background:#faf6ef;border-top:1px solid #efe6d8;">
    <div style="font-size:11.5px;color:#8c7765;line-height:1.7;"><strong>Meow &amp; Woof Pet House &amp; Spa</strong> • Hotline: 0905.123.456<br>245 Nguyễn Thị Minh Khai, Quận 1, TP.HCM • Mở cửa 08:00 – 21:00</div>
  </td></tr>
</table></td></tr></table></body></html>"""


def build_order_html_email(order: Dict[str, Any]) -> str:
    """Tạo giao diện HTML Email thông báo đơn hàng mới cho Admin sang trọng, rõ ràng."""
    from html import escape

    o_id = escape(str(order.get("id", "")))
    cust = escape(str(order.get("customer_name", "Quý khách")))
    phone = escape(str(order.get("phone", "")))
    cust_email = escape(str(order.get("email", "") or "Không cung cấp"))
    addr = escape(str(order.get("address", "")))
    cr_at = escape(str(order.get("created_at", "")))
    pm_raw = str(order.get("payment_method", "cod") or "cod").strip().lower()
    pm_label = "💳 Chuyển khoản VietQR 24/7" if pm_raw == "banking" or pm_raw == "vietqr" else "💵 Thu tiền khi nhận (COD)"
    status_lbl = escape(str(order.get("status", "Chờ xác nhận") or "Chờ xác nhận"))
    voucher_code = escape(str(order.get("voucher_code", "") or ""))
    try:
        discount_val = float(order.get("discount_amount", 0) or 0)
    except (TypeError, ValueError):
        discount_val = 0.0
    try:
        total_val = float(order.get("total_amount", 0) or 0)
    except (TypeError, ValueError):
        total_val = 0.0
    total = f"{total_val:,.0f}"

    rows_html = []
    for it in order.get("items", []):
        it_name = escape(str(it.get("name", "Sản phẩm")))
        it_sku = escape(str(it.get("sku", "")))
        qty = int(it.get("quantity", 1) or 1)
        sub = float(it.get("subtotal", 0) or 0)
        sku_badge = f"<div style='font-size:11px;color:#8c7765;margin-top:2px;'>SKU: {it_sku}</div>" if it_sku else ""
        rows_html.append(
            f"<tr>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #f3ebe0;color:#2b180d;'><strong>{it_name}</strong>{sku_badge}</td>"
            f"<td style='padding:10px 8px;border-bottom:1px solid #f3ebe0;text-align:center;color:#503829;font-weight:700;'>x{qty}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #f3ebe0;text-align:right;color:#c2410c;font-weight:800;white-space:nowrap;'>{sub:,.0f} đ</td>"
            f"</tr>"
        )
    rows = "".join(rows_html)

    discount_row = ""
    if voucher_code and discount_val > 0:
        discount_row = (
            f"<tr><td colspan='2' style='padding:8px 12px;color:#047857;font-weight:700;font-size:13px;'>"
            f"🎟️ Giảm giá Voucher (<code>{voucher_code}</code>)</td>"
            f"<td style='padding:8px 12px;text-align:right;color:#047857;font-weight:800;'>-{discount_val:,.0f} đ</td></tr>"
        )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4efe6;font-family:'Segoe UI',Arial,sans-serif;color:#2b180d;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4efe6;padding:24px 12px;"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;border:1px solid #eadfca;overflow:hidden;box-shadow:0 12px 32px rgba(43,24,13,0.10);">
  <tr><td style="padding:0;"><div style="height:6px;background:linear-gradient(90deg,#f97316,#ec4899,#8b5cf6);"></div></td></tr>
  <tr><td align="center" style="padding:26px 28px 18px;background:linear-gradient(180deg,#fffaf3 0%,#ffffff 100%);border-bottom:1px solid #f1e6d6;">
    <div style="display:inline-block;padding:5px 14px;border-radius:999px;background:#fff1e6;color:#ea580c;font-size:11px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">🛍️ THÔNG BÁO ĐƠN HÀNG MỚI VỀ ADMIN</div>
    <h1 style="margin:10px 0 4px;font-size:23px;font-weight:800;color:#2b180d;">Đơn Hàng #{o_id}</h1>
    <div style="font-size:13px;color:#786152;">Meow &amp; Woof Pet House &amp; Spa • {cr_at}</div>
  </td></tr>
  <tr><td style="padding:18px 28px 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#fff7ed 0%,#fffbeb 100%);border:1.5px solid #fed7aa;border-radius:12px;">
      <tr>
        <td style="padding:14px 18px;">
          <div style="font-size:11px;font-weight:800;color:#9a3412;text-transform:uppercase;letter-spacing:0.8px;">Tổng tiền thanh toán</div>
          <div style="font-size:26px;font-weight:900;color:#ea580c;margin-top:2px;">{total} đ</div>
        </td>
        <td align="right" style="padding:14px 18px;vertical-align:middle;">
          <div style="display:inline-block;padding:4px 10px;border-radius:999px;background:#ecfdf5;color:#047857;font-size:11.5px;font-weight:800;border:1px solid #a7f3d0;">{status_lbl}</div>
          <div style="font-size:12px;color:#6e5444;font-weight:700;margin-top:6px;">{pm_label}</div>
        </td>
      </tr>
    </table>
  </td></tr>
  <tr><td style="padding:10px 28px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fffdf9;border:1px solid #f0e6d8;border-radius:12px;font-size:13.5px;">
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;width:130px;font-weight:700;">👤 Khách hàng</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#2b180d;font-weight:800;">{cust}</td></tr>
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;font-weight:700;">📞 Điện thoại</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;"><a href="tel:{phone}" style="color:#ea580c;font-weight:800;text-decoration:none;">{phone}</a></td></tr>
      <tr><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#786152;font-weight:700;">✉️ Email</td><td style="padding:10px 16px;border-bottom:1px solid #f5ede2;color:#2b180d;">{cust_email}</td></tr>
      <tr><td style="padding:10px 16px;color:#786152;font-weight:700;">🏠 Địa chỉ giao</td><td style="padding:10px 16px;color:#2b180d;line-height:1.5;">{addr}</td></tr>
    </table>
  </td></tr>
  <tr><td style="padding:8px 28px 6px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #f0e6d8;border-radius:12px;overflow:hidden;font-size:13.5px;">
      <thead>
        <tr style="background:#faf4eb;color:#6e5444;">
          <th style="padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;">Sản phẩm / Thú cưng</th>
          <th style="padding:10px 8px;text-align:center;font-size:12px;text-transform:uppercase;">SL</th>
          <th style="padding:10px 12px;text-align:right;font-size:12px;text-transform:uppercase;">Thành tiền</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
      <tfoot>
        {discount_row}
        <tr style="background:#fff8f0;">
          <td colspan="2" style="padding:12px;font-weight:800;font-size:14px;color:#2b180d;border-top:1.5px solid #fed7aa;">TỔNG CỘNG THANH TOÁN</td>
          <td style="padding:12px;text-align:right;font-weight:900;font-size:17px;color:#ea580c;border-top:1.5px solid #fed7aa;white-space:nowrap;">{total} đ</td>
        </tr>
      </tfoot>
    </table>
  </td></tr>
  <tr><td align="center" style="padding:16px 28px 22px;">
    <a href="https://chomeo.vercel.app/admin?tab=orders" style="display:inline-block;padding:12px 30px;background:linear-gradient(135deg,#f97316 0%,#ea580c 100%);color:#ffffff;text-decoration:none;border-radius:999px;font-weight:800;font-size:14px;">📋 Mở Quản Trị Đơn Hàng &rarr;</a>
  </td></tr>
  <tr><td align="center" style="padding:16px 28px 22px;background:#faf6ef;border-top:1px solid #efe6d8;">
    <div style="font-size:11.5px;color:#8c7765;line-height:1.7;"><strong>Meow &amp; Woof Pet House &amp; Spa</strong> • Hotline: 0905.123.456<br>245 Nguyễn Thị Minh Khai, Quận 1, TP.HCM • Mở cửa 08:00 – 21:00</div>
  </td></tr>
</table></td></tr></table></body></html>"""


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


def build_voucher_html_email(recipient: str, subject: str, body: str, voucher: Optional[Dict[str, Any]] = None) -> str:
    """Thư mời voucher dạng 'lá thư' giấy kem sang trọng: thương hiệu, mã voucher, mức giảm và thời hạn."""
    from html import escape

    v = voucher or {}
    code = escape(str(v.get("code", "") or "MEOWWOOF-VIP"))
    title = escape(str(v.get("title", "") or subject or "Ưu đãi dành riêng cho bạn"))
    try:
        val = float(v.get("discount_value", 0) or 0)
    except (TypeError, ValueError):
        val = 0.0
    if v.get("discount_type") == "percent":
        big = f"GIẢM {val:g}%"
    else:
        big = f"GIẢM {val:,.0f}đ"
    try:
        min_order = float(v.get("min_order_value", 0) or 0)
    except (TypeError, ValueError):
        min_order = 0.0
    start = escape(str(v.get("start_date", "") or "Hôm nay"))
    expiry = escape(str(v.get("expiry_date", "") or "Không giới hạn"))
    min_txt = f"Đơn từ {min_order:,.0f}đ" if min_order > 0 else "Áp dụng cho mọi đơn hàng"
    name_part = escape(recipient.split("@")[0]) if recipient else "bạn"

    paras = "".join(
        f"<p style='margin:0 0 12px;font-size:15px;line-height:1.7;color:#4a3f35;'>{escape(p.strip())}</p>"
        for p in (body or "").split("\n")
        if p.strip()
    )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#efe7da;font-family:Georgia,'Times New Roman',serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#efe7da;padding:28px 12px;"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fffdf8;border-radius:6px;border:1px solid #e0d3bd;box-shadow:0 10px 30px rgba(90,70,40,0.18);">
  <tr><td style="padding:0;"><div style="height:8px;background:linear-gradient(90deg,#8b5cf6,#ec4899,#f59e0b);border-radius:6px 6px 0 0;"></div></td></tr>
  <tr><td align="center" style="padding:30px 28px 8px;">
    <div style="font-size:34px;line-height:1;">🐾</div>
    <div style="font-family:Georgia,serif;font-size:26px;font-weight:bold;letter-spacing:3px;color:#3b2a5a;margin-top:8px;">MEOW &amp; WOOF</div>
    <div style="font-size:12px;letter-spacing:4px;color:#b08a4a;margin-top:4px;text-transform:uppercase;">Pet House &amp; Spa</div>
    <div style="width:70px;height:2px;background:#d9b873;margin:16px auto 0;"></div>
  </td></tr>
  <tr><td style="padding:18px 38px 4px;">
    <p style="margin:0 0 14px;font-size:17px;color:#3b2a5a;font-style:italic;">Thân gửi {name_part},</p>
    {paras}
  </td></tr>
  <tr><td align="center" style="padding:8px 30px 6px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fff7e6;border:2px dashed #d9a441;border-radius:14px;">
      <tr><td align="center" style="padding:22px 16px 6px;">
        <div style="font-size:11px;letter-spacing:3px;color:#a2762a;font-weight:bold;">VOUCHER ƯU ĐÃI</div>
        <div style="font-size:15px;color:#6b5a45;margin-top:6px;">{title}</div>
        <div style="font-family:Georgia,serif;font-size:38px;font-weight:bold;color:#c2255c;margin:10px 0 2px;">{big}</div>
        <div style="font-size:12.5px;color:#8a7a62;">{min_txt}</div>
      </td></tr>
      <tr><td align="center" style="padding:10px 16px 8px;">
        <div style="display:inline-block;background:#3b2a5a;color:#fde68a;font-family:'Courier New',monospace;font-size:26px;font-weight:bold;letter-spacing:5px;padding:10px 26px;border-radius:10px;">{code}</div>
      </td></tr>
      <tr><td align="center" style="padding:6px 16px 22px;">
        <div style="font-size:13px;color:#6b5a45;">⏰ Hiệu lực: <b>{start}</b> &rarr; <b>{expiry}</b></div>
      </td></tr>
    </table>
  </td></tr>
  <tr><td style="padding:16px 38px 4px;">
    <p style="margin:0;font-size:13.5px;line-height:1.7;color:#6b5a45;">👉 <b>Cách dùng:</b> chọn sản phẩm, vào <b>Giỏ hàng &amp; Thanh toán</b>, nhập mã <b>{code}</b> vào ô Mã giảm giá để được trừ tiền ngay.</p>
  </td></tr>
  <tr><td align="center" style="padding:20px 28px 8px;">
    <a href="https://chomeo.vercel.app/shop" style="display:inline-block;background:linear-gradient(135deg,#8b5cf6,#ec4899);color:#ffffff;text-decoration:none;font-family:'Segoe UI',Arial,sans-serif;font-weight:bold;font-size:14.5px;padding:13px 34px;border-radius:99px;">Mua sắm ngay &rarr;</a>
  </td></tr>
  <tr><td style="padding:22px 38px 8px;">
    <p style="margin:0;font-size:15px;color:#3b2a5a;font-style:italic;">Trân trọng,</p>
    <p style="margin:2px 0 0;font-size:16px;color:#3b2a5a;font-weight:bold;">Đội ngũ Meow &amp; Woof 🐶🐱</p>
  </td></tr>
  <tr><td align="center" style="padding:18px 28px 26px;border-top:1px solid #eadfca;">
    <div style="font-family:'Segoe UI',Arial,sans-serif;font-size:11.5px;color:#a59880;line-height:1.7;">Meow &amp; Woof Pet House &amp; Spa • 245 Nguyễn Thị Minh Khai, Quận 1, TP.HCM<br>Hotline 0905.123.456 • Mở cửa 08:00 – 21:00</div>
  </td></tr>
</table></td></tr></table></body></html>"""


def _send_via_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    msg: EmailMessage,
) -> tuple:
    """
    Gửi EmailMessage qua SMTP, tự động thử cổng 465 (SSL) nếu cổng 587 (STARTTLS) lỗi mạng,
    và phân biệt rõ lỗi sai/thu hồi App Password (535) với lỗi kết nối.
    """
    attempts = [(smtp_port, smtp_port == 465)]
    if smtp_port != 465:
        attempts.append((465, True))

    last_err = ""
    for port, use_ssl in attempts:
        stage = "connect"
        try:
            if use_ssl:
                server_cm = smtplib.SMTP_SSL(smtp_host, port, timeout=10)
            else:
                server_cm = smtplib.SMTP(smtp_host, port, timeout=10)

            with server_cm as server:
                server.ehlo()
                if not use_ssl:
                    stage = "starttls"
                    server.starttls()
                    server.ehlo()
                stage = "login"
                server.login(smtp_user, smtp_pass)
                stage = "send"
                server.send_message(msg)
            return True, "", False
        except smtplib.SMTPAuthenticationError:
            return (
                False,
                "Mật khẩu ứng dụng Gmail không đúng hoặc đã bị Google thu hồi (535) — vui lòng tạo mã 16 ký tự mới ở Admin → Hộp thư Email",
                True,
            )
        except smtplib.SMTPServerDisconnected as exc:
            if stage == "login":
                # Gmail đóng socket ngay sau khi từ chối AUTH PLAIN (535) và client gửi tiếp AUTH LOGIN
                return (
                    False,
                    "Mật khẩu ứng dụng Gmail không đúng hoặc đã bị Google thu hồi (535) — vui lòng tạo mã 16 ký tự mới ở Admin → Hộp thư Email",
                    True,
                )
            last_err = str(exc)
            continue
        except Exception as exc:
            last_err = str(exc)
            if stage == "login":
                break
            continue

    return False, f"Lỗi SMTP ({last_err})", False


def send_and_log_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    allow_relay: bool = True,
    relay_fields: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Gửi email thật tới hộp thư (qua Google SMTP hoặc FormSubmit Relay đã kích hoạt) và lưu lịch sử vào bảng `email_logs`."""
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
    smtp_sent = False
    smtp_err = ""

    if smtp_user and smtp_pass and "@petshop.local" not in recipient_addr and "@example.com" not in recipient_addr:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"Meow & Woof Pet House <{smtp_user}>"
        msg["To"] = recipient_addr
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        smtp_sent, smtp_err, _ = _send_via_smtp(smtp_host, smtp_port, smtp_user, smtp_pass, msg)
        if smtp_sent:
            status = f"Đã gửi Gmail SMTP thành công tới {recipient_addr}"
        else:
            status = f"{smtp_err} — Đã lưu bản sao tại Hộp thư Admin"

    if not smtp_sent and is_real_email and not allow_relay:
        if not smtp_pass:
            status = (
                f"Chưa gửi tới {recipient_addr}: chưa có Mật khẩu ứng dụng Gmail hợp lệ — "
                f"vào Admin → Hộp thư Email dán App Password 16 ký tự mới (và cập nhật SMTP_PASS trên Vercel)"
            )
    elif not smtp_sent and is_real_email and allow_relay:
        # Dự phòng gửi thông báo Admin qua FormSubmit AJAX dùng token đã kích hoạt + bảng table gọn đẹp
        relay_target = get_formsubmit_token_for_email(recipient_addr) or recipient_addr
        try:
            relay_url = f"https://formsubmit.co/ajax/{relay_target}"
            relay_payload: Dict[str, Any] = {
                "_subject": subject,
                "_template": "table",
                "_captcha": "false",
            }
            if relay_fields:
                relay_payload.update(relay_fields)
            else:
                relay_payload["Cửa hàng"] = "Meow & Woof Pet House & Spa"
                relay_payload["Nội dung chi tiết"] = body

            payload_bytes = json.dumps(relay_payload, ensure_ascii=False).encode("utf-8")
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
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp_json = json.loads(resp.read().decode("utf-8", errors="ignore"))
                msg_info = str(resp_json.get("message", ""))
                if resp_json.get("success") in (True, "true"):
                    status = f"Đã gửi thẳng tới Gmail {recipient_addr} (FormSubmit Relay)"
                elif "activate" in msg_info.lower() or "confirm" in msg_info.lower():
                    status = (
                        f"Chờ bấm nút 'ACTIVATE FORM' trong Gmail {recipient_addr} "
                        f"(hoặc dán App Password Gmail 16 ký tự ở tab Hộp thư Email)"
                    )
                else:
                    status = f"Đã gửi thông báo tới {recipient_addr}"
        except Exception:
            if smtp_err:
                status = f"{smtp_err} — Đã lưu bản sao tại Hộp thư Admin"
            else:
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
    pm_raw = str(order_dict.get("payment_method", "cod") or "cod").strip().lower()
    pm_label = "Chuyển khoản VietQR 24/7" if pm_raw in ("banking", "vietqr") else "Thu tiền khi nhận (COD)"

    subject_admin = f"🔔 [ĐƠN HÀNG MỚI #{order_dict.get('id')}] Khách {order_dict.get('customer_name')} ({order_dict.get('phone')}) - {total_fmt}đ"
    body_admin = (
        f"🔔 THÔNG BÁO ĐƠN HÀNG MỚI VỀ EMAIL ADMIN ({admin_email}):\n"
        f"Có đơn hàng mới #{order_dict.get('id')} vừa được đặt thành công trên website Meow & Woof!\n\n"
        f"👤 Khách hàng đặt: {order_dict.get('customer_name')}\n"
        f"📞 Số điện thoại: {order_dict.get('phone')}\n"
        f"✉️ Email khách hàng: {cust_email or 'Không cung cấp'}\n"
        f"🏠 Địa chỉ giao hàng: {order_dict.get('address')}\n"
        f"💳 Thanh toán: {pm_label}\n"
        f"⏰ Thời gian đặt: {order_dict.get('created_at')}\n\n"
        f"Chi tiết sản phẩm đặt mua:\n{items_lines}\n\n"
        f"💰 TỔNG TIỀN THANH TOÁN: {total_fmt} VNĐ\n"
    )
    relay_fields = {
        "Mã đơn hàng": f"#{order_dict.get('id')}",
        "Khách hàng": str(order_dict.get("customer_name", "")),
        "Số điện thoại": str(order_dict.get("phone", "")),
        "Email khách": cust_email or "Không cung cấp",
        "Địa chỉ giao": str(order_dict.get("address", "")),
        "Sản phẩm đặt mua": " | ".join(
            f"{item['name']} (x{item['quantity']}: {item['subtotal']:,.0f}đ)"
            for item in order_dict.get("items", [])
        ),
        "Thanh toán": pm_label,
        "Tổng thanh toán": f"{total_fmt} VNĐ",
        "Thời gian đặt": str(order_dict.get("created_at", "")),
    }
    html_body = build_order_html_email(order_dict)

    return send_and_log_email(
        admin_email,
        subject_admin,
        body_admin,
        html_body=html_body,
        relay_fields=relay_fields,
    )


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
    relay_fields = {
        "Mã lịch hẹn": f"#{booking_dict.get('id')}",
        "Chủ nuôi": f"{booking_dict.get('customer_name')} ({booking_dict.get('phone')})",
        "Email khách": cust_email or "Không cung cấp",
        "Bé cưng": f"{booking_dict.get('pet_name')} ({booking_dict.get('pet_type')} - {booking_dict.get('pet_weight_kg')}kg)",
        "Gói dịch vụ": str(booking_dict.get("service_name", "")),
        "Thời gian hẹn": f"{booking_dict.get('appointment_date')} lúc {booking_dict.get('appointment_time')}",
        "Chi phí tạm tính": f"{total_fmt} VNĐ",
    }
    html_body = build_booking_html_email(booking_dict)

    return send_and_log_email(
        admin_email,
        subject_admin,
        body_admin,
        html_body=html_body,
        relay_fields=relay_fields,
    )
