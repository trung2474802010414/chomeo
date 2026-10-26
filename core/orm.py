"""
core/orm.py
Minh họa:
1. Descriptor Protocol (`__set_name__`, `__get__`, `__set__`) để kiểm tra kiểu dữ liệu & ràng buộc
   ngay khi gán giá trị cho thuộc tính của đối tượng (ví dụ: `product.price = -5` sẽ báo lỗi ngay).
2. Metaclass (`ModelMeta`) tự động quét các Field trong class con và sinh câu lệnh SQL tương ứng.
3. Generator (`iter_all`, `filter_by`) kết hợp Dict/List Comprehension để chuyển đổi dòng SQL thành Object.
"""

from typing import Any, Callable, Dict, Generator, List, Optional, Type
from core.database import DatabaseSession, stream_query


class ValidationError(ValueError):
    """Ngoại lệ tùy chỉnh khi dữ liệu gán vào Model không hợp lệ."""
    pass


# ============================================================================
# 1. DESCRIPTOR PROTOCOL
# ============================================================================
class Field:
    """
    Lớp cơ sở Descriptor đại diện cho một cột trong bảng SQLite.
    Khi một class chứa thuộc tính là instance của `Field`, Python sẽ tự động gọi:
    - `__set_name__(self, owner, name)` khi class được khởi tạo.
    - `__get__(self, instance, owner)` khi đọc thuộc tính `instance.attr`.
    - `__set__(self, instance, value)` khi gán thuộc tính `instance.attr = value`.
    """

    sql_type: str = "TEXT"

    def __init__(
        self,
        primary_key: bool = False,
        nullable: bool = False,
        default: Any = None,
    ):
        self.primary_key = primary_key
        self.nullable = nullable
        self.default = default
        self.name: str = ""

    def __set_name__(self, owner: Type, name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: Type) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name, self.default)

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None:
            if self.nullable or self.primary_key:
                instance.__dict__[self.name] = None
                return
            if self.default is not None:
                value = self.default() if callable(self.default) else self.default
            else:
                raise ValidationError(f"Trường '{self.name}' không được để trống (None).")
        validated_value = self.validate(value)
        instance.__dict__[self.name] = validated_value

    def validate(self, value: Any) -> Any:
        """Ghi đè ở các lớp con để kiểm tra kiểu dữ liệu cụ thể."""
        return value

    def column_ddl(self) -> str:
        """Sinh chuỗi định nghĩa cột SQL."""
        parts = [self.name, self.sql_type]
        if self.primary_key:
            parts.append("PRIMARY KEY AUTOINCREMENT")
        elif not self.nullable:
            parts.append("NOT NULL")
        return " ".join(parts)


class IntField(Field):
    sql_type = "INTEGER"

    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any) -> int:
        try:
            int_val = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Trường '{self.name}' phải là số nguyên (nhận được: {value!r}).")
        if self.min_value is not None and int_val < self.min_value:
            raise ValidationError(f"Trường '{self.name}' phải >= {self.min_value}.")
        if self.max_value is not None and int_val > self.max_value:
            raise ValidationError(f"Trường '{self.name}' phải <= {self.max_value}.")
        return int_val


class FloatField(Field):
    sql_type = "REAL"

    def __init__(self, min_value: Optional[float] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value

    def validate(self, value: Any) -> float:
        try:
            float_val = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Trường '{self.name}' phải là số thực (nhận được: {value!r}).")
        if self.min_value is not None and float_val < self.min_value:
            raise ValidationError(f"Trường '{self.name}' phải >= {self.min_value}.")
        return round(float_val, 2)


class StringField(Field):
    sql_type = "TEXT"

    def __init__(self, max_length: int = 255, choices: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length
        self.choices = choices

    def validate(self, value: Any) -> str:
        str_val = str(value).strip()
        if not self.nullable and not str_val:
            raise ValidationError(f"Trường '{self.name}' không được là chuỗi rỗng.")
        if len(str_val) > self.max_length:
            raise ValidationError(f"Trường '{self.name}' vượt quá {self.max_length} ký tự.")
        if self.choices and str_val not in self.choices:
            raise ValidationError(
                f"Trường '{self.name}' phải thuộc một trong các giá trị: {', '.join(self.choices)}."
            )
        return str_val


# ============================================================================
# 2. METACLASS CHO MINI-ORM
# ============================================================================
class ModelMeta(type):
    """
    Metaclass can thiệp vào quá trình tạo class Model (như Product, Booking).
    Nó dùng Dict Comprehension để thu thập tất cả các thuộc tính kiểu `Field`
    vào từ điển `_fields` của class.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: Dict[str, Any]):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != "BaseModel":
            # Dict Comprehension thu thập các Field descriptor được khai báo trong class
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
            # Lọc các cột khác khóa chính tự tăng bằng List Comprehension
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
        """
        Generator trả về từng đối tượng Model một cách lười biếng (lazy evaluation).
        Kết hợp `stream_query` để không bao giờ nạp toàn bộ bảng vào bộ nhớ cùng lúc.
        """
        sql = f"SELECT * FROM {cls._table_name} ORDER BY {order_by}"
        for row_dict in stream_query(sql):
            yield cls(**row_dict)

    @classmethod
    def filter_stream(
        cls,
        predicate: Callable[["BaseModel"], bool],
        order_by: str = "id DESC",
    ) -> Generator["BaseModel", None, None]:
        """
        Generator Pipeline: đọc từng bản ghi từ `iter_all()` và chỉ `yield` các bản ghi
        thỏa mãn hàm điều kiện `predicate`.
        """
        return (item for item in cls.iter_all(order_by=order_by) if predicate(item))
