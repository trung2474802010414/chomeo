"""
core/router.py
Minh họa:
1. Decorator có tham số (`@router.get("/api/...")`, `@router.post(...)`) dùng Closure 3 tầng hàm
   để đăng ký hàm xử lý (handler) gắn với biểu thức chính quy (Regex) của đường dẫn URL.
2. Decorator `@api_handler` dùng `functools.wraps` để tự động bắt lỗi `ValidationError`,
   đo thời gian thực thi (ms) và chuẩn hóa dữ liệu phản hồi JSON.
"""

import functools
import re
import time
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple
from core.orm import ValidationError


def api_handler(func: Callable) -> Callable:
    """
    Decorator bọc quanh các hàm xử lý API để:
    - Đo thời gian chạy bằng `time.perf_counter()`.
    - Bắt lỗi `ValidationError` (trả về HTTP 400) hoặc lỗi hệ thống (HTTP 500) tự động.
    - Giữ nguyên metadata (`__name__`, `__doc__`) của hàm gốc nhờ `@functools.wraps(func)`.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Tuple[int, Dict[str, Any]]:
        start = time.perf_counter()
        try:
            status_code, payload = func(*args, **kwargs)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            if isinstance(payload, dict):
                payload["_meta"] = {
                    "handler": func.__name__,
                    "execution_ms": elapsed_ms,
                }
            return status_code, payload
        except ValidationError as exc:
            return 400, {"ok": False, "error": str(exc), "error_type": "ValidationError"}
        except KeyError as exc:
            return 400, {"ok": False, "error": f"Thiếu trường bắt buộc: {exc}", "error_type": "KeyError"}
        except Exception as exc:
            return 500, {"ok": False, "error": f"Lỗi máy chủ: {exc}", "error_type": type(exc).__name__}

    return wrapper


class RouteEntry:
    """Lưu thông tin một route đã đăng ký (HTTP method, regex pattern, hàm xử lý)."""

    def __init__(self, method: str, path_template: str, handler: Callable):
        self.method = method.upper()
        self.path_template = path_template
        self.handler = handler
        # Chuyển `/api/products/{id}` thành biểu thức chính quy `^/api/products/(?P<id>[^/]+)$`
        regex_str = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path_template)
        self.pattern: Pattern[str] = re.compile(f"^{regex_str}$")

    def match(self, method: str, path: str) -> Optional[Dict[str, str]]:
        if self.method != method.upper():
            return None
        m = self.pattern.match(path)
        return m.groupdict() if m else None


class Router:
    """
    Bộ định tuyến URL tự xây dựng bằng Decorator có tham số (Parameterized Decorator).
    """

    def __init__(self) -> None:
        self.routes: List[RouteEntry] = []

    def route(self, method: str, path_template: str) -> Callable:
        """
        Decorator có tham số gồm 3 tầng:
        1. `route(method, path_template)` nhận cấu hình đường dẫn.
        2. `decorator(func)` nhận hàm xử lý thực tế và đăng ký vào `self.routes`.
        3. Trả về hàm đã được bọc bởi `@api_handler`.
        """

        def decorator(func: Callable) -> Callable:
            wrapped = api_handler(func)
            self.routes.append(RouteEntry(method, path_template, wrapped))
            return wrapped

        return decorator

    def get(self, path_template: str) -> Callable:
        return self.route("GET", path_template)

    def post(self, path_template: str) -> Callable:
        return self.route("POST", path_template)

    def put(self, path_template: str) -> Callable:
        return self.route("PUT", path_template)

    def delete(self, path_template: str) -> Callable:
        return self.route("DELETE", path_template)

    def resolve(self, method: str, path: str) -> Tuple[Optional[Callable], Dict[str, str]]:
        """Tìm hàm xử lý khớp với HTTP method và đường dẫn URL."""
        for entry in self.routes:
            params = entry.match(method, path)
            if params is not None:
                return entry.handler, params
        return None, {}
