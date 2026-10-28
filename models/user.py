"""
models/user.py
Model Quản lý Người dùng & Thành viên (Khách hàng & Admin).
Đáp ứng CLO2: Database SQLite ORM + Phân quyền Thành viên & Quản trị.
"""

from datetime import datetime
import hashlib
from typing import Optional
from core.orm import BaseModel, IntField, StringField


def hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng thuật toán an toàn SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class User(BaseModel):
    __tablename__ = "users"

    id = IntField(primary_key=True)
    username = StringField(max_length=60)
    fullname = StringField(max_length=100)
    email = StringField(max_length=120)
    phone = StringField(max_length=20)
    password_hash = StringField(max_length=120)
    role = StringField(max_length=20, default="customer")  # "admin" hoặc "customer"
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    def verify_password(self, password: str) -> bool:
        """Kiểm tra mật khẩu nhập vào có khớp với hash trong DB hay không."""
        return self.password_hash == hash_password(password)

    @classmethod
    def find_by_identifier(cls, identifier: str) -> Optional["User"]:
        """Tìm user theo username, email hoặc số điện thoại."""
        ident = identifier.strip().lower()
        for u in cls.iter_all():
            if (
                u.username.lower() == ident
                or u.email.lower() == ident
                or u.phone == ident
            ):
                return u
        return None

