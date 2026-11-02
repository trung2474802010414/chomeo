"""
services/email_templates.py
Mẫu HTML Email chuẩn Brand Meow & Woof Pet House & Spa (Vé Spa, Hóa đơn Đơn hàng, Ưu đãi VIP).
"""

from typing import Any, Dict

FOOTER_HTML = """<div style="border-top:1px solid rgba(255,255,255,0.08); padding-top:16px; margin-top:20px; font-size:12px; color:#94a3b8; text-align:center; line-height:1.6;">
  Meow &amp; Woof Pet House &amp; Spa Chó Mèo • Hotline: 0905.123.456<br>
  ⏰ Mở cửa: 08:00 – 21:00 hàng ngày • Cửa hàng &amp; Spa 5 sao toàn quốc.
</div>"""


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
    <h1 style="margin:0; font-size:22px; font-weight:800; color:#ffffff;">Cảm Ơn Bạn Đã Mua Sắm!</h1>
    <p style="margin:4px 0 0; font-size:13px; color:#dbeafe; font-weight:700;">ĐƠN HÀNG #{o_id} ĐÃ ĐƯỢC XÁC NHẬN THÀNH CÔNG</p>
  </div>
  <div style="background:#15102d; border:1px solid rgba(59,130,246,0.3); border-top:none; border-radius:0 0 24px 24px; padding:24px;">
    <p style="margin:0 0 14px; font-size:14.5px; color:#e2e8f0; line-height:1.5;">Xin chào <strong>{cust}</strong>, đơn hàng #{o_id} của bạn đang được đóng gói cẩn thận!</p>
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
      <a href="https://chomeo.vercel.app/" style="display:inline-block; padding:10px 28px; background:linear-gradient(135deg, #10b981 0%, #3b82f6 100%); color:#ffffff; text-decoration:none; border-radius:99px; font-weight:700; font-size:13.5px;">🛍️ Khám Phá Thêm Sản Phẩm Khác</a>
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
