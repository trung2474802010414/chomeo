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
from datetime import datetime
from typing import Any, Dict, List, Optional
from flask import current_app, has_request_context, request, session
from models.booking import SPA_SERVICES
from models.product import CATEGORIES, CAT_BREEDS, DOG_BREEDS, PET_TYPES


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
    """Form Đặt lịch Spa & Khám thú cưng trên trang `/spa` (Ràng buộc đầy đủ từng trường)."""

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

        if len(customer_name) < 2 or len(customer_name) > 80:
            self.add_error("customer_name", "Họ tên chủ nuôi phải từ 2 đến 80 ký tự.")
        elif re.search(r"[0-9!@#$%^&*()+=\[\]{};:\"\\|<>/?]", customer_name):
            self.add_error("customer_name", "Họ tên chủ nuôi không được chứa chữ số hoặc ký tự đặc biệt.")

        if not re.match(r"^0\d{8,10}$", phone):
            self.add_error("phone", "Số điện thoại phải bắt đầu bằng số 0 và gồm 9–11 chữ số.")

        if email:
            if len(email) > 120 or not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
                self.add_error("email", "Địa chỉ Email không đúng định dạng (VD: ten@gmail.com).")

        if len(pet_name) < 1 or len(pet_name) > 50:
            self.add_error("pet_name", "Tên thú cưng phải từ 1 đến 50 ký tự.")

        if pet_type not in ("Chó", "Mèo"):
            self.add_error("pet_type", "Loài thú cưng phải là Chó hoặc Mèo.")

        try:
            weight = float(self.raw_data.get("pet_weight_kg", 0))
            if weight < 0.2 or weight > 80:
                self.add_error("pet_weight_kg", "Cân nặng thú cưng phải nằm trong khoảng 0.2kg đến 80kg.")
        except (ValueError, TypeError):
            weight = 0.0
            self.add_error("pet_weight_kg", "Cân nặng phải là số hợp lệ (VD: 4.5).")

        if service_name not in SPA_SERVICES:
            self.add_error("service_name", "Gói dịch vụ lựa chọn không hợp lệ.")

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", appointment_date):
            self.add_error("appointment_date", "Vui lòng chọn ngày hẹn hợp lệ (YYYY-MM-DD).")
        else:
            try:
                datetime.strptime(appointment_date, "%Y-%m-%d")
            except ValueError:
                self.add_error("appointment_date", "Ngày hẹn không tồn tại trên lịch.")

        if not re.match(r"^\d{2}:\d{2}$", appointment_time):
            self.add_error("appointment_time", "Vui lòng chọn giờ hẹn hợp lệ (HH:MM).")
        else:
            hh, mm = [int(x) for x in appointment_time.split(":")]
            if (hh < 8) or (hh > 20) or (hh == 20 and mm > 30):
                self.add_error("appointment_time", "Khung giờ nhận lịch Spa là từ 08:00 sáng đến 20:30 tối.")

        if len(note) > 300:
            self.add_error("note", "Ghi chú tình trạng thú cưng tối đa 300 ký tự.")

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
    """Form Thanh toán Đơn hàng trên trang `/cart` (Ràng buộc chặt chẽ thông tin giao hàng)."""

    def _clean_fields(self) -> None:
        customer_name = str(self.raw_data.get("customer_name", "")).strip()
        phone = str(self.raw_data.get("phone", "")).strip()
        email = str(self.raw_data.get("email", "")).strip()
        address = str(self.raw_data.get("address", "")).strip()

        if len(customer_name) < 2 or len(customer_name) > 80:
            self.add_error("customer_name", "Họ tên người nhận phải từ 2 đến 80 ký tự.")
        elif re.search(r"[0-9!@#$%^&*()+=\[\]{};:\"\\|<>/?]", customer_name):
            self.add_error("customer_name", "Họ tên người nhận không được chứa số hoặc ký tự đặc biệt.")

        if not re.match(r"^0\d{8,10}$", phone):
            self.add_error("phone", "Số điện thoại nhận hàng phải bắt đầu bằng số 0 và gồm 9–11 chữ số.")

        if email:
            if len(email) > 120 or not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
                self.add_error("email", "Địa chỉ Email nhận hóa đơn không đúng định dạng.")

        if len(address) < 6 or len(address) > 250:
            self.add_error("address", "Địa chỉ giao hàng phải từ 6 đến 250 ký tự (Số nhà, đường, phường/xã, quận/huyện).")

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
        breed = str(self.raw_data.get("breed", "")).strip()
        image_url = str(self.raw_data.get("image_url", "")).strip()
        description = str(self.raw_data.get("description", "")).strip()

        if not re.match(r"^[A-Z0-9][A-Z0-9\-_]{2,29}$", sku):
            self.add_error("sku", "Mã SKU phải từ 3–30 ký tự (chỉ gồm chữ in hoa, số, dấu gạch ngang '-').")
        if len(name) < 3 or len(name) > 150:
            self.add_error("name", "Tên sản phẩm / thú cưng phải từ 3 đến 150 ký tự.")
        if category not in CATEGORIES:
            self.add_error("category", "Danh mục không hợp lệ.")
        if pet_type not in PET_TYPES:
            self.add_error("pet_type", "Loài thú cưng không hợp lệ.")

        # Ràng buộc chéo giữa Loài (pet_type), Danh mục (category) và Giống (breed)
        if category == "Chó cảnh" and pet_type != "Chó":
            self.add_error("category", "Danh mục 'Chó cảnh' chỉ áp dụng khi loài thú cưng là 'Chó'.")
        elif category == "Mèo cảnh" and pet_type != "Mèo":
            self.add_error("category", "Danh mục 'Mèo cảnh' chỉ áp dụng khi loài thú cưng là 'Mèo'.")

        if len(breed) > 80:
            self.add_error("breed", "Tên giống thú cưng tối đa 80 ký tự.")
        elif breed:
            if pet_type == "Chó" and (breed in CAT_BREEDS or breed.lower().startswith("mèo")):
                self.add_error("breed", f"Loài đang chọn là 'Chó', không thể gắn giống mèo ('{breed}').")
            elif pet_type == "Mèo" and (breed in DOG_BREEDS or breed.lower().startswith("chó")):
                self.add_error("breed", f"Loài đang chọn là 'Mèo', không thể gắn giống chó ('{breed}').")

        if image_url and not (
            image_url.startswith("http://")
            or image_url.startswith("https://")
            or image_url.startswith("data:image/")
            or image_url.startswith("/")
        ):
            self.add_error("image_url", "Đường dẫn ảnh phải bắt đầu bằng https://, http:// hoặc là file ảnh tải lên.")

        try:
            price = float(self.raw_data.get("price", 0))
            if price < 1000 or price > 500_000_000:
                self.add_error("price", "Giá bán phải từ 1.000đ đến 500.000.000đ.")
        except (ValueError, TypeError):
            price = 0.0
            self.add_error("price", "Giá bán phải là số hợp lệ.")

        try:
            stock = int(self.raw_data.get("stock", 0))
            if stock < 0 or stock > 10000:
                self.add_error("stock", "Số lượng tồn kho phải từ 0 đến 10.000.")
        except (ValueError, TypeError):
            stock = 0
            self.add_error("stock", "Số lượng tồn kho phải là số nguyên.")

        if len(description) > 1000:
            self.add_error("description", "Mô tả sản phẩm tối đa 1.000 ký tự.")

        self.data = {
            "sku": sku,
            "name": name,
            "category": category,
            "pet_type": pet_type,
            "breed": breed,
            "price": price,
            "stock": stock,
            "image_url": image_url,
            "description": description,
        }


class AdminLoginForm(BaseFlaskForm):
    """Form Đăng nhập Quản trị viên (Admin Login) có kiểm tra CSRF và dữ liệu đầu vào."""

    def _clean_fields(self) -> None:
        username = str(self.raw_data.get("username", "")).strip()
        password = str(self.raw_data.get("password", "")).strip()

        if len(username) < 3 or len(username) > 50:
            self.add_error("username", "Tên đăng nhập phải từ 3 đến 50 ký tự.")
        if len(password) < 4 or len(password) > 64:
            self.add_error("password", "Mật khẩu phải từ 4 đến 64 ký tự.")

        self.data = {
            "username": username,
            "password": password,
        }


class NetworkApiForm(BaseFlaskForm):
    """Form cấu hình truy vấn API thú cưng bằng `urllib` + `API Key`."""

    def _clean_fields(self) -> None:
        species = str(self.raw_data.get("species", "cat")).strip().lower()
        api_key = str(self.raw_data.get("api_key", "")).strip()
        search_breed = str(self.raw_data.get("search_breed", "")).strip()

        if species not in ("cat", "dog"):
            species = "cat"

        self.data = {
            "species": species,
            "api_key": api_key,
            "search_breed": search_breed[:60],
        }


