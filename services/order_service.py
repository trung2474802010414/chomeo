"""
services/order_service.py
Xử lý giao dịch đặt hàng và trừ tồn kho theo Transaction trong SQLite (`DatabaseSession`).
"""

import json
from typing import Any, Dict, List
from core.database import DatabaseSession
from core.orm import ValidationError
from models.order import Order
from services.email_service import send_order_confirmation_email


def create_order_transactional(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo đơn hàng và trừ tồn kho sản phẩm trong cùng 1 giao dịch SQLite (`DatabaseSession`)."""
    customer_name = str(payload.get("customer_name", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip()
    address = str(payload.get("address", "")).strip()
    cart_items = payload.get("items", [])

    if not customer_name or not phone or not address:
        raise ValidationError("Vui lòng nhập đầy đủ Họ tên, Số điện thoại và Địa chỉ nhận hàng.")
    if not isinstance(cart_items, list) or not cart_items:
        raise ValidationError("Giỏ hàng đang trống.")

    order_lines: List[Dict[str, Any]] = []

    with DatabaseSession() as db:
        for line in cart_items:
            product_id = int(line.get("product_id", 0))
            qty = int(line.get("quantity", 0))
            if qty <= 0:
                raise ValidationError("Số lượng mua phải lớn hơn 0.")

            row = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not row:
                raise ValidationError(f"Không tìm thấy sản phẩm có ID #{product_id}.")

            product_dict = dict(row)
            if product_dict["stock"] < qty:
                raise ValidationError(
                    f"Sản phẩm '{product_dict['name']}' chỉ còn {product_dict['stock']} món trong kho."
                )

            new_stock = product_dict["stock"] - qty
            db.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))

            order_lines.append(
                {
                    "product_id": product_id,
                    "sku": product_dict["sku"],
                    "name": product_dict["name"],
                    "price": product_dict["price"],
                    "quantity": qty,
                    "subtotal": round(product_dict["price"] * qty, 2),
                }
            )

        total_amount = sum(item["subtotal"] for item in order_lines)

        order = Order(
            customer_name=customer_name,
            phone=phone,
            email=email,
            address=address,
            items_json=json.dumps(order_lines, ensure_ascii=False),
            total_amount=total_amount,
        )
        db.execute(
            "INSERT INTO orders (customer_name, phone, email, address, items_json, total_amount, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                order.customer_name,
                order.phone,
                order.email,
                order.address,
                order.items_json,
                order.total_amount,
                order.created_at,
            ),
        )
        order.id = db.cursor.lastrowid if db.cursor else None

    order_dict = order.to_dict()
    send_order_confirmation_email(order_dict)
    return order_dict

