"""
models/product.py
Model Sản phẩm cửa hàng thú cưng (Chó & Mèo), sử dụng Descriptor (`StringField`, `FloatField`, `IntField`)
và Metaclass (`BaseModel`) từ `core.orm`.
"""

from typing import Any, Dict
from core.orm import BaseModel, FloatField, IntField, StringField

CATEGORIES = ["Thức ăn", "Phụ kiện", "Vệ sinh & Chăm sóc", "Đồ chơi", "Y tế & Vitamin"]
PET_TYPES = ["Chó", "Mèo", "Chó & Mèo"]


class Product(BaseModel):
    __tablename__ = "products"

    id = IntField(primary_key=True)
    sku = StringField(max_length=32)
    name = StringField(max_length=120)
    category = StringField(max_length=60, choices=CATEGORIES)
    pet_type = StringField(max_length=30, choices=PET_TYPES)
    price = FloatField(min_value=1000.0)
    stock = IntField(min_value=0, default=0)
    description = StringField(max_length=500, nullable=True, default="")

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

