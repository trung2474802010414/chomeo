"""
models/entities.py
Toàn bộ các lớp thực thể (Models) của hệ thống Meow & Woof Pet House & Spa:
- Product: Thú cưng (Chó cảnh, Mèo cảnh) & Sản phẩm (Thức ăn, Phụ kiện, Vệ sinh, Đồ chơi, Y tế)
- SpaBooking: Lịch hẹn Spa & Grooming thú cưng
- Order: Đơn đặt mua hàng của khách
- EmailLog: Nhật ký gửi thông báo Email
- User: Tài khoản thành viên & Quản trị viên (lưu trữ bền vững đa tầng SQLite + JSON Store)
"""

from datetime import datetime
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from core.database import resolve_writable_json_path
from core.orm import BaseModel, FloatField, IntField, StringField

CATEGORIES = [
    "Chó cảnh",
    "Mèo cảnh",
    "Thức ăn",
    "Phụ kiện",
    "Vệ sinh & Chăm sóc",
    "Đồ chơi",
    "Y tế & Vitamin",
]

PET_TYPES = ["Chó", "Mèo", "Chó & Mèo"]

DOG_BREEDS: List[str] = [
    "Chó Phốc Sóc (Pomeranian)",
    "Chó Poodle",
    "Chó Chihuahua",
    "Chó Corgi Chân Lùn",
    "Chó Golden Retriever",
    "Chó Labrador",
    "Chó Alaska",
    "Chó Husky",
    "Chó Akita",
    "Chó Shiba Inu",
    "Chó Samoyed",
    "Chó Chow Chow",
    "Chó Pug Mặt Xệ",
    "Chó Bull Pháp",
    "Chó Schnauzer",
    "Chó Phú Quốc",
    "Chó Becgie Đức",
    "Chó Beagle",
    "Chó Bichon Frise",
    "Chó Lạp Xưởng",
]

CAT_BREEDS: List[str] = [
    "Mèo Anh Lông Ngắn (ALN)",
    "Mèo Anh Lông Dài (ALD)",
    "Mèo Tai Cụp Scottish Fold",
    "Mèo Chân Ngắn Munchkin",
    "Mèo Ba Tư (Persian)",
    "Mèo Ragdoll",
    "Mèo Bengal",
    "Mèo Maine Coon",
    "Mèo Xiêm (Siamese)",
    "Mèo Nga Mắt Xanh",
    "Mèo Sphynx Không Lông",
    "Mèo Mỹ Lông Ngắn",
]

SPA_SERVICES: Dict[str, float] = {
    "Tắm sấy & Vệ sinh tai móng": 150000.0,
    "Cắt tỉa & Tạo kiểu lông (Grooming)": 280000.0,
    "Cạo lông máu / Cạo vệ sinh": 180000.0,
    "Khám sức khỏe & Tư vấn dinh dưỡng": 120000.0,
    "Trông giữ thú cưng (1 ngày)": 200000.0,
}

BOOKING_STATUSES = ["Chờ xác nhận", "Đã xác nhận", "Hoàn thành", "Đã hủy"]
ORDER_STATUSES = ["Chờ xác nhận", "Đang đóng gói", "Đang giao hàng", "Hoàn thành", "Đã hủy"]

USERS_STORE_PATH = resolve_writable_json_path("users_store.json")
ORDERS_STORE_PATH = resolve_writable_json_path("orders_store.json")
BOOKINGS_STORE_PATH = resolve_writable_json_path("bookings_store.json")
VOUCHERS_STORE_PATH = resolve_writable_json_path("vouchers_store.json")


def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng thuật toán an toàn SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class Product(BaseModel):
    __tablename__ = "products"

    id = IntField(primary_key=True)
    sku = StringField(max_length=32)
    name = StringField(max_length=150)
    category = StringField(max_length=60, choices=CATEGORIES)
    pet_type = StringField(max_length=30, choices=PET_TYPES)
    breed = StringField(max_length=100, nullable=True, default="")
    price = FloatField(min_value=1000.0)
    stock = IntField(min_value=0, default=0)
    image_url = StringField(max_length=250000, nullable=True, default="")
    description = StringField(max_length=1000, nullable=True, default="")

    @property
    def stock_status(self) -> str:
        """Thuộc tính tính toán động (@property) dựa trên số lượng tồn kho."""
        if self.stock == 0:
            return "Hết hàng"
        if self.stock <= 5:
            return "Sắp hết"
        return "Còn hàng"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["stock_status"] = self.stock_status
        return data


class SpaBooking(BaseModel):
    __tablename__ = "spa_bookings"

    id = IntField(primary_key=True)
    customer_name = StringField(max_length=100)
    phone = StringField(max_length=20)
    email = StringField(max_length=120, nullable=True, default="")
    pet_name = StringField(max_length=60)
    pet_type = StringField(max_length=20, choices=["Chó", "Mèo"])
    pet_weight_kg = FloatField(min_value=0.2)
    service_name = StringField(max_length=100, choices=list(SPA_SERVICES.keys()))
    appointment_date = StringField(max_length=30)
    appointment_time = StringField(max_length=20)
    total_price = FloatField(min_value=0.0, default=0.0)
    status = StringField(max_length=40, choices=BOOKING_STATUSES, default="Chờ xác nhận")
    note = StringField(max_length=300, nullable=True, default="")
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    @staticmethod
    def calculate_service_price(service_name: str, weight_kg: float) -> float:
        base_price = SPA_SERVICES.get(service_name, 150000.0)
        if weight_kg > 10:
            multiplier = 1.4
        elif weight_kg >= 5:
            multiplier = 1.2
        else:
            multiplier = 1.0
        return round(base_price * multiplier, 0)

    def save(self) -> "SpaBooking":
        """Lưu vào SQLite và đồng bộ xuống file JSON bền vững."""
        super().save()
        self._persist_to_json_file()
        return self

    def _persist_to_json_file(self) -> None:
        """Lưu bản sao lịch hẹn Spa vào bookings_store.json để không bao giờ mất khi đổi tài khoản / tắt web."""
        try:
            os.makedirs(os.path.dirname(BOOKINGS_STORE_PATH), exist_ok=True)
            records: List[Dict[str, Any]] = []
            if os.path.exists(BOOKINGS_STORE_PATH):
                with open(BOOKINGS_STORE_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        records = loaded

            entry = self.to_dict()
            key = (
                str(self.phone).strip(),
                str(self.pet_name).strip(),
                str(self.appointment_date).strip(),
                str(self.appointment_time).strip(),
            )
            updated = False
            for idx, item in enumerate(records):
                item_key = (
                    str(item.get("phone", "")).strip(),
                    str(item.get("pet_name", "")).strip(),
                    str(item.get("appointment_date", "")).strip(),
                    str(item.get("appointment_time", "")).strip(),
                )
                if item_key == key:
                    records[idx] = entry
                    updated = True
                    break
            if not updated:
                records.append(entry)

            with open(BOOKINGS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(records[-50:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def sync_all_to_json_file(cls) -> List[Dict[str, Any]]:
        """Đồng bộ toàn bộ danh sách lịch hẹn hiện tại trong SQLite xuống file JSON."""
        all_items = [b.to_dict() for b in cls.iter_all(order_by="id ASC")]
        try:
            os.makedirs(os.path.dirname(BOOKINGS_STORE_PATH), exist_ok=True)
            with open(BOOKINGS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(all_items[-50:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return all_items

    @classmethod
    def sync_from_json_store(cls) -> None:
        """Khôi phục danh sách lịch hẹn Spa từ bookings_store.json vào SQLite."""
        if not os.path.exists(BOOKINGS_STORE_PATH):
            return
        try:
            with open(BOOKINGS_STORE_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, list):
                cls.restore_bookings_list(records)
        except Exception:
            pass

    @classmethod
    def restore_bookings_list(cls, bookings: List[Dict[str, Any]]) -> None:
        """Khôi phục danh sách lịch hẹn Spa từ Cookie/JSON vào SQLite mà không tạo trùng."""
        try:
            existing_map = {
                (
                    b.phone.strip(),
                    b.pet_name.strip(),
                    b.appointment_date.strip(),
                    b.appointment_time.strip(),
                ): b
                for b in cls.iter_all()
            }
            for bd in bookings:
                if not isinstance(bd, dict):
                    continue
                phone = str(bd.get("phone", "")).strip()
                pet_name = str(bd.get("pet_name", "")).strip()
                app_date = str(bd.get("appointment_date", "")).strip()
                app_time = str(bd.get("appointment_time", "")).strip()
                if not phone or not pet_name or not app_date:
                    continue
                key = (phone, pet_name, app_date, app_time)
                status_val = str(bd.get("status", "Chờ xác nhận")).strip()
                if status_val not in BOOKING_STATUSES:
                    status_val = "Chờ xác nhận"
                if key in existing_map:
                    ex = existing_map[key]
                    if ex.status != status_val:
                        ex.status = status_val
                        super(SpaBooking, ex).save()
                    continue
                svc = str(bd.get("service_name", "Tắm sấy & Vệ sinh tai móng")).strip()
                if svc not in SPA_SERVICES:
                    svc = "Tắm sấy & Vệ sinh tai móng"
                p_type = str(bd.get("pet_type", "Mèo")).strip()
                if p_type not in ("Chó", "Mèo"):
                    p_type = "Mèo"
                new_b = cls(
                    customer_name=str(bd.get("customer_name", "Khách hàng")).strip(),
                    phone=phone,
                    email=str(bd.get("email", "")).strip(),
                    pet_name=pet_name,
                    pet_type=p_type,
                    pet_weight_kg=max(0.2, float(bd.get("pet_weight_kg", 3.5) or 3.5)),
                    service_name=svc,
                    appointment_date=app_date,
                    appointment_time=app_time or "09:00",
                    total_price=float(bd.get("total_price", 150000.0) or 150000.0),
                    status=status_val,
                    note=str(bd.get("note", "")).strip(),
                    created_at=str(
                        bd.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    ),
                )
                super(SpaBooking, new_b).save()
                existing_map[key] = new_b
        except Exception:
            pass


class Order(BaseModel):
    __tablename__ = "orders"

    id = IntField(primary_key=True)
    customer_name = StringField(max_length=100)
    phone = StringField(max_length=20)
    email = StringField(max_length=120, nullable=True, default="")
    address = StringField(max_length=255)
    items_json = StringField(max_length=4000)
    total_amount = FloatField(min_value=0.0)
    voucher_code = StringField(max_length=40, nullable=True, default="")
    discount_amount = FloatField(min_value=0.0, default=0.0)
    status = StringField(max_length=40, nullable=True, default="Chờ xác nhận")
    payment_method = StringField(max_length=30, nullable=True, default="cod")
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    @property
    def items(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.items_json)
        except Exception:
            return []

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["items"] = self.items
        return data

    def save(self) -> "Order":
        """Lưu đơn hàng vào SQLite và đồng bộ xuống file JSON bền vững."""
        super().save()
        self._persist_to_json_file()
        return self

    def _persist_to_json_file(self) -> None:
        """Lưu bản sao đơn hàng vào orders_store.json để không bao giờ mất khi đổi qua tài khoản Admin."""
        try:
            os.makedirs(os.path.dirname(ORDERS_STORE_PATH), exist_ok=True)
            records: List[Dict[str, Any]] = []
            if os.path.exists(ORDERS_STORE_PATH):
                with open(ORDERS_STORE_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        records = loaded

            entry = self.to_dict()
            key = (
                str(self.phone).strip(),
                str(self.created_at).strip(),
                round(float(self.total_amount), 0),
            )
            updated = False
            for idx, item in enumerate(records):
                item_key = (
                    str(item.get("phone", "")).strip(),
                    str(item.get("created_at", "")).strip(),
                    round(float(item.get("total_amount", 0)), 0),
                )
                if item_key == key:
                    records[idx] = entry
                    updated = True
                    break
            if not updated:
                records.append(entry)

            with open(ORDERS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(records[-50:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def sync_all_to_json_file(cls) -> List[Dict[str, Any]]:
        """Đồng bộ toàn bộ danh sách đơn hàng hiện tại trong SQLite xuống file JSON."""
        all_orders = [o.to_dict() for o in cls.iter_all(order_by="id ASC")]
        try:
            os.makedirs(os.path.dirname(ORDERS_STORE_PATH), exist_ok=True)
            with open(ORDERS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(all_orders[-50:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return all_orders

    @classmethod
    def sync_from_json_store(cls) -> None:
        """Khôi phục danh sách đơn hàng từ orders_store.json vào SQLite."""
        if not os.path.exists(ORDERS_STORE_PATH):
            return
        try:
            with open(ORDERS_STORE_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, list):
                cls.restore_orders_list(records)
        except Exception:
            pass

    @classmethod
    def restore_orders_list(cls, orders: List[Dict[str, Any]]) -> None:
        """Khôi phục danh sách đơn hàng từ Cookie/JSON vào SQLite để Admin luôn nhìn thấy đầy đủ đơn hàng."""
        try:
            existing_map = {
                (
                    o.phone.strip(),
                    o.created_at.strip(),
                    round(float(o.total_amount), 0),
                ): o
                for o in cls.iter_all()
            }
            existing_emails_created = {e.created_at.strip() for e in EmailLog.iter_all()}
            for od in orders:
                if not isinstance(od, dict):
                    continue
                phone = str(od.get("phone", "")).strip()
                created_at = str(
                    od.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                ).strip()
                total_amt = float(od.get("total_amount", 0) or 0)
                if not phone or total_amt <= 0:
                    continue
                key = (phone, created_at, round(total_amt, 0))
                status_val = str(od.get("status", "Chờ xác nhận") or "Chờ xác nhận").strip()
                if status_val not in ORDER_STATUSES:
                    status_val = "Chờ xác nhận"
                pay_val = str(od.get("payment_method", "cod") or "cod").strip()
                if key in existing_map:
                    ex = existing_map[key]
                    if getattr(ex, "status", "Chờ xác nhận") != status_val:
                        ex.status = status_val
                        super(Order, ex).save()
                    continue

                raw_items = od.get("items_json", "")
                if not raw_items and isinstance(od.get("items"), list):
                    raw_items = json.dumps(od["items"], ensure_ascii=False)
                if not raw_items:
                    raw_items = "[]"

                new_o = cls(
                    customer_name=str(od.get("customer_name", "Khách hàng")).strip(),
                    phone=phone,
                    email=str(od.get("email", "")).strip(),
                    address=str(od.get("address", "Đà Nẵng")).strip(),
                    items_json=str(raw_items),
                    total_amount=total_amt,
                    voucher_code=str(od.get("voucher_code", "") or "").strip(),
                    discount_amount=float(od.get("discount_amount", 0) or 0),
                    status=status_val,
                    payment_method=pay_val,
                    created_at=created_at,
                )
                super(Order, new_o).save()
                existing_map[key] = new_o

                # Đồng bộ luôn bản ghi thông báo Email đơn hàng vào Hộp thư Admin nếu chưa có
                if created_at not in existing_emails_created:
                    admin_mail = os.environ.get(
                        "PETSHOP_ADMIN_NOTIFY_EMAIL", "admin@meowwoof.vn"
                    )
                    log_entry = EmailLog(
                        recipient=admin_mail,
                        subject=f"[Meow & Woof - BÁO ĐƠN MỚI] Đơn hàng #{new_o.id} từ {new_o.customer_name} ({new_o.total_amount:,.0f}đ)",
                        body=(
                            f"Khách hàng: {new_o.customer_name} | SĐT: {new_o.phone} | "
                            f"Email: {new_o.email} | Địa chỉ: {new_o.address} | "
                            f"Tổng thanh toán: {new_o.total_amount:,.0f} VNĐ"
                        ),
                        delivery_status="Đã lưu vào Hộp thư Admin",
                        created_at=created_at,
                    )
                    log_entry.save()
                    existing_emails_created.add(created_at)
        except Exception:
            pass


class EmailLog(BaseModel):
    __tablename__ = "email_logs"

    id = IntField(primary_key=True)
    recipient = StringField(max_length=150)
    subject = StringField(max_length=250)
    body = StringField(max_length=15000)
    delivery_status = StringField(max_length=250, default="Đã lưu & Gửi")
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


class User(BaseModel):
    __tablename__ = "users"

    id = IntField(primary_key=True)
    username = StringField(max_length=60)
    fullname = StringField(max_length=100)
    email = StringField(max_length=120)
    phone = StringField(max_length=20)
    password_hash = StringField(max_length=120)
    role = StringField(max_length=20, default="customer")
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    def save(self) -> "User":
        """Lưu vào SQLite và đồng bộ xuống file JSON bền vững."""
        super().save()
        self._persist_to_json_file()
        return self

    def _persist_to_json_file(self) -> None:
        """Lưu bản sao tài khoản vào data/users_store.json để không bao giờ mất khi tắt web."""
        try:
            os.makedirs(os.path.dirname(USERS_STORE_PATH), exist_ok=True)
            records: List[Dict[str, str]] = []
            if os.path.exists(USERS_STORE_PATH):
                with open(USERS_STORE_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        records = loaded

            updated = False
            u_lower = self.username.strip().lower()
            entry = {
                "username": self.username,
                "fullname": self.fullname,
                "email": self.email,
                "phone": self.phone,
                "password_hash": self.password_hash,
                "role": self.role,
                "created_at": self.created_at,
            }
            for idx, item in enumerate(records):
                if str(item.get("username", "")).strip().lower() == u_lower:
                    records[idx] = entry
                    updated = True
                    break
            if not updated:
                records.append(entry)

            with open(USERS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def sync_from_json_store(cls) -> None:
        """Khôi phục danh sách tài khoản từ data/users_store.json vào SQLite khi khởi động."""
        if not os.path.exists(USERS_STORE_PATH):
            return
        try:
            with open(USERS_STORE_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, list):
                cls.restore_accounts_list(records)
        except Exception:
            pass

    @classmethod
    def sync_all_to_json_file(cls) -> List[Dict[str, str]]:
        """Đồng bộ toàn bộ danh sách tài khoản hiện tại trong SQLite xuống file JSON."""
        all_users = [
            {
                "username": u.username,
                "fullname": u.fullname,
                "email": u.email,
                "phone": u.phone,
                "password_hash": u.password_hash,
                "role": u.role,
                "created_at": u.created_at,
            }
            for u in cls.iter_all(order_by="id ASC")
        ]
        try:
            os.makedirs(os.path.dirname(USERS_STORE_PATH), exist_ok=True)
            with open(USERS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(all_users, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return all_users

    @classmethod
    def restore_accounts_list(cls, accounts: List[Dict[str, str]]) -> None:
        """Khôi phục danh sách tài khoản từ Cookie/LocalStorage/JSON vào SQLite và cập nhật thông tin mới nhất."""
        try:
            existing_map = {u.username.strip().lower(): u for u in cls.iter_all()}
            for acc in accounts:
                if not isinstance(acc, dict):
                    continue
                uname = str(acc.get("username", "")).strip()
                p_hash = str(acc.get("password_hash", "")).strip()
                if not uname or not p_hash:
                    continue
                u_key = uname.lower()
                if u_key in existing_map:
                    ex_u = existing_map[u_key]
                    changed = False
                    new_fn = str(acc.get("fullname", ex_u.fullname)).strip()
                    new_em = str(acc.get("email", ex_u.email)).strip()
                    new_ph = str(acc.get("phone", ex_u.phone)).strip()
                    if new_fn and ex_u.fullname != new_fn:
                        ex_u.fullname = new_fn
                        changed = True
                    if new_em and ex_u.email != new_em:
                        ex_u.email = new_em
                        changed = True
                    if new_ph and ex_u.phone != new_ph:
                        ex_u.phone = new_ph
                        changed = True
                    if p_hash and ex_u.password_hash != p_hash:
                        ex_u.password_hash = p_hash
                        changed = True
                    if changed:
                        super(User, ex_u).save()
                    continue
                new_u = cls(
                    username=uname,
                    fullname=str(acc.get("fullname", uname)).strip(),
                    email=str(acc.get("email", f"{uname}@gmail.com")).strip(),
                    phone=str(acc.get("phone", "0905123456")).strip(),
                    password_hash=p_hash,
                    role=str(acc.get("role", "customer")).strip() or "customer",
                    created_at=str(
                        acc.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    ),
                )
                super(User, new_u).save()
                existing_map[u_key] = new_u
        except Exception:
            pass

    def verify_password(self, password: str) -> bool:
        """Kiểm tra mật khẩu nhập vào có khớp với hash trong DB hay không."""
        return self.password_hash == hash_password(password)

    @classmethod
    def find_by_identifier(cls, identifier: str) -> Optional["User"]:
        """Tìm user theo username, email hoặc số điện thoại (tự động đồng bộ từ JSON trước)."""
        cls.sync_from_json_store()
        ident = identifier.strip().lower()
        for u in cls.iter_all():
            if (
                u.username.lower() == ident
                or u.email.lower() == ident
                or u.phone == ident
            ):
                return u
        return None


class Voucher(BaseModel):
    """Mã giảm giá / Voucher do Admin tự thiết lập chữ, mức giảm và thời gian áp dụng."""

    __tablename__ = "vouchers"

    id = IntField(primary_key=True)
    code = StringField(max_length=40)
    title = StringField(max_length=160, default="Voucher Ưu Đãi Meow & Woof")
    discount_type = StringField(max_length=20, default="fixed")  # "fixed" (VNĐ) hoặc "percent" (%)
    discount_value = FloatField(min_value=0.0, default=50000.0)
    min_order_value = FloatField(min_value=0.0, default=0.0)
    max_discount = FloatField(min_value=0.0, default=0.0)
    start_date = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d"),
    )
    expiry_date = StringField(
        max_length=40,
        default="2027-12-31",
    )
    usage_limit = IntField(min_value=1, default=100)
    used_count = IntField(min_value=0, default=0)
    is_active = IntField(min_value=0, default=1)
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    def is_currently_valid(self) -> Tuple[bool, str]:
        """Kiểm tra trạng thái hoạt động, số lượt dùng và thời hạn áp dụng của Voucher."""
        if int(self.is_active or 0) <= 0:
            return False, f"Mã Voucher '{self.code}' hiện đang tạm ngưng áp dụng."
        if int(self.used_count or 0) >= int(self.usage_limit or 100):
            return False, f"Mã Voucher '{self.code}' đã hết lượt sử dụng ({self.used_count}/{self.usage_limit})."
        today_str = datetime.now().strftime("%Y-%m-%d")
        s_date = str(self.start_date or "").strip()[:10]
        e_date = str(self.expiry_date or "").strip()[:10]
        if s_date and today_str < s_date:
            return False, f"Mã Voucher '{self.code}' sẽ bắt đầu có hiệu lực từ ngày {s_date}."
        if e_date and today_str > e_date:
            return False, f"Mã Voucher '{self.code}' đã hết hạn vào ngày {e_date}."
        return True, "Hợp lệ"

    def calculate_discount(self, subtotal: float) -> Tuple[bool, str, float]:
        """Tính số tiền được giảm trên tổng tạm tính giỏ hàng `subtotal`."""
        ok, msg = self.is_currently_valid()
        if not ok:
            return False, msg, 0.0
        min_val = float(self.min_order_value or 0.0)
        if subtotal < min_val:
            return (
                False,
                f"Mã '{self.code}' yêu cầu đơn hàng tối thiểu {min_val:,.0f} đ (Giỏ hiện tại: {subtotal:,.0f} đ).",
                0.0,
            )
        dtype = str(self.discount_type or "fixed").strip().lower()
        dval = float(self.discount_value or 0.0)
        if dtype == "percent":
            pct = max(0.0, min(100.0, dval))
            disc = round(subtotal * (pct / 100.0), 0)
            max_cap = float(self.max_discount or 0.0)
            if max_cap > 0 and disc > max_cap:
                disc = max_cap
        else:
            disc = round(dval, 0)

        disc = min(subtotal, max(0.0, disc))
        return True, f"Áp dụng mã '{self.code}' thành công (-{disc:,.0f} đ)!", disc

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        ok, status_msg = self.is_currently_valid()
        data["is_valid_now"] = ok
        data["status_label"] = "Đang hoạt động" if ok else status_msg
        if str(self.discount_type).lower() == "percent":
            cap_txt = f" (Tối đa {self.max_discount:,.0f}đ)" if float(self.max_discount or 0) > 0 else ""
            data["discount_display"] = f"Giảm {self.discount_value:.0f}%{cap_txt}"
        else:
            data["discount_display"] = f"Giảm {self.discount_value:,.0f} đ"
        return data

    def save(self) -> "Voucher":
        self.code = str(self.code or "").strip().upper()
        super().save()
        self._persist_to_json_file()
        return self

    def _persist_to_json_file(self) -> None:
        try:
            os.makedirs(os.path.dirname(VOUCHERS_STORE_PATH), exist_ok=True)
            records: List[Dict[str, Any]] = []
            if os.path.exists(VOUCHERS_STORE_PATH):
                with open(VOUCHERS_STORE_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        records = loaded

            entry = self.to_dict()
            code_upper = str(self.code).strip().upper()
            updated = False
            for idx, item in enumerate(records):
                if str(item.get("code", "")).strip().upper() == code_upper:
                    records[idx] = entry
                    updated = True
                    break
            if not updated:
                records.append(entry)

            with open(VOUCHERS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def sync_all_to_json_file(cls) -> List[Dict[str, Any]]:
        all_vouchers = [v.to_dict() for v in cls.iter_all(order_by="id DESC")]
        try:
            os.makedirs(os.path.dirname(VOUCHERS_STORE_PATH), exist_ok=True)
            with open(VOUCHERS_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(all_vouchers, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return all_vouchers

    @classmethod
    def sync_from_json_store(cls) -> None:
        if not os.path.exists(VOUCHERS_STORE_PATH):
            return
        try:
            with open(VOUCHERS_STORE_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, list):
                cls.restore_vouchers_list(records)
        except Exception:
            pass

    @classmethod
    def restore_vouchers_list(cls, vouchers: List[Dict[str, Any]]) -> None:
        try:
            existing_map = {str(v.code).strip().upper(): v for v in cls.iter_all()}
            for vd in vouchers:
                if not isinstance(vd, dict):
                    continue
                code_str = str(vd.get("code", "")).strip().upper()
                if not code_str:
                    continue
                if code_str in existing_map:
                    ex = existing_map[code_str]
                    ex.title = str(vd.get("title", ex.title)).strip()
                    ex.discount_type = str(vd.get("discount_type", ex.discount_type)).strip()
                    ex.discount_value = float(vd.get("discount_value", ex.discount_value) or 0)
                    ex.min_order_value = float(vd.get("min_order_value", ex.min_order_value) or 0)
                    ex.max_discount = float(vd.get("max_discount", ex.max_discount) or 0)
                    ex.start_date = str(vd.get("start_date", ex.start_date)).strip()
                    ex.expiry_date = str(vd.get("expiry_date", ex.expiry_date)).strip()
                    ex.usage_limit = max(1, int(vd.get("usage_limit", ex.usage_limit) or 100))
                    ex.used_count = max(int(ex.used_count or 0), int(vd.get("used_count", 0) or 0))
                    ex.is_active = int(vd.get("is_active", ex.is_active) if vd.get("is_active") is not None else 1)
                    super(Voucher, ex).save()
                    continue

                new_v = cls(
                    code=code_str,
                    title=str(vd.get("title", "Voucher Ưu Đãi Meow & Woof")).strip(),
                    discount_type=str(vd.get("discount_type", "fixed")).strip(),
                    discount_value=float(vd.get("discount_value", 50000) or 50000),
                    min_order_value=float(vd.get("min_order_value", 0) or 0),
                    max_discount=float(vd.get("max_discount", 0) or 0),
                    start_date=str(vd.get("start_date", datetime.now().strftime("%Y-%m-%d"))).strip(),
                    expiry_date=str(vd.get("expiry_date", "2027-12-31")).strip(),
                    usage_limit=max(1, int(vd.get("usage_limit", 100) or 100)),
                    used_count=max(0, int(vd.get("used_count", 0) or 0)),
                    is_active=int(vd.get("is_active", 1) if vd.get("is_active") is not None else 1),
                    created_at=str(vd.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))).strip(),
                )
                super(Voucher, new_v).save()
                existing_map[code_str] = new_v
        except Exception:
            pass

    @classmethod
    def find_by_code(cls, code: str) -> Optional["Voucher"]:
        cls.sync_from_json_store()
        c_upper = str(code or "").strip().upper()
        if not c_upper:
            return None
        for v in cls.iter_all():
            if str(v.code).strip().upper() == c_upper:
                return v
        return None


