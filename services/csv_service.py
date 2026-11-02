"""
services/csv_service.py
Xử lý xuất và nhập dữ liệu sản phẩm định dạng CSV bằng Generator Streaming (CLO4 & CLO5).
"""

from typing import Any, Dict, Generator, List
from core.orm import ValidationError
from core.paginator import parse_csv_stream, stream_csv_export
from models.product import Product


def export_products_csv_generator() -> Generator[str, None, None]:
    """Trả về Generator xuất từng dòng CSV của danh sách sản phẩm."""
    fieldnames = ["sku", "name", "category", "pet_type", "breed", "price", "stock", "image_url", "description"]
    record_stream = (p.to_dict() for p in Product.iter_all(order_by="id ASC"))
    return stream_csv_export(record_stream, fieldnames)


def import_products_from_csv(csv_text: str) -> Dict[str, Any]:
    """
    Sử dụng Generator `parse_csv_stream` đọc từng dòng CSV,
    kiểm tra hợp lệ qua Descriptor của `Product` và lưu vào cơ sở dữ liệu.
    """
    imported_count = 0
    updated_count = 0
    errors: List[str] = []

    existing_by_sku = {p.sku: p for p in Product.iter_all()}

    for line_idx, row in enumerate(parse_csv_stream(csv_text), start=2):
        try:
            sku = row.get("sku", "").strip()
            if not sku:
                raise ValidationError("Thiếu mã SKU.")

            if sku in existing_by_sku:
                prod = existing_by_sku[sku]
                prod.name = row.get("name", prod.name)
                prod.category = row.get("category", prod.category)
                prod.pet_type = row.get("pet_type", prod.pet_type)
                prod.breed = row.get("breed", prod.breed)
                prod.price = row.get("price", prod.price)
                prod.stock = row.get("stock", prod.stock)
                if row.get("image_url"):
                    prod.image_url = row.get("image_url")
                prod.description = row.get("description", prod.description)
                prod.save()
                updated_count += 1
            else:
                new_prod = Product(
                    sku=sku,
                    name=row.get("name", ""),
                    category=row.get("category", "Thức ăn"),
                    pet_type=row.get("pet_type", "Chó & Mèo"),
                    breed=row.get("breed", ""),
                    price=row.get("price", 0),
                    stock=row.get("stock", 0),
                    image_url=row.get("image_url", ""),
                    description=row.get("description", ""),
                )
                new_prod.save()
                existing_by_sku[sku] = new_prod
                imported_count += 1
        except Exception as exc:
            errors.append(f"Dòng {line_idx}: {exc}")

    return {
        "imported": imported_count,
        "updated": updated_count,
        "errors": errors,
    }

