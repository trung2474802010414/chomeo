"""
models/product.py
Model Thú cưng & Sản phẩm cửa hàng (Chó cảnh, Mèo cảnh, Thức ăn, Phụ kiện...),
sử dụng Descriptor (`StringField`, `FloatField`, `IntField`) và Metaclass (`BaseModel`) từ `core.orm`.
"""

from typing import Any, Dict, List
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

# Danh sách các giống Chó cảnh & Mèo cảnh cho Mega-Menu và Bộ lọc (giống PetHouse)
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
