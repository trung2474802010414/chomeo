"""
core/database.py
Minh họa:
1. Context Manager (`__enter__`, `__exit__`) quản lý kết nối và transaction SQLite an toàn.
2. Generator (`yield`) kết hợp `fetchmany` để đọc dữ liệu theo từng dòng (streaming) mà không tốn RAM.
"""

import os
import sqlite3
import tempfile
from typing import Any, Dict, Generator, Iterable, Optional, Tuple


def _resolve_db_path() -> str:
    """
    Tự động chọn đường dẫn lưu file SQLite:
    - Khi chạy trên máy cá nhân (Local): lưu tại `petshop/petshop.db`.
    - Khi deploy lên môi trường Serverless như Vercel (chỉ cho phép ghi trong `/tmp`):
      tự động lưu tại `/tmp/petshop.db` để không bị lỗi Read-Only Filesystem.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.environ.get("VERCEL") or not os.access(base_dir, os.W_OK):
        return os.path.join(tempfile.gettempdir(), "petshop.db")
    return os.path.join(base_dir, "petshop.db")


DB_PATH = _resolve_db_path()


class DatabaseSession:
    """
    Context Manager tự viết bằng class thông qua 2 magic methods:
    - `__enter__`: Mở kết nối SQLite và trả về đối tượng session khi bắt đầu khối `with`.
    - `__exit__`: Tự động `commit()` nếu không có lỗi, hoặc `rollback()` nếu có Exception,
      sau đó luôn đóng kết nối.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def __enter__(self) -> "DatabaseSession":
        self.conn = sqlite3.connect(self.db_path)
        # Trả về từng dòng dưới dạng sqlite3.Row (có thể truy cập như dict)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self.conn is not None:
            if exc_type is None:
                # Không có lỗi xảy ra trong khối `with` -> lưu thay đổi
                self.conn.commit()
            else:
                # Có lỗi xảy ra -> hoàn tác toàn bộ câu lệnh trong giao dịch
                self.conn.rollback()
            self.conn.close()
        # Trả về False để nếu có Exception thì vẫn ném ra ngoài cho tầng trên xử lý
        return False

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        assert self.cursor is not None
        return self.cursor.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: Iterable[Tuple[Any, ...]]) -> sqlite3.Cursor:
        assert self.cursor is not None
        return self.cursor.executemany(sql, seq_of_params)


def stream_query(
    sql: str,
    params: Tuple[Any, ...] = (),
    batch_size: int = 50,
    db_path: str = DB_PATH,
) -> Generator[Dict[str, Any], None, None]:
    """
    Generator đọc dữ liệu từng lô (batch) từ SQLite và `yield` từng bản ghi dạng dict.

    Kiến thức Python nâng cao:
    - Thay vì dùng `fetchall()` nạp toàn bộ kết quả vào bộ nhớ (list), hàm chứa từ khóa `yield`
      sẽ trở thành một Generator Function.
    - Mỗi lần vòng lặp bên ngoài yêu cầu phần tử tiếp theo (`next()`), hàm mới chạy tiếp
      và chỉ giữ tối đa `batch_size` bản ghi trong RAM.
    """
    with DatabaseSession(db_path) as db:
        cursor = db.execute(sql, params)
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            # Dùng Generator Expression chuyển từng sqlite3.Row thành dict và yield ra ngoài
            yield from (dict(row) for row in rows)
