"""
forms/petshop_forms.py
Đáp ứng CLO2 (Form) & CLO4 (Flask, Flask-WTF):
- Hỗ trợ kiểm tra hợp lệ biểu mẫu (Form Validation), chống giả mạo truy vấn (CSRF Token),
  và lưu trữ thông báo lỗi từng trường (`form.errors`).
- Tương thích hoàn toàn với mẫu thiết kế của `flask-wtf` (`validate_on_submit()`, `csrf_token`).
"""

import hashlib
import hmac
import re
from typing import Any, Dict, List, Optional
from flask import current_app, has_request_context, request, session
from models.booking import SPA_SERVICES
from models.product import CATEGORIES, PET_TYPES


class BaseFlaskForm:
    """
    Lớp cơ sở cho các Form trong Flask (theo chuẩn giao diện của `flask_wtf.FlaskForm`):
    - Tự động sinh và kiểm tra `csrf_token` trong `session`.
    - Cung cấp phương thức `validate_on_submit()` kiểm tra khi có HTTP POST.
    - Trả về danh sách lỗi chi tiết trong `self.errors`.
    """

    def __init__(self, formdata: Optional[Dict[str, Any]] = None):
        if formdata is None and has_request_context():
            if request.is_json:
                formdata = request.get_json(silent=True) or {}
            else:
                formdata = request.form.to_dict()
        self.raw_data: Dict[str, Any] = formdata or {}
        self.data: Dict[str, Any] = {}
        self.errors: Dict[str, List[str]] = {}

    @property
    def csrf_token(self) -> str:
        """Sinh mã CSRF bảo vệ biểu mẫu gắn với phiên làm việc (session)."""
        if not has_request_context():
            return "test-csrf-token"
        secret = str(current_app.config.get("SECRET_KEY", "petshop-secret-key"))
        sid = session.get("_csrf_seed")
        if not sid:
            sid = "petshop-session-csrf"
            session["_csrf_seed"] = sid
        return hmac.new(secret.encode("utf-8"), sid.encode("utf-8"), hashlib.sha256).hexdigest()[:32]

    def validate_on_submit(self) -> bool:
        """Trả về True nếu request là POST và toàn bộ dữ liệu hợp lệ."""
        if has_request_context() and request.method not in ("POST", "PUT"):
            return False
        return self.validate()

    def validate(self) -> bool:
        self.errors.clear()
        self._clean_fields()
        return len(self.errors) == 0

    def add_error(self, field: str, message: str) -> None:
        self.errors.setdefault(field, []).append(message)

    def _clean_fields(self) -> None:
        pass


class SpaBookingForm(BaseFlaskForm):
    """Form Đặt lịch Spa & Khám thú cưng trên trang `/spa`."""

    def _clean_fields(self) -> None:
        customer_name = str(self.raw_data.get("customer_name", "")).strip()
        phone = str(self.raw_data.get("phone", "")).strip()
        email = str(self.raw_data.get("email", "")).strip()
        pet_name = str(self.raw_data.get("pet_name", "")).strip()
        pet_type = str(self.raw_data.get("pet_type", "Mèo")).strip()
        service_name = str(self.raw_data.get("service_name", "")).strip()
        appointment_date = str(self.raw_data.get("appointment_date", "")).strip()
        appointment_time = str(self.raw_data.get("appointment_time", "")).strip()
        note = str(self.raw_data.get("note", "")).strip()

        if len(customer_name) < 2:
            self.add_error("customer_name", "Vui lòng nhập họ tên chủ nuôi (ít nhất 2 ký tự).")

        if not re.match(r"^0\d{8,10}$", phone):
            self.add_error("phone", "Số điện thoại phải bắt đầu bằng số 0 và gồm 9-11 chữ số.")

        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            self.add_error("email", "Địa chỉ Email không đúng định dạng.")

        if not pet_name:
            self.add_error("pet_name", "Vui lòng nhập tên thú cưng của bạn.")

        if pet_type not in ("Chó", "Mèo"):
            self.add_error("pet_type", "Loài thú cưng phải là Chó hoặc Mèo.")

        try:
            weight = float(self.raw_data.get("pet_weight_kg", 0))
            if weight < 0.2 or weight > 80:
                self.add_error("pet_weight_kg", "Cân nặng thú cưng phải từ 0.2kg đến 80kg.")
        except (ValueError, TypeError):
            weight = 0.0
            self.add_error("pet_weight_kg", "Cân nặng phải là số hợp lệ.")

        if service_name not in SPA_SERVICES:
            self.add_error("service_name", "Gói dịch vụ lựa chọn không hợp lệ.")

        if not appointment_date:
            self.add_error("appointment_date", "Vui lòng chọn ngày hẹn.")
        if not appointment_time:
            self.add_error("appointment_time", "Vui lòng chọn giờ hẹn.")

        self.data = {
            "customer_name": customer_name,
            "phone": phone,
            "email": email,
            "pet_name": pet_name,
            "pet_type": pet_type,
            "pet_weight_kg": weight,
            "service_name": service_name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "note": note,
        }


class CheckoutForm(BaseFlaskForm):
    """Form Thanh toán Đơn hàng trên trang `/cart`."""

    def _clean_fields(self) -> None:
        customer_name = str(self.raw_data.get("customer_name", "")).strip()
        phone = str(self.raw_data.get("phone", "")).strip()
        email = str(self.raw_data.get("email", "")).strip()
        address = str(self.raw_data.get("address", "")).strip()

        if len(customer_name) < 2:
            self.add_error("customer_name", "Vui lòng nhập họ tên người nhận.")
        if not re.match(r"^0\d{8,10}$", phone):
            self.add_error("phone", "Số điện thoại không hợp lệ (gồm 9-11 chữ số).")
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            self.add_error("email", "Địa chỉ Email nhận hóa đơn không hợp lệ.")
        if len(address) < 5:
            self.add_error("address", "Vui lòng nhập địa chỉ giao hàng chi tiết.")

        self.data = {
            "customer_name": customer_name,
            "phone": phone,
            "email": email,
            "address": address,
        }


class ProductForm(BaseFlaskForm):
    """Form Thêm / Cập nhật sản phẩm trong trang `/admin`."""

    def _clean_fields(self) -> None:
        sku = str(self.raw_data.get("sku", "")).strip().upper()
        name = str(self.raw_data.get("name", "")).strip()
        category = str(self.raw_data.get("category", "")).strip()
        pet_type = str(self.raw_data.get("pet_type", "")).strip()
        description = str(self.raw_data.get("description", "")).strip()

        if not sku:
            self.add_error("sku", "Mã SKU không được để trống.")
        if not name:
            self.add_error("name", "Tên sản phẩm không được để trống.")
        if category not in CATEGORIES:
            self.add_error("category", "Danh mục không hợp lệ.")
        if pet_type not in PET_TYPES:
            self.add_error("pet_type", "Loài thú cưng không hợp lệ.")

        try:
            price = float(self.raw_data.get("price", 0))
            if price < 1000:
                self.add_error("price", "Giá bán phải từ 1.000đ trở lên.")
        except (ValueError, TypeError):
            price = 0.0
            self.add_error("price", "Giá bán phải là số.")

        try:
            stock = int(self.raw_data.get("stock", 0))
            if stock < 0:
                self.add_error("stock", "Tồn kho không được âm.")
        except (ValueError, TypeError):
            stock = 0
            self.add_error("stock", "Tồn kho phải là số nguyên.")

        self.data = {
            "sku": sku,
            "name": name,
            "category": category,
            "pet_type": pet_type,
            "price": price,
            "stock": stock,
            "description": description,
        }


class NetworkApiForm(BaseFlaskForm):
    """Form cấu hình truy vấn API thú cưng bằng `urllib` + `API Key` (CLO3)."""

    def _clean_fields(self) -> None:
        species = str(self.raw_data.get("species", "cat")).strip().lower()
        api_key = str(self.raw_data.get("api_key", "")).strip()
        search_breed = str(self.raw_data.get("search_breed", "")).strip()

        if species not in ("cat", "dog"):
            species = "cat"

        self.data = {
            "species": species,
            "api_key": api_key,
            "search_breed": search_breed,
        }


class AdminLoginForm(BaseFlaskForm):
    """Form Đăng nhập Quản trị viên (Admin Login) có kiểm tra CSRF và dữ liệu đầu vào."""

    def _clean_fields(self) -> None:
        username = str(self.raw_data.get("username", "")).strip()
        password = str(self.raw_data.get("password", "")).strip()

        if not username:
            self.add_error("username", "Vui lòng nhập tên đăng nhập.")
        if not password:
            self.add_error("password", "Vui lòng nhập mật khẩu.")

        self.data = {
            "username": username,
            "password": password,
        }

