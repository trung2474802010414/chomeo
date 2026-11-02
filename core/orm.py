"""
core/orm.py
Minh họa:
1. Descriptor Protocol: Tái sử dụng qua `core.fields`.
2. Metaclass (`ModelMeta`) tự động quét các Field trong class con và sinh câu lệnh SQL.
3. Generator (`iter_all`, `filter_by`) kết hợp Comprehensions để chuyển đổi dòng SQL thành Object.
"""

from typing import Any, Callable, Dict, Generator, List, Optional, Type
from core.database import DatabaseSession, stream_query
from core.fields import (
    Field,
    FloatField,
    IntField,
    StringField,
    ValidationError,
)

__all__ = [
    "ValidationError",
    "Field",
    "IntField",
    "FloatField",
    "StringField",
    "ModelMeta",
    "BaseModel",
]


class ModelMeta(type):
    """
    Metaclass can thiệp vào quá trình tạo class Model (như Product, Booking).
    Dùng Dict Comprehension thu thập tất cả thuộc tính kiểu `Field` vào `_fields`.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: Dict[str, Any]):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != "BaseModel":
            fields = {
                attr_name: attr_val
                for attr_name, attr_val in namespace.items()
                if isinstance(attr_val, Field)
            }
            cls._fields = fields
            cls._table_name = namespace.get("__tablename__", name.lower() + "s")
        return cls


class BaseModel(metaclass=ModelMeta):
    """
    Lớp cơ sở cho mọi bảng dữ liệu. Cung cấp các phương thức CRUD và Generator truy vấn.
    """

    _fields: Dict[str, Field] = {}
    _table_name: str = ""

    def __init__(self, **kwargs: Any):
        for field_name, field_obj in self._fields.items():
            if field_name in kwargs and kwargs[field_name] is not None:
                val = kwargs[field_name]
            else:
                val = field_obj.default() if callable(field_obj.default) else field_obj.default
            setattr(self, field_name, val)

    def to_dict(self) -> Dict[str, Any]:
        """Dùng Dict Comprehension xuất dữ liệu của instance ra dictionary."""
        return {field_name: getattr(self, field_name) for field_name in self._fields}

    @classmethod
    def create_table(cls) -> None:
        """Tự động sinh câu lệnh CREATE TABLE IF NOT EXISTS từ danh sách `_fields`."""
        columns_ddl = ", ".join(field.column_ddl() for field in cls._fields.values())
        sql = f"CREATE TABLE IF NOT EXISTS {cls._table_name} ({columns_ddl})"
        with DatabaseSession() as db:
            db.execute(sql)

    def save(self) -> "BaseModel":
        """Lưu đối tượng vào SQLite (INSERT nếu chưa có id, UPDATE nếu đã có id)."""
        pk_value = getattr(self, "id", None)
        if pk_value is None:
            non_pk_fields = [name for name, f in self._fields.items() if not f.primary_key]
            placeholders = ", ".join("?" for _ in non_pk_fields)
            columns = ", ".join(non_pk_fields)
            values = tuple(getattr(self, name) for name in non_pk_fields)

            sql = f"INSERT INTO {self._table_name} ({columns}) VALUES ({placeholders})"
            with DatabaseSession() as db:
                cursor = db.execute(sql, values)
                setattr(self, "id", cursor.lastrowid)
        else:
            non_pk_fields = [name for name, f in self._fields.items() if not f.primary_key]
            set_clause = ", ".join(f"{name} = ?" for name in non_pk_fields)
            values = tuple(getattr(self, name) for name in non_pk_fields) + (pk_value,)

            sql = f"UPDATE {self._table_name} SET {set_clause} WHERE id = ?"
            with DatabaseSession() as db:
                db.execute(sql, values)
        return self

    @classmethod
    def delete_by_id(cls, record_id: int) -> bool:
        sql = f"DELETE FROM {cls._table_name} WHERE id = ?"
        with DatabaseSession() as db:
            cursor = db.execute(sql, (record_id,))
            return cursor.rowcount > 0

    @classmethod
    def get_by_id(cls, record_id: int) -> Optional["BaseModel"]:
        sql = f"SELECT * FROM {cls._table_name} WHERE id = ?"
        with DatabaseSession() as db:
            row = db.execute(sql, (record_id,)).fetchone()
            return cls(**dict(row)) if row else None

    @classmethod
    def iter_all(cls, order_by: str = "id DESC") -> Generator["BaseModel", None, None]:
        """Generator trả về từng đối tượng Model lười biếng (lazy evaluation)."""
        sql = f"SELECT * FROM {cls._table_name} ORDER BY {order_by}"
        for row_dict in stream_query(sql):
            yield cls(**row_dict)

    @classmethod
    def filter_stream(
        cls,
        predicate: Callable[["BaseModel"], bool],
        order_by: str = "id DESC",
    ) -> Generator["BaseModel", None, None]:
        """Generator Pipeline: lọc bản ghi thỏa mãn hàm `predicate`."""
        return (item for item in cls.iter_all(order_by=order_by) if predicate(item))
