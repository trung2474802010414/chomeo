"""
core/fields.py
Cài đặt Descriptor Protocol cho Mini-ORM:
- Field: Lớp cơ sở Descriptor quản lý tên cột và sinh DDL.
- IntField, FloatField, StringField: Kiểm tra kiểu dữ liệu và ràng buộc tự động.
"""

from typing import Any, List, Optional, Type


class ValidationError(ValueError):
    """Ngoại lệ tùy chỉnh khi dữ liệu gán vào Model không hợp lệ."""
    pass


class Field:
    """Lớp cơ sở Descriptor đại diện cho một cột trong bảng SQLite."""

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

