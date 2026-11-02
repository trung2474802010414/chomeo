"""
forms/customer_forms.py
Các biểu mẫu dành cho khách hàng & quản trị:
- SpaBookingForm: Đặt lịch Spa thú cưng.
- CheckoutForm: Thanh toán & địa chỉ giao hàng.
- AdminLoginForm: Đăng nhập quản trị viên.
- NetworkApiForm: Cấu hình gọi API urllib.
"""

from datetime import datetime
import re
from forms.base_form import BaseFlaskForm
from models.booking import SPA_SERVICES


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
    """Form Thanh toán Đơn hàng trên trang `/cart`."""

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

        payment_method = str(self.raw_data.get("payment_method", "cod")).strip()
        note = str(self.raw_data.get("note", "")).strip()

        if len(address) < 6 or len(address) > 250:
            self.add_error("address", "Địa chỉ giao hàng phải từ 6 đến 250 ký tự.")

        self.data = {
            "customer_name": customer_name,
            "phone": phone,
            "email": email,
            "address": address,
            "payment_method": payment_method or "cod",
            "note": note,
        }


class AdminLoginForm(BaseFlaskForm):
    """Form Đăng nhập Quản trị viên (Admin Login)."""

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

