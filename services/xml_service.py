"""
services/xml_service.py
Xử lý xuất và nhập dữ liệu sản phẩm định dạng XML bằng `xml.etree.ElementTree` (CLO3 & CLO4).
"""

from typing import Any, Dict, List
from xml.dom import minidom
import xml.etree.ElementTree as ET

from core.orm import ValidationError
from models.product import Product


def export_products_to_xml() -> str:
    """
    Minh họa xử lý XML (CLO3 - JSON/XML):
    Chuyển toàn bộ danh sách sản phẩm từ SQLite sang tài liệu XML chuẩn bằng `xml.etree.ElementTree`.
    """
    root = ET.Element("petshop_catalog")
    root.set("version", "1.0")
    root.set("generator", "Python xml.etree.ElementTree")

    products_el = ET.SubElement(root, "products")
    for product in Product.iter_all(order_by="id ASC"):
        item_el = ET.SubElement(products_el, "product")
        item_el.set("id", str(product.id))
        item_el.set("sku", str(product.sku))

        for tag_name in ("name", "category", "pet_type", "price", "stock", "description"):
            child = ET.SubElement(item_el, tag_name)
            child.text = str(getattr(product, tag_name) or "")

    raw_bytes = ET.tostring(root, encoding="utf-8")
    parsed_dom = minidom.parseString(raw_bytes)
    return parsed_dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def import_products_from_xml(xml_text: str) -> Dict[str, Any]:
    """
    Đọc và phân tích chuỗi XML (`ET.fromstring`) để thêm hoặc cập nhật sản phẩm vào SQLite.
    """
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError as exc:
        raise ValidationError(f"Cú pháp XML không hợp lệ: {exc}")

    existing_by_sku = {p.sku: p for p in Product.iter_all()}
    imported = 0
    updated = 0
    errors: List[str] = []

    product_nodes = root.findall(".//product")
    if not product_nodes:
        raise ValidationError("Không tìm thấy thẻ <product> nào trong tài liệu XML.")

    for idx, node in enumerate(product_nodes, start=1):
        try:
            sku = (node.get("sku") or node.findtext("sku") or "").strip().upper()
            if not sku:
                raise ValidationError("Thiếu thuộc tính hoặc thẻ sku.")

            name = (node.findtext("name") or "").strip()
            category = (node.findtext("category") or "Thức ăn").strip()
            pet_type = (node.findtext("pet_type") or "Chó & Mèo").strip()
            price = float(node.findtext("price") or 0)
            stock = int(node.findtext("stock") or 0)
            description = (node.findtext("description") or "").strip()

            if sku in existing_by_sku:
                prod = existing_by_sku[sku]
                prod.name = name or prod.name
                prod.category = category
                prod.pet_type = pet_type
                prod.price = price
                prod.stock = stock
                prod.description = description
                prod.save()
                updated += 1
            else:
                new_prod = Product(
                    sku=sku,
                    name=name,
                    category=category,
                    pet_type=pet_type,
                    price=price,
                    stock=stock,
                    description=description,
                )
                new_prod.save()
                existing_by_sku[sku] = new_prod
                imported += 1
        except Exception as exc:
            errors.append(f"Thẻ <product> #{idx}: {exc}")

    return {"imported": imported, "updated": updated, "errors": errors}

