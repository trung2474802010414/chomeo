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
from models.booking import SPA_SERVICES, SpaBooking
from models.email_log import EmailLog
from models.order import Order
from models.product import CATEGORIES, CAT_BREEDS, DOG_BREEDS, Product
from services.email_service import send_booking_confirmation_email
from services.network_service import (
    export_products_to_xml,
    fetch_pet_breeds_via_urllib,
    import_products_from_xml,
)
from services.petshop_service import (
    compute_dashboard_stats,
    create_order_transactional,
    export_products_csv_generator,
    get_product_detail_and_related,
    import_products_from_csv,
    init_db_and_seed,
    query_products,
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

# Tự động khởi tạo bảng và dữ liệu mẫu ngay khi Vercel WSGI import `app`
init_db_and_seed()

# Giữ bộ Router Decorator phục vụ REST API & Unit Test
router = Router()


# ============================================================================
# HELPER GIỎ HÀNG TRONG SESSION FLASK
# ============================================================================

def get_session_cart() -> Dict[str, int]:
    """Lấy giỏ hàng dạng {product_id_str: quantity} từ Flask session."""
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart


def build_cart_view_data() -> Tuple[List[Dict[str, Any]], float, int]:
    """Chuyển giỏ hàng trong session thành danh sách chi tiết sản phẩm + tổng tiền."""
    cart_map = get_session_cart()
    items: List[Dict[str, Any]] = []
    total_amount = 0.0
    total_count = 0

    for pid_str, qty in list(cart_map.items()):
        try:
            prod = Product.get_by_id(int(pid_str))
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
    """Tự động truyền số lượng món trong giỏ hàng, trạng thái Admin và danh sách Giống chó/mèo vào mọi template Jinja2."""
    _, _, count = build_cart_view_data()
    return {
        "cart_count": count,
        "is_admin": bool(session.get("admin_logged_in")),
        "admin_user": session.get("admin_user", "admin"),
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
    stats = compute_dashboard_stats()
    featured_page = query_products(page=1, page_size=6)
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
        featured_products=featured_page["items"],
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
                "success",
            )
            return redirect(url_for("spa_page"))
        else:
            flash("Vui lòng kiểm tra lại các thông tin báo đỏ trên biểu mẫu.", "error")

    recent_bookings = [b.to_dict() for b in list(SpaBooking.iter_all())[:8]]
    return render_template(
        "spa.html",
        active_page="spa",
        form=form,
        spa_services=SPA_SERVICES,
        default_date=default_date,
        recent_bookings=recent_bookings,
    )


@app.route("/cart", methods=["GET", "POST"])
def cart_page():
    """Trang Giỏ hàng & Thanh toán: Đặt hàng theo Transaction và gửi Email hóa đơn."""
    cart_items, cart_total, _ = build_cart_view_data()
    form = CheckoutForm()

    if request.method == "POST":
        if not cart_items:
            flash("Giỏ hàng đang trống, vui lòng chọn sản phẩm trước khi thanh toán.", "error")
            return redirect(url_for("shop_page"))

        if form.validate_on_submit():
            try:
                order_dict = create_order_transactional(
                    {
                        "customer_name": form.data["customer_name"],
                        "phone": form.data["phone"],
                        "email": form.data["email"],
                        "address": form.data["address"],
                        "items": [
                            {"product_id": i["product_id"], "quantity": i["quantity"]}
                            for i in cart_items
                        ],
                    }
                )
                session["cart"] = {}
                session.modified = True
                flash(
                    f"Đặt hàng thành công! Mã đơn hàng #{order_dict['id']} — "
                    f"Tổng thanh toán: {order_dict['total_amount']:,.0f} đ. Đã gửi Email xác nhận đơn hàng!",
                    "success",
                )
                return redirect(url_for("home_page", lookup_phone=order_dict["phone"]))
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
    )


@app.route("/cart/add", methods=["POST"])
def add_to_cart_route():
    """Thêm 1 sản phẩm vào giỏ hàng trong session."""
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
    """Streaming CSV Export qua Generator."""
    csv_content = "\ufeff" + "".join(export_products_csv_generator())
    return Response(
        csv_content,
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
    """Trang Đăng nhập Quản trị viên (Admin Login)."""
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_page", tab="dashboard"))

    form = AdminLoginForm()
    next_url = request.args.get("next") or request.form.get("next") or url_for("admin_page", tab="dashboard")

    if request.method == "POST":
        if form.validate_on_submit():
            expected_user = os.environ.get("ADMIN_USER", "admin")
            expected_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
            username = form.data["username"]
            password = form.data["password"]

            if username == expected_user and password == expected_pass:
                session["admin_logged_in"] = True
                session["admin_user"] = username
                session.modified = True
                flash(f"Đăng nhập thành công! Chào mừng Quản trị viên '{username}' đến với Dashboard.", "success")
                return redirect(next_url)
            else:
                flash("Tên đăng nhập hoặc mật khẩu không chính xác (Mặc định: admin / admin123).", "error")
        else:
            flash("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.", "error")

    return render_template(
        "login.html",
        active_page="login",
        form=form,
        next_url=next_url,
    )


@app.route("/logout")
def logout_page():
    """Đăng xuất khỏi phiên Quản trị viên."""
    session.pop("admin_logged_in", None)
    session.pop("admin_user", None)
    session.modified = True
    flash("Đã đăng xuất khỏi tài khoản Quản trị viên.", "success")
    return redirect(url_for("login_page"))


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
    products = [p.to_dict() for p in Product.iter_all(order_by="id DESC")]
    bookings = [b.to_dict() for b in SpaBooking.iter_all(order_by="id DESC")]
    orders = [o.to_dict() for o in Order.iter_all(order_by="id DESC")]
    email_logs = [e.to_dict() for e in EmailLog.iter_all(order_by="id DESC")]
    xml_preview = export_products_to_xml() if admin_tab == "import_export" else ""

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
        edit_product=edit_product,
        product_form=ProductForm(),
    )


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
    return redirect(url_for("admin_page", tab="bookings"))


@app.route("/admin/bookings/<int:booking_id>/delete", methods=["POST"])
@admin_required
def admin_delete_booking(booking_id: int):
    if SpaBooking.delete_by_id(booking_id):
        flash(f"Đã xóa lịch hẹn Spa #{booking_id}.", "success")
    else:
        flash(f"Không tìm thấy lịch hẹn #{booking_id}.", "error")
    return redirect(url_for("admin_page", tab="bookings"))


@app.route("/admin/orders/<int:order_id>/delete", methods=["POST"])
@admin_required
def admin_delete_order(order_id: int):
    if Order.delete_by_id(order_id):
        flash(f"Đã xóa đơn hàng #{order_id}.", "success")
    else:
        flash(f"Không tìm thấy đơn hàng #{order_id}.", "error")
    return redirect(url_for("admin_page", tab="orders"))


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


# ============================================================================
# REST API ENDPOINTS (TƯƠNG THÍCH BỘ KIỂM THỬ & CLIENT)
# ============================================================================

@router.get("/api/stats")
def handle_get_stats(query: Dict[str, str], body: Dict[str, Any], params: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    return 200, {"ok": True, "data": compute_dashboard_stats()}


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
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()
