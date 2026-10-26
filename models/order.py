"""
models/order.py
Model Đơn hàng mua sản phẩm tại Pet Shop.
"""

from datetime import datetime
import json
from typing import Any, Dict, List
from core.orm import BaseModel, FloatField, IntField, StringField


class Order(BaseModel):
    __tablename__ = "orders"

    id = IntField(primary_key=True)
    customer_name = StringField(max_length=100)
    phone = StringField(max_length=20)
    email = StringField(max_length=120, nullable=True, default="")
    address = StringField(max_length=255)
    items_json = StringField(max_length=4000)
    total_amount = FloatField(min_value=0.0)
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    @property
    def items(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.items_json)
        except Exception:
            return []

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["items"] = self.items
        return data
