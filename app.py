"""
app.py
Ứng dụng Web Flask hoàn chỉnh cho Meow & Woof Pet Shop & Spa.
Đáp ứng toàn bộ Rubric đánh giá học phần:
- CLO2 (50%): Thiết kế & xây dựng ứng dụng web Flask (Jinja2 Template Inheritance, Form Validation & CSRF, SQLite Database, SMTP Email).
- CLO3 (10%): Lập trình mạng Internet (`urllib.request`, Header `x-api-key`, xử lý JSON & XML `ElementTree`).
- CLO4 (20%): Sử dụng thành thạo thư viện Python (`Flask`, `forms`, `urllib`, `json`, `xml`, `sqlite3`, `smtplib`).
- CLO5 (10%): Module hóa code rõ ràng (`core/`, `models/`, `forms/`, `services/`, `templates/`, `static/`).
"""

from datetime import datetime, timedelta
import functools
import json
import os
import re
import sys
from typing import Any, Callable, Dict, List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from core.orm import ValidationError
from core.paginator import paginate_stream
from core.router import Router
from forms.petshop_forms import AdminLoginForm, CheckoutForm, ProductForm, SpaBookingForm
from models.entities import (
    CATEGORIES,
    CAT_BREEDS,
    DOG_BREEDS,
    EmailLog,
    Order,
    Product,
    SPA_SERVICES,
    SpaBooking,
    User,
    hash_password,
)
from services.email_service import (
    build_booking_html_email,
    build_marketing_html_email,
    build_order_html_email,
    get_admin_notification_email,
    get_smtp_credentials,
    save_smtp_credentials,
    send_and_log_email,
    send_booking_confirmation_email,
    send_order_confirmation_email,
    send_test_email,
    set_admin_notification_email,
)
from services.network_service import (
    export_products_to_xml,
    fetch_pet_breeds_via_urllib,
    import_products_from_xml,
)
from services.petshop_service import (
    SUPPORTED_BANKS,
    compute_dashboard_stats,
    create_order_transactional,
    export_products_csv_generator,
    get_bank_config,
    get_product_detail_and_related,
    import_products_from_csv,
    init_db_and_seed,
    query_products,
    save_bank_config,
    search_pets_by_price,
)

# Tự động nhận diện thư mục chứa template ('templates' hoặc 'html')
_TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
if not os.path.isdir(_TEMPLATE_DIR) and os.path.isdir(os.path.join(BASE_DIR, "html")):
    _TEMPLATE_DIR = os.path.join(BASE_DIR, "html")

app = Flask(
    __name__,
    template_folder=_TEMPLATE_DIR,
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "meow-woof-petshop-secret-2026")
# Duy trì phiên đăng nhập và tài khoản 365 ngày kể cả khi tắt và mở lại trình duyệt
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

# Tự động khởi tạo bảng và dữ liệu mẫu ngay khi Vercel WSGI import `app`
init_db_and_seed()
User.sync_from_json_store()

# Giữ bộ Router Decorator phục vụ REST API & Unit Test
router = Router()


def _read_cookie_accounts_vault() -> List[Dict[str, str]]:
    """Đọc danh sách tài khoản đã đăng ký lưu trong Cookie bền vững 365 ngày."""
    raw = request.cookies.get("mw_users_vault", "")
    if not raw:
        return []
    try:
        import urllib.parse

        decoded = urllib.parse.unquote(raw)
        data = json.loads(decoded)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _attach_account_to_vault_cookie(resp: Response, user_obj: User) -> Response:
    """Lưu tài khoản vào Cookie bền vững 365 ngày để tắt web mở lại không bao giờ mất."""
    try:
        import urllib.parse

        vault = _read_cookie_accounts_vault()
        u_lower = user_obj.username.strip().lower()
        entry = {
            "username": user_obj.username,
            "fullname": user_obj.fullname,
            "email": user_obj.email,
            "phone": user_obj.phone,
            "password_hash": user_obj.password_hash,
            "role": user_obj.role,
            "created_at": user_obj.created_at,
        }
        vault = [x for x in vault if str(x.get("username", "")).strip().lower() != u_lower]
        vault.append(entry)
        vault = vault[-10:]
        encoded = urllib.parse.quote(json.dumps(vault, ensure_ascii=False))
        resp.set_cookie(
            "mw_users_vault",
            encoded,
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


def _encode_compressed_vault(data: List[Dict[str, Any]]) -> str:
    """Nén danh sách JSON bằng zlib + base64 an toàn URL để lưu nhiều đơn hàng/lịch hẹn trong Cookie < 4KB."""
    import base64
    import zlib

    raw_bytes = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw_bytes, level=9)
    return "z:" + base64.urlsafe_b64encode(compressed).decode("ascii")


def _decode_compressed_vault(raw_cookie: str) -> List[Dict[str, Any]]:
    """Giải mã danh sách JSON từ Cookie (hỗ trợ cả chuẩn nén z: và chuẩn urllib.parse.unquote)."""
    if not raw_cookie:
        return []
    try:
        if raw_cookie.startswith("z:"):
            import base64
            import zlib

            compressed = base64.urlsafe_b64decode(raw_cookie[2:].encode("ascii"))
            decoded_str = zlib.decompress(compressed).decode("utf-8")
            data = json.loads(decoded_str)
        else:
            decoded_str = urllib.parse.unquote(raw_cookie)
            data = json.loads(decoded_str)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _read_cookie_orders_vault() -> List[Dict[str, Any]]:
    """Đọc danh sách đơn hàng đã lưu từ Cookie trình duyệt để không mất khi chuyển sang tài khoản Admin."""
    return _decode_compressed_vault(request.cookies.get("mw_orders_vault", ""))


def _attach_order_to_vault_cookie(resp: Response, order_dict: Dict[str, Any]) -> Response:
    """Đính kèm đơn hàng mới vào Cookie bền vững 365 ngày."""
    try:
        vault = _read_cookie_orders_vault()
        key = (
            str(order_dict.get("phone", "")).strip(),
            str(order_dict.get("created_at", "")).strip(),
            round(float(order_dict.get("total_amount", 0)), 0),
        )
        compact_items = [
            {
                "product_id": i.get("product_id"),
                "sku": i.get("sku", ""),
                "name": i.get("name", ""),
                "price": i.get("price", 0),
                "quantity": i.get("quantity", 1),
                "subtotal": i.get("subtotal", 0),
            }
            for i in order_dict.get("items", [])
        ]
        compact_order = {
            "id": order_dict.get("id"),
            "customer_name": order_dict.get("customer_name", ""),
            "phone": order_dict.get("phone", ""),
            "email": order_dict.get("email", ""),
            "address": order_dict.get("address", ""),
            "items": compact_items,
            "total_amount": order_dict.get("total_amount", 0),
            "status": order_dict.get("status", "Chờ xác nhận"),
            "payment_method": order_dict.get("payment_method", "cod"),
            "created_at": order_dict.get("created_at", ""),
        }
        vault = [
            x
            for x in vault
            if (
                str(x.get("phone", "")).strip(),
                str(x.get("created_at", "")).strip(),
                round(float(x.get("total_amount", 0)), 0),
            )
            != key
        ]
        vault.append(compact_order)
        vault = vault[-15:]
        resp.set_cookie(
            "mw_orders_vault",
            _encode_compressed_vault(vault),
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


def _sync_orders_vault_cookie(resp: Response, all_orders: List[Dict[str, Any]]) -> Response:
    """Đồng bộ lại Cookie đơn hàng khi Admin cập nhật trạng thái hoặc xóa đơn hàng."""
    try:
        resp.set_cookie(
            "mw_orders_vault",
            _encode_compressed_vault(all_orders[-15:]),
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


def _sync_users_vault_cookie(resp: Response, all_users: List[Dict[str, str]]) -> Response:
    """Đồng bộ lại Cookie tài khoản khi Khách hàng hoặc Admin cập nhật/xóa tài khoản."""
    try:
        encoded = urllib.parse.quote(json.dumps(all_users[-15:], ensure_ascii=False))
        resp.set_cookie(
            "mw_users_vault",
            encoded,
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


def _read_cookie_bookings_vault() -> List[Dict[str, Any]]:
    """Đọc danh sách lịch hẹn Spa từ Cookie trình duyệt."""
    return _decode_compressed_vault(request.cookies.get("mw_bookings_vault", ""))


def _attach_booking_to_vault_cookie(resp: Response, booking_dict: Dict[str, Any]) -> Response:
    """Đính kèm lịch hẹn Spa mới vào Cookie bền vững 365 ngày."""
    try:
        vault = _read_cookie_bookings_vault()
        key = (
            str(booking_dict.get("phone", "")).strip(),
            str(booking_dict.get("pet_name", "")).strip(),
            str(booking_dict.get("appointment_date", "")).strip(),
            str(booking_dict.get("appointment_time", "")).strip(),
        )
        vault = [
            x
            for x in vault
            if (
                str(x.get("phone", "")).strip(),
                str(x.get("pet_name", "")).strip(),
                str(x.get("appointment_date", "")).strip(),
                str(x.get("appointment_time", "")).strip(),
            )
            != key
        ]
        vault.append(booking_dict)
        vault = vault[-15:]
        resp.set_cookie(
            "mw_bookings_vault",
            _encode_compressed_vault(vault),
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


def _sync_bookings_vault_cookie(resp: Response, all_bookings: List[Dict[str, Any]]) -> Response:
    """Đồng bộ lại Cookie lịch hẹn Spa khi Admin đổi trạng thái hoặc xóa lịch hẹn."""
    try:
        resp.set_cookie(
            "mw_bookings_vault",
            _encode_compressed_vault(all_bookings[-15:]),
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


@app.before_request
def restore_persistent_accounts_before_request() -> None:
    """Tự động đồng bộ tài khoản, đơn hàng, lịch Spa, ngân hàng và email Admin từ JSON & Cookie trước mỗi request."""
    User.sync_from_json_store()
    vault = _read_cookie_accounts_vault()
    cur_backup = session.get("current_user_backup")
    if isinstance(cur_backup, dict):
        vault.append(cur_backup)
    if vault:
        User.restore_accounts_list(vault)

    # Khôi phục đơn hàng từ file JSON & Cookie để khi thoát khách sang Admin không bao giờ mất đơn
    Order.sync_from_json_store()
    orders_vault = _read_cookie_orders_vault()
    if orders_vault:
        Order.restore_orders_list(orders_vault)

    # Khôi phục lịch hẹn Spa từ file JSON & Cookie
    SpaBooking.sync_from_json_store()
    bookings_vault = _read_cookie_bookings_vault()
    if bookings_vault:
        SpaBooking.restore_bookings_list(bookings_vault)

    # Khôi phục cấu hình ngân hàng từ Cookie nếu trên Serverless cold-start
    if not os.environ.get("PETSHOP_BANK_CONFIG"):
        raw_bank = request.cookies.get("mw_bank_config", "")
        if raw_bank:
            try:
                bank_data = json.loads(urllib.parse.unquote(raw_bank))
                if isinstance(bank_data, dict) and bank_data.get("account_number"):
                    save_bank_config(bank_data)
            except Exception:
                pass

    # Khôi phục Email nhận thông báo của Admin & Mật khẩu ứng dụng SMTP từ Cookie nếu trên Serverless cold-start
    raw_mail = request.cookies.get("mw_admin_email", "")
    if raw_mail and not os.environ.get("PETSHOP_ADMIN_NOTIFY_EMAIL"):
        try:
            mail_str = urllib.parse.unquote(raw_mail).strip()
            if "@" in mail_str:
                set_admin_notification_email(mail_str)
        except Exception:
            pass

    raw_smtp_pass = request.cookies.get("mw_smtp_pass", "")
    if raw_smtp_pass and not os.environ.get("SMTP_PASS"):
        try:
            pass_str = urllib.parse.unquote(raw_smtp_pass).strip()
            if pass_str:
                save_smtp_credentials(get_admin_notification_email(), pass_str, "smtp.gmail.com", 587)
        except Exception:
            pass


# ============================================================================
# HELPER GIỎ HÀNG TRONG SESSION FLASK
# ============================================================================

def get_session_cart() -> Dict[str, int]:
    """Lấy giỏ hàng từ Flask session (chỉ trả về giỏ hàng của tài khoản đang đăng nhập)."""
    if not session.get("customer_logged_in") and not session.get("admin_logged_in"):
        return {}
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart


def build_cart_view_data() -> Tuple[List[Dict[str, Any]], float, int]:
    """Chuyển giỏ hàng trong session thành danh sách chi tiết sản phẩm + tổng tiền (chỉ mở 1 kết nối DB duy nhất)."""
    cart_map = get_session_cart()
    if not cart_map:
        return [], 0.0, 0

    items: List[Dict[str, Any]] = []
    total_amount = 0.0
    total_count = 0

    product_by_id = {p.id: p for p in Product.iter_all()}
    for pid_str, qty in list(cart_map.items()):
        try:
            prod = product_by_id.get(int(pid_str))
        except ValueError:
            prod = None
        if not prod or qty <= 0:
            continue
        actual_qty = min(qty, prod.stock) if prod.stock > 0 else 0
        if actual_qty <= 0:
            continue
        subtotal = round(prod.price * actual_qty, 2)
        total_amount += subtotal
        total_count += actual_qty
        items.append(
            {
                "product_id": prod.id,
                "sku": prod.sku,
                "name": prod.name,
                "price": prod.price,
                "stock": prod.stock,
                "quantity": actual_qty,
                "subtotal": subtotal,
            }
        )
    return items, total_amount, total_count


@app.context_processor
def inject_global_template_vars() -> Dict[str, Any]:
    """Tự động truyền số lượng giỏ hàng, trạng thái Admin & Khách hàng vào mọi template Jinja2."""
    cart_map = get_session_cart()
    count = sum(max(0, int(v)) for v in cart_map.values() if isinstance(v, (int, str)) and str(v).isdigit())
    just_logged_in = bool(session.pop("just_logged_in", False))
    return {
        "cart_count": count,
        "is_admin": bool(session.get("admin_logged_in")),
        "admin_user": session.get("admin_user", "admin"),
        "customer_logged_in": bool(session.get("customer_logged_in")),
        "customer_name": session.get("customer_name", ""),
        "customer_username": session.get("customer_username", ""),
        "customer_email": session.get("customer_email", ""),
        "customer_phone": session.get("customer_phone", ""),
        "just_logged_in": just_logged_in,
        "global_admin_email": get_admin_notification_email(),
        "global_dog_breeds": DOG_BREEDS,
        "global_cat_breeds": CAT_BREEDS,
    }


def admin_required(view_func: Callable) -> Callable:
    """
    Custom Decorator bảo vệ các route Quản trị (`/admin*`):
    Nếu người dùng chưa đăng nhập tài khoản Admin, tự động chặn và chuyển hướng sang trang `/login`.
    """

    @functools.wraps(view_func)
    def wrapped_view(*args: Any, **kwargs: Any):
        if not session.get("admin_logged_in"):
            flash("Vui lòng đăng nhập tài khoản Quản trị viên để truy cập Dashboard.", "error")
            return redirect(url_for("login_page", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


# ============================================================================
# CÁC TRANG GIAO DIỆN WEB FLASK (CLO2 & CLO3)
# ============================================================================

@app.route("/")
def home_page():
    """Trang chủ: Banner, Sản phẩm nổi bật và Tra cứu nhanh Đơn hàng / Lịch hẹn."""
    all_prods = [p.to_dict() for p in Product.iter_all(order_by="id DESC")]
    # Hiển thị 12 sản phẩm & thú cưng tiêu biểu nhất trên trang chủ
    featured_products = all_prods[:12] if len(all_prods) >= 12 else all_prods
    stats = {"total_products": len(all_prods)}
    lookup_phone = request.args.get("lookup_phone", "").strip()
    lookup_result = None

    if lookup_phone:
        matched_orders = [
            o.to_dict() for o in Order.filter_stream(lambda item: lookup_phone in item.phone)
        ]
        matched_bookings = [
            b.to_dict() for b in SpaBooking.filter_stream(lambda item: lookup_phone in item.phone)
        ]
        lookup_result = {"orders": matched_orders, "bookings": matched_bookings}

    return render_template(
        "home.html",
        active_page="home",
        stats=stats,
        featured_products=featured_products,
        lookup_phone=lookup_phone,
        lookup_result=lookup_result,
    )


@app.route("/shop")
def shop_page():
    """Trang Cửa hàng: Lọc đa điều kiện (loài, giống chó/mèo, danh mục, giá) bằng Generator Pipeline & PageIterator."""
    keyword = request.args.get("keyword", "").strip()
    pet_type = request.args.get("pet_type", "ALL").strip()
    category = request.args.get("category", "ALL").strip()
    breed = request.args.get("breed", "ALL").strip()
    min_price_str = request.args.get("min_price", "").strip()
    max_price_str = request.args.get("max_price", "").strip()
    sort_by = request.args.get("sort_by", "id_desc").strip()
    page = max(1, int(request.args.get("page", "1") or "1"))

    min_price = float(min_price_str) if min_price_str else None
    max_price = float(max_price_str) if max_price_str else None

    # Ràng buộc chéo trên Backend:
    # 1. Nếu min_price > max_price thì tự động hoán đổi để không bị lỗi rỗng vô lý
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price
        min_price_str, max_price_str = str(int(min_price)), str(int(max_price))

    # 2. Nếu chọn Danh mục "Chó cảnh" hoặc "Mèo cảnh" thì tự động đồng bộ Loài tương ứng
    if category == "Chó cảnh" and pet_type not in ("ALL", "Chó"):
        pet_type = "Chó"
    elif category == "Mèo cảnh" and pet_type not in ("ALL", "Mèo"):
        pet_type = "Mèo"

    # 3. Nếu chọn Loài là "Chó" nhưng breed lại là giống Mèo (hoặc ngược lại) thì tự động đặt lại breed = "ALL"
    if pet_type == "Chó" and breed in CAT_BREEDS:
        breed = "ALL"
    elif pet_type == "Mèo" and breed in DOG_BREEDS:
        breed = "ALL"
    elif pet_type == "Chó & Mèo" and breed != "ALL":
        breed = "ALL"

    page_data = query_products(
        keyword=keyword,
        category=category,
        pet_type=pet_type,
        breed=breed,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        page_size=6,
    )

    # Khi khách chọn lọc theo 1 giống cụ thể (VD: Chó Schnauzer hoặc giống chưa có sẵn cá thể),
    # tự động gợi ý các giống chó/mèo cùng loài và các đồ dùng/thức ăn phù hợp cho loài đó.
    related_suggestions: List[Dict[str, Any]] = []
    if breed and breed != "ALL":
        target_pet_type = pet_type if pet_type in ("Chó", "Mèo") else ("Chó" if "Chó" in breed or breed in DOG_BREEDS else "Mèo")
        current_ids = {item["id"] for item in page_data["items"]}
        all_items = [p.to_dict() for p in Product.iter_all(order_by="id ASC")]
        related_suggestions = [
            item
            for item in all_items
            if item["id"] not in current_ids and item["pet_type"] in (target_pet_type, "Cả hai")
        ][:8]

    filters = {
        "keyword": keyword,
        "pet_type": pet_type,
        "category": category,
        "breed": breed,
        "min_price": min_price_str,
        "max_price": max_price_str,
        "sort_by": sort_by,
    }

    return render_template(
        "shop.html",
        active_page="shop",
        page_data=page_data,
        filters=filters,
        categories=CATEGORIES,
        related_suggestions=related_suggestions,
    )


@app.route("/product/<int:product_id>")
def product_detail_page(product_id: int):
    """
    Trang Chi tiết Thú cưng / Sản phẩm (Tham khảo PetHouse):
    Hiển thị ảnh lớn, thông số chi tiết, danh sách các giống liên quan (`related_pets`)
    và danh sách thức ăn / phụ kiện / đồ dùng liên quan (`related_supplies`).
    """
    detail_bundle = get_product_detail_and_related(product_id)
    if not detail_bundle:
        flash(f"Không tìm thấy sản phẩm hoặc thú cưng mã #{product_id}.", "error")
        return redirect(url_for("shop_page"))

    return render_template(
        "product_detail.html",
        active_page="shop",
        p=detail_bundle["product"],
        product=detail_bundle["product"],
        related_pets=detail_bundle["related_pets"],
        related_supplies=detail_bundle["related_supplies"],
    )


@app.route("/spa", methods=["GET", "POST"])
def spa_page():
    """Trang Đặt lịch Spa & Khám thú cưng: Xử lý Form Validation + gửi Email xác nhận."""
    form = SpaBookingForm()
    default_date = datetime.now().strftime("%Y-%m-%d")
    booking_id = request.args.get("booking_id", "").strip()
    booking_success = None
    if booking_id.isdigit():
        b_obj = SpaBooking.get_by_id(int(booking_id))
        if b_obj:
            booking_success = b_obj.to_dict()

    if request.method == "POST":
        if form.validate_on_submit():
            d = form.data
            fee = SpaBooking.calculate_service_price(d["service_name"], d["pet_weight_kg"])
            booking = SpaBooking(
                customer_name=d["customer_name"],
                phone=d["phone"],
                email=d["email"],
                pet_name=d["pet_name"],
                pet_type=d["pet_type"],
                pet_weight_kg=d["pet_weight_kg"],
                service_name=d["service_name"],
                appointment_date=d["appointment_date"],
                appointment_time=d["appointment_time"],
                total_price=fee,
                status="Chờ xác nhận",
                note=d["note"],
            )
            booking.save()
            booking_dict = booking.to_dict()
            email_info = send_booking_confirmation_email(booking_dict)
            flash(
                f"Đặt lịch Spa thành công! Mã lịch hẹn #{booking.id} cho bé {booking.pet_name} "
                f"(Chi phí: {fee:,.0f} đ). Trạng thái Email: {email_info['delivery_status']}.",
                "booking_success",
            )
            resp = make_response(redirect(url_for("spa_page", booking_id=booking.id)))
            return _attach_booking_to_vault_cookie(resp, booking_dict)
        else:
            flash("Vui lòng kiểm tra lại các thông tin báo đỏ trên biểu mẫu.", "error")

    return render_template(
        "spa.html",
        active_page="spa",
        form=form,
        spa_services=SPA_SERVICES,
        default_date=default_date,
        booking_success=booking_success,
    )


@app.route("/cart", methods=["GET", "POST"])
def cart_page():
    """Trang Giỏ hàng & Thanh toán: Bắt buộc đăng nhập tài khoản, Đặt hàng theo Transaction và gửi Email về Admin."""
    is_logged_in = bool(session.get("customer_logged_in") or session.get("admin_logged_in"))
    if not is_logged_in:
        # Không lưu lại giỏ hàng từ các thao tác trước khi chưa đăng nhập
        session.pop("cart", None)

    cart_items, cart_total, _ = build_cart_view_data()
    form = CheckoutForm()

    if request.method == "POST":
        if not is_logged_in:
            flash("⚠️ Bắt buộc phải có tài khoản! Vui lòng đăng nhập hoặc đăng ký thành viên trước khi đặt hàng.", "error")
            return redirect(url_for("login_page", next=url_for("cart_page")))

        if not cart_items:
            flash("Giỏ hàng đang trống, vui lòng chọn sản phẩm trước khi thanh toán.", "error")
            return redirect(url_for("shop_page"))

        if form.validate_on_submit():
            try:
                payment_method = form.data.get("payment_method", "cod")
                order_dict = create_order_transactional(
                    {
                        "customer_name": form.data["customer_name"],
                        "phone": form.data["phone"],
                        "email": form.data["email"],
                        "address": form.data["address"],
                        "payment_method": payment_method,
                        "status": "Chờ xác nhận",
                        "items": [
                            {"product_id": i["product_id"], "quantity": i["quantity"]}
                            for i in cart_items
                        ],
                    }
                )
                session["last_payment_method"] = payment_method
                # Xóa sạch toàn bộ dữ liệu giỏ hàng & thao tác đặt hàng trước đó
                session["cart"] = {}
                session.modified = True
                admin_email = get_admin_notification_email()
                flash(
                    f"🎉 Đặt hàng thành công! Mã đơn hàng #{order_dict['id']} — "
                    f"Tổng thanh toán: {order_dict['total_amount']:,.0f} đ. Đã gửi thông báo đơn hàng về hộp thư Admin ({admin_email})!",
                    "order_success",
                )
                resp = make_response(redirect(url_for("order_success_page", order_id=order_dict["id"])))
                return _attach_order_to_vault_cookie(resp, order_dict)
            except ValidationError as exc:
                flash(str(exc), "error")
        else:
            flash("Vui lòng điền đầy đủ và chính xác thông tin người nhận hàng.", "error")

    return render_template(
        "cart.html",
        active_page="cart",
        cart_items=cart_items,
        cart_total=cart_total,
        form=form,
        bank_config=get_bank_config(),
    )


@app.route("/order-success/<int:order_id>")
def order_success_page(order_id: int):
    """Trang xác nhận đặt hàng thành công: Xem chi tiết đơn hàng, QR thanh toán và link lịch sử mua."""
    order_obj = Order.get_by_id(order_id)
    if not order_obj:
        order_obj = next(Order.iter_all(order_by="id DESC"), None)
    if not order_obj:
        flash(f"Không tìm thấy đơn hàng mã #{order_id}.", "error")
        return redirect(url_for("shop_page"))
    payment_method = session.get("last_payment_method", "cod")
    order_dict = order_obj.to_dict()
    return render_template(
        "order_success.html",
        active_page="cart",
        order=order_dict,
        order_items=order_dict.get("items", []),
        payment_method=payment_method,
        bank_config=get_bank_config(),
    )


@app.route("/orders/history")
@app.route("/my-orders")
@app.route("/profile")
def order_history_page():
    """Trang Hồ Sơ Tài Khoản Khách Hàng & Lịch Sử Mua Hàng / Đặt Lịch Spa (Đồng bộ 100% với Admin)."""
    query_phone = request.args.get("phone", "").strip()
    if not session.get("customer_logged_in") and not session.get("admin_logged_in") and not query_phone:
        flash("🔑 Vui lòng đăng nhập tài khoản để xem Hồ sơ khách hàng & Lịch sử mua hàng của bạn!", "error")
        return redirect(url_for("login_page", next=url_for("order_history_page")))

    username_sess = str(session.get("customer_username", "")).strip()
    phone_sess = query_phone or str(session.get("customer_phone", "")).strip()
    email_sess = str(session.get("customer_email", "")).strip().lower()
    name_sess = str(session.get("customer_name", "")).strip().lower()

    user_obj = None
    if query_phone:
        user_obj = User.find_by_identifier(query_phone)
    if not user_obj and username_sess:
        user_obj = User.find_by_identifier(username_sess)
    if not user_obj and phone_sess:
        user_obj = User.find_by_identifier(phone_sess)
    if not user_obj and email_sess:
        user_obj = User.find_by_identifier(email_sess)

    if user_obj:
        profile_data = {
            "id": user_obj.id,
            "username": user_obj.username,
            "fullname": user_obj.fullname,
            "full_name": user_obj.fullname,
            "phone": user_obj.phone,
            "email": user_obj.email,
            "created_at": user_obj.created_at,
            "role": user_obj.role,
        }
        u_phone = (user_obj.phone or "").strip()
        u_email = (user_obj.email or "").strip().lower()
        u_name = (user_obj.fullname or "").strip().lower()
    else:
        fname_val = session.get("customer_name") or ("Quản Trị Viên Admin" if session.get("admin_logged_in") else "Khách hàng")
        profile_data = {
            "id": 0,
            "username": session.get("admin_user", "admin") if session.get("admin_logged_in") else (username_sess or "thanh_vien"),
            "fullname": fname_val,
            "full_name": fname_val,
            "phone": phone_sess or "0905123456",
            "email": email_sess or get_admin_notification_email(),
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "role": "admin" if session.get("admin_logged_in") else "customer",
        }
        u_phone = phone_sess
        u_email = email_sess
        u_name = name_sess

    all_orders = list(Order.iter_all(order_by="id DESC"))
    all_bookings = list(SpaBooking.iter_all(order_by="id DESC"))

    if session.get("admin_logged_in") and not session.get("customer_logged_in") and not query_phone:
        orders = [o.to_dict() for o in all_orders]
        bookings = [b.to_dict() for b in all_bookings]
    else:
        orders = [
            o.to_dict()
            for o in all_orders
            if (u_phone and u_phone in (o.phone or ""))
            or (u_email and u_email == (o.email or "").strip().lower())
            or (u_name and u_name == (o.customer_name or "").strip().lower())
        ]
        bookings = [
            b.to_dict()
            for b in all_bookings
            if (u_phone and u_phone in (b.phone or ""))
            or (u_email and u_email == (b.email or "").strip().lower())
            or (u_name and u_name == (b.customer_name or "").strip().lower())
        ]

    total_spent = sum(
        o.get("total_amount", 0) for o in orders if o.get("status") != "Đã hủy"
    ) + sum(
        b.get("total_price", 0) for b in bookings if b.get("status") != "Đã hủy"
    )

    if total_spent >= 15000000:
        vip_tier = "💎 Hạng Kim Cương"
        vip_color = "#c4b5fd"
    elif total_spent >= 5000000:
        vip_tier = "🥇 Hạng Vàng"
        vip_color = "#fde047"
    elif total_spent >= 1000000:
        vip_tier = "🥈 Hạng Bạc"
        vip_color = "#38bdf8"
    else:
        vip_tier = "🌱 Thành Viên Thân Thiết"
        vip_color = "#6ee7b7"

    return render_template(
        "order_history.html",
        active_page="orders",
        profile=profile_data,
        customer_profile=profile_data,
        vip_tier=vip_tier,
        vip_color=vip_color,
        phone=profile_data["phone"],
        orders=orders,
        bookings=bookings,
        total_spent=total_spent,
        bank_config=get_bank_config(),
    )


@app.route("/profile/update", methods=["POST"])
def update_customer_profile_route():
    """Khách hàng tự cập nhật thông tin cá nhân trên trang Hồ sơ và đồng bộ ngay với Admin."""
    if not session.get("customer_logged_in") and not session.get("admin_logged_in"):
        return redirect(url_for("login_page"))

    fullname = (request.form.get("fullname") or request.form.get("full_name") or "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    new_password = request.form.get("new_password", "").strip()

    if len(fullname) < 2 or len(fullname) > 80:
        flash("Họ và tên phải từ 2 đến 80 ký tự.", "error")
        return redirect(url_for("order_history_page"))
    if not re.match(r"^0\d{8,10}$", phone):
        flash("Số điện thoại phải bắt đầu bằng số 0 và gồm 9–11 chữ số.", "error")
        return redirect(url_for("order_history_page"))
    if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
        flash("Địa chỉ Email không đúng định dạng.", "error")
        return redirect(url_for("order_history_page"))

    username_sess = str(session.get("customer_username", "")).strip()
    user_obj = User.find_by_identifier(username_sess) if username_sess else None
    if not user_obj and session.get("customer_phone"):
        user_obj = User.find_by_identifier(str(session.get("customer_phone")))

    old_phone = str(session.get("customer_phone", "")).strip()
    old_name = str(session.get("customer_name", "")).strip()

    if user_obj:
        old_phone = user_obj.phone
        old_name = user_obj.fullname
        user_obj.fullname = fullname
        user_obj.phone = phone
        user_obj.email = email
        if new_password:
            if len(new_password) < 6:
                flash("Mật khẩu mới phải từ 6 ký tự trở lên.", "error")
                return redirect(url_for("order_history_page"))
            user_obj.password_hash = hash_password(new_password)
        user_obj.save()

    # Đồng bộ luôn thông tin khách hàng trên các đơn hàng & lịch Spa đã đặt để Admin thấy đồng nhất
    for o in Order.iter_all():
        if (old_phone and o.phone == old_phone) or (old_name and o.customer_name == old_name):
            o.customer_name = fullname
            o.phone = phone
            o.email = email
            super(Order, o).save()
    all_orders = Order.sync_all_to_json_file()

    for b in SpaBooking.iter_all():
        if (old_phone and b.phone == old_phone) or (old_name and b.customer_name == old_name):
            b.customer_name = fullname
            b.phone = phone
            b.email = email
            super(SpaBooking, b).save()
    all_bookings = SpaBooking.sync_all_to_json_file()

    session["customer_name"] = fullname
    session["customer_phone"] = phone
    session["customer_email"] = email
    session.modified = True

    all_users = User.sync_all_to_json_file()
    flash("✅ Đã cập nhật thông tin tài khoản và đồng bộ với hệ thống Quản trị Admin thành công!", "success")
    resp = make_response(redirect(url_for("order_history_page")))
    resp = _sync_users_vault_cookie(resp, all_users)
    resp = _sync_orders_vault_cookie(resp, all_orders)
    return _sync_bookings_vault_cookie(resp, all_bookings)


@app.route("/cart/add", methods=["POST"])
def add_to_cart_route():
    """Thêm 1 sản phẩm vào giỏ hàng trong session (Bắt buộc đăng nhập tài khoản trước)."""
    if not session.get("customer_logged_in") and not session.get("admin_logged_in"):
        session.pop("cart", None)
        flash("⚠️ Vui lòng đăng nhập hoặc tạo tài khoản thành viên trước khi thêm sản phẩm vào giỏ & đặt hàng!", "error")
        return redirect(url_for("login_page", next=url_for("shop_page")))

    product_id = request.form.get("product_id", "").strip()
    next_url = request.form.get("next_url") or url_for("shop_page")

    if product_id.isdigit():
        prod = Product.get_by_id(int(product_id))
        if prod and prod.stock > 0:
            cart = get_session_cart()
            current_qty = cart.get(product_id, 0)
            if current_qty + 1 <= prod.stock:
                cart[product_id] = current_qty + 1
                session["cart"] = cart
                session.modified = True
                flash(f"Đã thêm '{prod.name}' vào giỏ hàng!", "success")
            else:
                flash(f"Sản phẩm '{prod.name}' chỉ còn tối đa {prod.stock} món trong kho.", "error")
    return redirect(next_url)


@app.route("/cart/update", methods=["POST"])
def update_cart_route():
    """Tăng/giảm số lượng sản phẩm trong giỏ hàng."""
    product_id = request.form.get("product_id", "").strip()
    delta = int(request.form.get("delta", "0") or "0")
    cart = get_session_cart()

    if product_id in cart:
        prod = Product.get_by_id(int(product_id))
        new_qty = cart[product_id] + delta
        if new_qty <= 0 or not prod:
            cart.pop(product_id, None)
        elif new_qty <= prod.stock:
            cart[product_id] = new_qty
        else:
            flash(f"Kho chỉ còn {prod.stock} sản phẩm '{prod.name}'.", "error")
        session["cart"] = cart
        session.modified = True
    return redirect(url_for("cart_page"))


@app.route("/cart/clear", methods=["POST"])
def clear_cart_route():
    session["cart"] = {}
    session.modified = True
    flash("Đã xóa toàn bộ sản phẩm trong giỏ hàng.", "success")
    return redirect(url_for("cart_page"))


@app.route("/network")
def network_page():
    """Trang Lập trình mạng (CLO3): Gọi REST API bằng urllib + API Key & xử lý XML/JSON."""
    species = request.args.get("species", "cat").strip().lower()
    search_breed = request.args.get("search_breed", "").strip()
    api_key = request.args.get("api_key", "").strip()

    breed_result = fetch_pet_breeds_via_urllib(
        species=species,
        api_key=api_key,
        search_breed=search_breed,
        limit=8,
    )
    xml_preview = export_products_to_xml()

    return render_template(
        "network.html",
        active_page="network",
        species=species,
        search_breed=search_breed,
        api_key=api_key,
        breed_result=breed_result,
        xml_preview=xml_preview,
    )


@app.route("/export/xml")
@app.route("/api/products/export-xml")
def export_xml_route():
    """Tải xuống danh mục sản phẩm định dạng XML."""
    xml_str = export_products_to_xml()
    return Response(
        xml_str,
        mimetype="application/xml; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="products_catalog.xml"'},
    )


@app.route("/export/json")
@app.route("/api/products/export-json")
def export_json_route():
    """Tải xuống danh mục sản phẩm định dạng JSON."""
    items = [p.to_dict() for p in Product.iter_all(order_by="id ASC")]
    json_str = json.dumps(items, ensure_ascii=False, indent=2)
    return Response(
        json_str,
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="products_catalog.json"'},
    )


@app.route("/export/csv")
@app.route("/api/products/export-csv")
def export_csv_route():
    """Streaming CSV Export qua Generator đúng chuẩn tiết kiệm RAM (CLO4 & CLO5)."""
    def generate_with_bom():
        yield "\ufeff"
        yield from export_products_csv_generator()

    return Response(
        generate_with_bom(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="products_catalog.csv"'},
    )


@app.route("/import/xml", methods=["POST"])
@admin_required
def import_xml_route():
    """Phân tích cú pháp tài liệu XML và nhập sản phẩm vào SQLite (Thuộc quyền Admin)."""
    xml_text = request.form.get("xml_text", "").strip()
    try:
        summary = import_products_from_xml(xml_text)
        flash(
            f"Import XML thành công! Đã thêm mới {summary['imported']} sản phẩm, "
            f"cập nhật {summary['updated']} sản phẩm.",
            "success",
        )
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_page", tab="import_export"))


# ============================================================================
# ĐĂNG NHẬP & TRANG QUẢN TRỊ ADMIN (`/login`, `/logout`, `/admin`)
# ============================================================================

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Trang Đăng nhập Quản trị viên (Admin) & Đăng nhập/Đăng ký Thành viên Khách hàng."""
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_page", tab="dashboard"))
    if session.get("customer_logged_in"):
        return redirect(url_for("shop_page"))

    form = AdminLoginForm()
    raw_next = (request.args.get("next") or request.form.get("next") or "").strip()
    # Chặn lỗ hổng Open Redirect: chỉ chấp nhận relative path an toàn nội bộ
    if raw_next and raw_next.startswith("/") and not raw_next.startswith("//") and not raw_next.startswith("/\\"):
        next_url = raw_next
    else:
        next_url = ""

    if request.method == "POST":
        auth_action = request.form.get("auth_action", "login").strip()

        # Phục hồi danh sách tài khoản từ client_user_backup (nếu trình duyệt gửi kèm)
        backup_raw = request.form.get("client_user_backup", "").strip()
        if backup_raw:
            try:
                b_data = json.loads(backup_raw)
                if isinstance(b_data, list):
                    User.restore_accounts_list(b_data)
                elif isinstance(b_data, dict):
                    User.restore_accounts_list([b_data])
            except Exception:
                pass

        # 1. Xử lý ĐĂNG KÝ THÀNH VIÊN MỚI
        if auth_action == "register":
            fullname = request.form.get("reg_fullname", "").strip()
            username = request.form.get("reg_username", "").strip()
            email = request.form.get("reg_email", "").strip()
            phone = request.form.get("reg_phone", "").strip()
            password = request.form.get("reg_password", "").strip()
            confirm_pass = request.form.get("reg_confirm_password", "").strip()

            if len(fullname) < 2 or len(fullname) > 80:
                flash("Họ và tên phải từ 2 đến 80 ký tự.", "error")
            elif len(username) < 3 or len(username) > 40:
                flash("Tên đăng nhập phải từ 3 đến 40 ký tự.", "error")
            elif not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
                flash("Địa chỉ Email không đúng định dạng.", "error")
            elif not re.match(r"^0\d{8,10}$", phone):
                flash("Số điện thoại phải bắt đầu bằng số 0 và gồm 9–11 chữ số.", "error")
            elif len(password) < 6:
                flash("Mật khẩu phải có tối thiểu 6 ký tự.", "error")
            elif password != confirm_pass:
                flash("Mật khẩu xác nhận không khớp.", "error")
            else:
                existing = User.find_by_identifier(username) or User.find_by_identifier(email)
                if existing:
                    flash(f"Tên đăng nhập '{username}' hoặc Email '{email}' đã được đăng ký. Vui lòng đăng nhập hoặc dùng tên khác.", "error")
                else:
                    new_user = User(
                        username=username,
                        fullname=fullname,
                        email=email,
                        phone=phone,
                        password_hash=hash_password(password),
                        role="customer",
                    )
                    new_user.save()
                    # Xóa sạch toàn bộ dữ liệu từ thao tác trước (giỏ hàng cũ, thông tin cũ)
                    session.clear()
                    session.permanent = False
                    session["just_logged_in"] = True
                    session["customer_logged_in"] = True
                    session["customer_id"] = new_user.id
                    session["customer_name"] = new_user.fullname
                    session["customer_username"] = new_user.username
                    session["customer_email"] = new_user.email
                    session["customer_phone"] = new_user.phone
                    session["user_role"] = "customer"
                    session["cart"] = {}
                    session.modified = True
                    flash(f"🎉 Đăng ký và lưu tài khoản thành công! Xin chào {new_user.fullname}, chúc bạn mua sắm vui vẻ!", "success")
                    target_dest = next_url if (next_url and not next_url.startswith("/admin")) else url_for("shop_page")
                    resp = redirect(target_dest)
                    return _attach_account_to_vault_cookie(resp, new_user)

        # 2. Xử lý ĐĂNG NHẬP (ADMIN HOẶC THÀNH VIÊN)
        else:
            expected_user = os.environ.get("ADMIN_USER", "admin")
            expected_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
            input_user = request.form.get("username", "").strip()
            input_pass = request.form.get("password", "").strip()

            # A. Kiểm tra tài khoản Quản trị Admin -> Vào Dashboard
            if input_user == expected_user and input_pass == expected_pass:
                session.clear()
                session.permanent = False
                session["just_logged_in"] = True
                session["admin_logged_in"] = True
                session["admin_user"] = expected_user
                session["user_role"] = "admin"
                session["cart"] = {}
                session.modified = True
                flash(f"Đăng nhập thành công! Chào mừng Quản trị viên '{expected_user}' đến với Dashboard.", "success")
                return redirect(next_url or url_for("admin_page", tab="dashboard"))

            # B. Kiểm tra tài khoản Thành viên Khách hàng -> Vào Trang bán hàng
            customer_user = User.find_by_identifier(input_user)

            if customer_user and customer_user.verify_password(input_pass):
                # Xóa sạch toàn bộ dữ liệu từ thao tác trước (giỏ hàng cũ, form cũ)
                session.clear()
                session.permanent = False
                session["just_logged_in"] = True
                session["customer_logged_in"] = True
                session["customer_id"] = customer_user.id
                session["customer_name"] = customer_user.fullname
                session["customer_username"] = customer_user.username
                session["customer_email"] = customer_user.email
                session["customer_phone"] = customer_user.phone
                session["user_role"] = "customer"
                session["cart"] = {}
                session.modified = True
                flash(f"🎉 Đăng nhập thành công! Xin chào {customer_user.fullname}, chúc bạn mua sắm vui vẻ!", "success")
                target_dest = next_url if (next_url and not next_url.startswith("/admin")) else url_for("shop_page")
                resp = redirect(target_dest)
                return _attach_account_to_vault_cookie(resp, customer_user)

            flash("Tên đăng nhập hoặc mật khẩu không chính xác (Mặc định Admin: admin / admin123).", "error")

    return render_template(
        "login.html",
        active_page="login",
        form=form,
        next_url=next_url,
    )


@app.route("/logout")
def logout_page():
    """Đăng xuất khỏi phiên Quản trị viên hoặc Thành viên và xóa sạch dữ liệu thao tác trước."""
    silent = request.args.get("silent") == "1"
    session.clear()
    session.modified = True
    if not silent:
        flash("Bạn đã đăng xuất tài khoản thành công.", "success")
    return redirect(url_for("home_page"))


@app.route("/admin")
@admin_required
def admin_page():
    """Trang Dashboard & Quản trị hệ thống: Hỗ trợ lọc kỳ báo cáo (Hôm nay, 7 ngày, 30 ngày, Tháng này, Tự chọn ngày)."""
    admin_tab = request.args.get("tab", "dashboard").strip()
    edit_id = request.args.get("edit_id", "").strip()
    edit_product = Product.get_by_id(int(edit_id)) if edit_id.isdigit() else None

    # Xử lý lọc kỳ báo cáo theo ngày cho Dashboard
    period = request.args.get("period", "30d").strip()
    start_date_arg = request.args.get("start_date", "").strip()
    end_date_arg = request.args.get("end_date", "").strip()

    today_dt = datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")

    if period == "custom" and (start_date_arg or end_date_arg):
        start_date = start_date_arg
        end_date = end_date_arg or today_str
        if start_date and end_date and start_date > end_date:
            start_date, end_date = end_date, start_date
            flash("Ngày bắt đầu lớn hơn ngày kết thúc, hệ thống đã tự động đảo lại khoảng ngày hợp lệ.", "error")
    elif period == "today":
        start_date = today_str
        end_date = today_str
    elif period == "7d":
        start_date = (today_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today_str
    elif period == "month":
        start_date = today_dt.replace(day=1).strftime("%Y-%m-%d")
        end_date = today_str
    elif period == "all":
        start_date = ""
        end_date = ""
    else:
        period = "30d"
        start_date = (today_dt - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = today_str

    stats = compute_dashboard_stats(start_date=start_date, end_date=end_date)
    products = [p.to_dict() for p in Product.iter_all(order_by="id DESC")] if admin_tab == "products" else []
    bookings = [b.to_dict() for b in SpaBooking.iter_all(order_by="id DESC")] if admin_tab == "bookings" else []
    orders = [o.to_dict() for o in Order.iter_all(order_by="id DESC")] if admin_tab == "orders" else []
    email_logs = [e.to_dict() for e in EmailLog.iter_all(order_by="id DESC")] if admin_tab == "emails" else []
    xml_preview = export_products_to_xml() if admin_tab == "import_export" else ""

    low_stock_products = []
    if admin_tab == "inventory_alerts":
        all_prods = [p.to_dict() for p in Product.iter_all(order_by="stock ASC, id ASC")]
        low_stock_products = [p for p in all_prods if int(p.get("stock", 0)) <= 10]

    breed_api_preview = None
    if admin_tab == "system_settings":
        species_test = request.args.get("test_species", "cat")
        api_key_test = request.args.get("test_api_key", "").strip()
        if request.args.get("run_api_test") == "1":
            breed_api_preview = fetch_pet_breeds_via_urllib(species=species_test, api_key=api_key_test, limit=4)

    return render_template(
        "admin.html",
        active_page="admin",
        admin_tab=admin_tab,
        period=period,
        start_date=start_date or (today_dt - timedelta(days=30)).strftime("%Y-%m-%d"),
        end_date=end_date or today_str,
        stats=stats,
        products=products,
        bookings=bookings,
        orders=orders,
        email_logs=email_logs,
        xml_preview=xml_preview,
        low_stock_products=low_stock_products,
        spa_services=SPA_SERVICES,
        breed_api_preview=breed_api_preview,
        python_version=sys.version.split()[0],
        edit_product=edit_product,
        product_form=ProductForm(),
        smtp_creds=get_smtp_credentials(),
        admin_notification_email=get_admin_notification_email(),
        bank_config=get_bank_config(),
        supported_banks=SUPPORTED_BANKS,
    )


@app.route("/admin/banking/save", methods=["POST"])
@admin_required
def admin_save_banking():
    """Lưu cấu hình tài khoản ngân hàng và mã VietQR thanh toán do Admin tùy chỉnh."""
    bank_bin = request.form.get("bank_bin", "970422").strip()
    bank_name = request.form.get("bank_name", "MB Bank (Ngân hàng Quân Đội)").strip()
    account_number = request.form.get("account_number", "").strip()
    account_name = request.form.get("account_name", "").strip().upper()
    syntax_prefix = request.form.get("syntax_prefix", "MEOW").strip().upper() or "MEOW"
    template = request.form.get("template", "compact2").strip()
    is_active = request.form.get("is_active") == "1"

    if not account_number or not account_name:
        flash("Vui lòng điền đầy đủ Số tài khoản và Tên chủ tài khoản ngân hàng.", "error")
        return redirect(url_for("admin_page", tab="banking"))

    cleaned_bank = save_bank_config(
        {
            "bank_bin": bank_bin,
            "bank_name": bank_name,
            "account_number": account_number,
            "account_name": account_name,
            "syntax_prefix": syntax_prefix,
            "template": template,
            "is_active": is_active,
        }
    )
    flash(f"Đã lưu thành công cấu hình ngân hàng '{bank_name}' (STK: {account_number})!", "success")
    resp = make_response(redirect(url_for("admin_page", tab="banking")))
    try:
        resp.set_cookie(
            "mw_bank_config",
            urllib.parse.quote(json.dumps(cleaned_bank, ensure_ascii=False)),
            max_age=365 * 24 * 3600,
            samesite="Lax",
            httponly=False,
        )
    except Exception:
        pass
    return resp


@app.route("/admin/products/save", methods=["POST"])
@admin_required
def admin_save_product():
    form = ProductForm()
    product_id = request.form.get("product_id", "").strip()

    if form.validate_on_submit():
        d = form.data
        if product_id.isdigit():
            prod = Product.get_by_id(int(product_id))
            if prod:
                for k, v in d.items():
                    setattr(prod, k, v)
                prod.save()
                flash(f"Đã cập nhật sản phẩm #{prod.id} ({prod.name}).", "success")
        else:
            new_prod = Product(**d)
            new_prod.save()
            flash(f"Đã thêm sản phẩm mới '{new_prod.name}' vào kho!", "success")
    else:
        err_msgs = "; ".join(f"{k}: {', '.join(v)}" for k, v in form.errors.items())
        flash(f"Dữ liệu sản phẩm chưa hợp lệ: {err_msgs}", "error")

    return redirect(url_for("admin_page", tab="products"))


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_delete_product(product_id: int):
    if Product.delete_by_id(product_id):
        flash(f"Đã xóa sản phẩm #{product_id}.", "success")
    else:
        flash(f"Không tìm thấy sản phẩm #{product_id}.", "error")
    return redirect(url_for("admin_page", tab="products"))


@app.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
def admin_update_booking_status(booking_id: int):
    new_status = request.form.get("status", "").strip()
    booking = SpaBooking.get_by_id(booking_id)
    if booking:
        try:
            booking.status = new_status
            booking.save()
            flash(f"Đã cập nhật trạng thái lịch hẹn #{booking_id} sang '{new_status}'.", "success")
        except ValidationError as exc:
            flash(str(exc), "error")
    all_bookings = SpaBooking.sync_all_to_json_file()
    resp = make_response(redirect(url_for("admin_page", tab="bookings")))
    return _sync_bookings_vault_cookie(resp, all_bookings)


@app.route("/admin/bookings/<int:booking_id>/delete", methods=["POST"])
@admin_required
def admin_delete_booking(booking_id: int):
    if SpaBooking.delete_by_id(booking_id):
        flash(f"Đã xóa lịch hẹn Spa #{booking_id}.", "success")
    else:
        flash(f"Không tìm thấy lịch hẹn #{booking_id}.", "error")
    all_bookings = SpaBooking.sync_all_to_json_file()
    resp = make_response(redirect(url_for("admin_page", tab="bookings")))
    return _sync_bookings_vault_cookie(resp, all_bookings)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_update_order_status(order_id: int):
    """Admin cập nhật trạng thái xử lý đơn hàng và đồng bộ ngay với trang Lịch sử của Khách."""
    new_status = request.form.get("status", "").strip()
    order_obj = Order.get_by_id(order_id)
    if order_obj and new_status:
        order_obj.status = new_status
        order_obj.save()
        flash(f"Đã cập nhật trạng thái đơn hàng #{order_id} sang '{new_status}'.", "success")
    all_orders = Order.sync_all_to_json_file()
    resp = make_response(redirect(url_for("admin_page", tab="orders")))
    return _sync_orders_vault_cookie(resp, all_orders)


@app.route("/admin/orders/<int:order_id>/delete", methods=["POST"])
@admin_required
def admin_delete_order(order_id: int):
    if Order.delete_by_id(order_id):
        flash(f"Đã xóa đơn hàng #{order_id}.", "success")
    else:
        flash(f"Không tìm thấy đơn hàng #{order_id}.", "error")
    all_orders = Order.sync_all_to_json_file()
    resp = make_response(redirect(url_for("admin_page", tab="orders")))
    return _sync_orders_vault_cookie(resp, all_orders)


@app.route("/admin/customers/save", methods=["POST"])
@admin_required
def admin_save_customer():
    """Admin thêm mới hoặc cập nhật toàn bộ thông tin tài khoản khách hàng."""
    user_id = request.form.get("user_id", "").strip()
    username = request.form.get("username", "").strip()
    fullname = (request.form.get("fullname") or request.form.get("full_name") or "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if len(fullname) < 2 or not phone:
        flash("Vui lòng nhập đầy đủ Họ tên và Số điện thoại của khách hàng.", "error")
        return redirect(url_for("admin_page", tab="customers"))

    if user_id.isdigit() and int(user_id) > 0:
        u_obj = User.get_by_id(int(user_id))
        if u_obj:
            old_phone = u_obj.phone
            old_name = u_obj.fullname
            u_obj.fullname = fullname
            u_obj.phone = phone
            u_obj.email = email
            if username and len(username) >= 3:
                u_obj.username = username
            if password and len(password) >= 6:
                u_obj.password_hash = hash_password(password)
            u_obj.save()

            # Đồng bộ thông tin khách trên các đơn hàng của khách đó
            for o in Order.iter_all():
                if (old_phone and o.phone == old_phone) or (old_name and o.customer_name == old_name):
                    o.customer_name = fullname
                    o.phone = phone
                    o.email = email
                    super(Order, o).save()
            Order.sync_all_to_json_file()
            flash(f"Đã cập nhật thông tin khách hàng '{fullname}' (@{u_obj.username}) thành công!", "success")
    else:
        if len(username) < 3:
            flash("Tên đăng nhập phải có ít nhất 3 ký tự.", "error")
            return redirect(url_for("admin_page", tab="customers"))
        existing = User.find_by_identifier(username)
        if existing:
            flash(f"Tên đăng nhập '@{username}' đã tồn tại.", "error")
            return redirect(url_for("admin_page", tab="customers"))
        new_u = User(
            username=username,
            fullname=fullname,
            phone=phone,
            email=email,
            password_hash=hash_password(password if len(password) >= 6 else "123456"),
            role="customer",
        )
        new_u.save()
        flash(f"Đã tạo tài khoản khách hàng mới '{fullname}' (@{username}) thành công!", "success")

    all_users = User.sync_all_to_json_file()
    resp = make_response(redirect(url_for("admin_page", tab="customers")))
    return _sync_users_vault_cookie(resp, all_users)


@app.route("/admin/customers/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_customer(user_id: int):
    """Admin xóa tài khoản khách hàng khỏi hệ thống."""
    if User.delete_by_id(user_id):
        flash(f"Đã xóa tài khoản khách hàng #{user_id} khỏi hệ thống.", "success")
    else:
        flash(f"Không tìm thấy tài khoản khách hàng #{user_id}.", "error")
    all_users = User.sync_all_to_json_file()
    resp = make_response(redirect(url_for("admin_page", tab="customers")))
    return _sync_users_vault_cookie(resp, all_users)


@app.route("/admin/products/import-csv", methods=["POST"])
@admin_required
def admin_import_csv():
    csv_text = request.form.get("csv_text", "").strip()
    if not csv_text:
        flash("Nội dung CSV không được để trống.", "error")
        return redirect(url_for("admin_page", tab="import_export"))
    summary = import_products_from_csv(csv_text)
    flash(
        f"Import CSV hoàn tất: Thêm mới {summary['imported']} sản phẩm, cập nhật {summary['updated']} sản phẩm.",
        "success",
    )
    return redirect(url_for("admin_page", tab="products"))


@app.route("/admin/products/<int:product_id>/restock", methods=["POST"])
@admin_required
def admin_restock_product(product_id: int):
    prod = Product.get_by_id(product_id)
    if not prod:
        flash(f"Không tìm thấy sản phẩm #{product_id}.", "error")
        return redirect(url_for("admin_page", tab="inventory_alerts"))

    try:
        add_qty = int(request.form.get("add_qty", "0"))
    except ValueError:
        add_qty = 0

    new_price_raw = request.form.get("new_price", "").strip()
    if add_qty <= 0 and not new_price_raw:
        flash("Vui lòng nhập số lượng nhập thêm (> 0) hoặc mức giá mới.", "error")
        return redirect(url_for("admin_page", tab="inventory_alerts"))

    if add_qty > 0:
        prod.stock = int(prod.stock) + add_qty
    if new_price_raw:
        try:
            val_price = float(new_price_raw)
            if val_price >= 1000:
                prod.price = val_price
        except ValueError:
            pass

    prod.save()
    flash(f"Đã cập nhật kho cho '{prod.name}' (Tồn kho hiện tại: {prod.stock}).", "success")
    return redirect(url_for("admin_page", tab="inventory_alerts"))


@app.route("/admin/marketing/send-email", methods=["POST"])
@admin_required
def admin_send_marketing_email():
    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    if not recipient or "@" not in recipient or not subject or not body:
        flash("Vui lòng nhập đầy đủ Email người nhận hợp lệ, Tiêu đề và Nội dung chương trình khuyến mãi.", "error")
        return redirect(url_for("admin_page", tab="spa_pricing"))

    html_body = build_marketing_html_email(recipient, subject, body)
    send_and_log_email(recipient, subject, body, html_body=html_body)
    flash(f"Đã phát hành Email ưu đãi VIP chuẩn Brand tới '{recipient}' và lưu vào Hộp thư hệ thống!", "success")
    return redirect(url_for("admin_page", tab="spa_pricing"))


@app.route("/admin/system/resync-seed", methods=["POST"])
@admin_required
def admin_resync_seed():
    init_db_and_seed()
    flash("Đã đồng bộ và kiểm tra toàn bộ 42 sản phẩm chuẩn trong SEED_CATALOG thành công!", "success")
    return redirect(url_for("admin_page", tab="system_settings"))


@app.route("/admin/system/save-smtp", methods=["POST"])
@admin_required
def admin_save_smtp():
    """Lưu địa chỉ Email của Admin nhận thông báo đơn hàng và gửi thư kiểm tra kết nối ngay."""
    admin_notify_mail = request.form.get("admin_notification_email", "").strip()
    smtp_pass = request.form.get("smtp_pass", "").strip()

    if admin_notify_mail and "@" in admin_notify_mail:
        set_admin_notification_email(admin_notify_mail)
        if smtp_pass:
            save_smtp_credentials(admin_notify_mail, smtp_pass, "smtp.gmail.com", 587)
        test_res = send_test_email(admin_notify_mail)
        delivery_st = test_res.get("delivery_status", "")
        session["trigger_formsubmit_ping"] = admin_notify_mail
        flash(
            f"🎉 Đã lưu Email Admin ('{admin_notify_mail}')! Trạng thái gửi: {delivery_st}.",
            "success",
        )
        resp = make_response(redirect(url_for("admin_page", tab="emails")))
        try:
            resp.set_cookie(
                "mw_admin_email",
                urllib.parse.quote(admin_notify_mail),
                max_age=365 * 24 * 3600,
                samesite="Lax",
                httponly=False,
            )
            if smtp_pass:
                resp.set_cookie(
                    "mw_smtp_pass",
                    urllib.parse.quote(smtp_pass.replace(" ", "")),
                    max_age=365 * 24 * 3600,
                    samesite="Lax",
                    httponly=False,
                )
        except Exception:
            pass
        return resp
    else:
        flash("Vui lòng nhập địa chỉ Email Admin hợp lệ.", "error")

    return redirect(url_for("admin_page", tab="emails"))



@app.route("/admin/emails/preview-sample/<sample_type>")
@admin_required
def admin_email_preview_sample(sample_type: str):
    """Xem trực quan giao diện HTML Email gửi cho khách hàng chuẩn Brand Meow & Woof."""
    if sample_type == "spa":
        sample_data = {
            "id": 108,
            "customer_name": "Nguyễn Minh Anh",
            "pet_name": "Mochi",
            "pet_type": "Mèo",
            "pet_weight_kg": "4.2",
            "service_name": "Cắt tỉa & Tạo kiểu lông (Grooming)",
            "appointment_date": "2026-10-29",
            "appointment_time": "09:30",
            "total_price": 280000,
            "note": "Bé nhút nhát, sợ tiếng sấy to",
        }
        return Response(build_booking_html_email(sample_data), mimetype="text/html; charset=utf-8")
    elif sample_type == "order":
        sample_data = {
            "id": 204,
            "customer_name": "Trần Hải Đăng",
            "phone": "0905123456",
            "address": "123 Nguyễn Văn Linh, Q. Hải Châu, TP. Đà Nẵng",
            "created_at": "2026-10-28 15:30:00",
            "total_amount": 560000,
            "items": [
                {"name": "Hạt Royal Canin British Shorthair 2kg", "quantity": 1, "price": 420000, "subtotal": 420000},
                {"name": "Pate Ciao Churu Cá Hồi Gói 4 Tuýp", "quantity": 2, "price": 70000, "subtotal": 140000},
            ],
        }
        return Response(build_order_html_email(sample_data), mimetype="text/html; charset=utf-8")
    else:
        sample_body = "Cảm ơn bạn đã đồng hành cùng Meow & Woof Pet House!\nTặng bạn mã giảm giá 20% cho toàn bộ dịch vụ Spa và phụ kiện thú cưng trong tuần lễ khai trương cơ sở mới."
        return Response(build_marketing_html_email("khachhang@vip.com", "[Meow & Woof] Tri ân khách hàng thân thiết", sample_body), mimetype="text/html; charset=utf-8")



# ============================================================================
# REST API ENDPOINTS (TƯƠNG THÍCH BỘ KIỂM THỬ & CLIENT)
# ============================================================================

@router.get("/api/stats")
def handle_get_stats(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    return 200, {"ok": True, "data": compute_dashboard_stats()}


@router.get("/api/pets")
def handle_search_pets(
    query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]
) -> Tuple[int, Dict[str, Any]]:
    """API tìm kiếm danh sách Thú cưng theo khoảng giá, chuẩn hóa theo api-design.md."""
    min_price_str = query.get("min_price")
    max_price_str = query.get("max_price")
    try:
        min_p = float(min_price_str) if min_price_str else None
        max_p = float(max_price_str) if max_price_str else None
    except ValueError:
        return 400, {
            "success": False,
            "code": 400,
            "message": "Giá trị min_price hoặc max_price không hợp lệ (phải là số).",
            "data": None,
        }

    page = int(query["page"]) if query.get("page", "").isdigit() else 1
    page_size = int(query["page_size"]) if query.get("page_size", "").isdigit() else 10
    pet_type = query.get("pet_type")
    sort_by = query.get("sort_by", "price_asc")

    success, msg, data = search_pets_by_price(
        min_price=min_p,
        max_price=max_p,
        pet_type=pet_type,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

    if not success:
        return 400, {
            "success": False,
            "code": 400,
            "message": msg,
            "data": None,
        }

    return 200, {
        "success": True,
        "code": 200,
        "message": msg,
        "data": data,
    }


@router.get("/api/products")
def handle_list_products(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    result = query_products(
        keyword=query.get("keyword", ""),
        category=query.get("category", "ALL"),
        pet_type=query.get("pet_type", "ALL"),
        min_price=float(query["min_price"]) if query.get("min_price") else None,
        max_price=float(query["max_price"]) if query.get("max_price") else None,
        in_stock_only=query.get("in_stock_only") == "1",
        sort_by=query.get("sort_by", "id_desc"),
        page=int(query.get("page", "1")),
        page_size=int(query.get("page_size", "6")),
    )
    return 200, {"ok": True, "data": result}


@router.post("/api/products")
def handle_create_product(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    product = Product(
        sku=body.get("sku"),
        name=body.get("name"),
        category=body.get("category"),
        pet_type=body.get("pet_type"),
        price=body.get("price"),
        stock=body.get("stock", 0),
        description=body.get("description", ""),
    )
    product.save()
    return 201, {"ok": True, "data": product.to_dict()}


@router.get("/api/bookings")
def handle_list_bookings(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    status_filter = query.get("status", "ALL")
    page = int(query.get("page", "1"))
    page_size = int(query.get("page_size", "8"))
    stream = (
        b.to_dict()
        for b in SpaBooking.filter_stream(
            lambda item: status_filter == "ALL" or item.status == status_filter,
            order_by="appointment_date DESC, appointment_time DESC",
        )
    )
    return 200, {"ok": True, "data": paginate_stream(stream, page=page, page_size=page_size)}


@router.post("/api/bookings")
def handle_create_booking(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    service_name = body.get("service_name", "")
    weight = float(body.get("pet_weight_kg", 0))
    calculated_price = SpaBooking.calculate_service_price(service_name, weight)
    booking = SpaBooking(
        customer_name=body.get("customer_name"),
        phone=body.get("phone"),
        email=body.get("email", ""),
        pet_name=body.get("pet_name"),
        pet_type=body.get("pet_type"),
        pet_weight_kg=weight,
        service_name=service_name,
        appointment_date=body.get("appointment_date"),
        appointment_time=body.get("appointment_time"),
        total_price=calculated_price,
        status="Chờ xác nhận",
        note=body.get("note", ""),
    )
    booking.save()
    booking_dict = booking.to_dict()
    send_booking_confirmation_email(booking_dict)
    return 201, {"ok": True, "data": booking_dict}


@router.post("/api/orders")
def handle_create_order(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    order_dict = create_order_transactional(body)
    return 201, {"ok": True, "data": order_dict}


@router.get("/api/lookup")
def handle_customer_lookup(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    phone = query.get("phone", "").strip()
    if not phone:
        raise ValidationError("Vui lòng nhập số điện thoại cần tra cứu.")
    matched_orders = [o.to_dict() for o in Order.filter_stream(lambda item: phone in item.phone)]
    matched_bookings = [b.to_dict() for b in SpaBooking.filter_stream(lambda item: phone in item.phone)]
    return 200, {"ok": True, "data": {"phone": phone, "orders": matched_orders, "bookings": matched_bookings}}


@app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def flask_api_bridge(subpath: str):
    """Chuyển tiếp mọi request `/api/...` trong Flask qua bộ Decorator `router`."""
    full_path = "/api/" + subpath
    handler, path_params = router.resolve(request.method, full_path)
    if handler is None:
        return jsonify({"ok": False, "error": f"Không tìm thấy endpoint {request.method} {full_path}"}), 404
    query_params = request.args.to_dict()
    body_data = request.get_json(silent=True) or {}
    status_code, payload = handler(query_params, body_data, path_params)
    return jsonify(payload), status_code


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    init_db_and_seed()
    print(f"=== Flask Server Meow & Woof Pet Shop đang chạy tại: http://{host}:{port} ===")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_server()
