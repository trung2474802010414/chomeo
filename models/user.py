"""
models/user.py
Model Quản lý Người dùng & Thành viên (Khách hàng & Admin).
Đáp ứng CLO2: Database SQLite ORM + Phân quyền Thành viên & Quản trị + Lưu trữ bền vững.
"""

from datetime import datetime
import hashlib
import json
import os
from typing import Dict, List, Optional
from core.orm import BaseModel, IntField, StringField

USERS_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "users_store.json",
)


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
    def restore_accounts_list(cls, accounts: List[Dict[str, str]]) -> None:
        """Khôi phục danh sách tài khoản từ Cookie/LocalStorage/JSON vào SQLite."""
        try:
            existing_usernames = {u.username.strip().lower() for u in cls.iter_all()}
            for acc in accounts:
                if not isinstance(acc, dict):
                    continue
                uname = str(acc.get("username", "")).strip()
                p_hash = str(acc.get("password_hash", "")).strip()
                if not uname or not p_hash or uname.lower() in existing_usernames:
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
                existing_usernames.add(uname.lower())
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
