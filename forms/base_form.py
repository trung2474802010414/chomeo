"""
forms/base_form.py
Lớp cơ sở BaseFlaskForm hỗ trợ CSRF Token và Form Validation theo chuẩn Flask-WTF.
"""

import hashlib
import hmac
from typing import Any, Dict, List, Optional
from flask import current_app, has_request_context, request, session


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

