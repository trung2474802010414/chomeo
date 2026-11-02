"""
forms/product_forms.py
Biểu mẫu Thêm & Cập nhật Sản phẩm/Thú cưng trong trang Quản trị Admin (/admin).
"""

import re
from forms.base_form import BaseFlaskForm
from models.product import CATEGORIES, CAT_BREEDS, DOG_BREEDS, PET_TYPES


class ProductForm(BaseFlaskForm):
    """Form Thêm / Cập nhật sản phẩm trong trang `/admin`."""

    def _clean_fields(self) -> None:
        sku = str(self.raw_data.get("sku", "")).strip().upper()
        name = str(self.raw_data.get("name", "")).strip()
        category = str(self.raw_data.get("category", "")).strip()
        pet_type = str(self.raw_data.get("pet_type", "")).strip()
        breed = str(self.raw_data.get("breed", "")).strip()
        image_url = str(self.raw_data.get("image_url", "")).strip()
        description = str(self.raw_data.get("description", "")).strip()

        if not re.match(r"^[A-Z0-9][A-Z0-9\-_]{2,29}$", sku):
            self.add_error("sku", "Mã SKU phải từ 3–30 ký tự (chỉ gồm chữ in hoa, số, dấu gạch ngang '-').")
        if len(name) < 3 or len(name) > 150:
            self.add_error("name", "Tên sản phẩm / thú cưng phải từ 3 đến 150 ký tự.")
        if category not in CATEGORIES:
            self.add_error("category", "Danh mục không hợp lệ.")
        if pet_type not in PET_TYPES:
            self.add_error("pet_type", "Loài thú cưng không hợp lệ.")

        # Ràng buộc chéo giữa Loài (pet_type), Danh mục (category) và Giống (breed)
        if category == "Chó cảnh" and pet_type != "Chó":
            self.add_error("category", "Danh mục 'Chó cảnh' chỉ áp dụng khi loài thú cưng là 'Chó'.")
        elif category == "Mèo cảnh" and pet_type != "Mèo":
            self.add_error("category", "Danh mục 'Mèo cảnh' chỉ áp dụng khi loài thú cưng là 'Mèo'.")

        if len(breed) > 80:
            self.add_error("breed", "Tên giống thú cưng tối đa 80 ký tự.")
        elif breed:
            if pet_type == "Chó" and (breed in CAT_BREEDS or breed.lower().startswith("mèo")):
                self.add_error("breed", f"Loài đang chọn là 'Chó', không thể gắn giống mèo ('{breed}').")
            elif pet_type == "Mèo" and (breed in DOG_BREEDS or breed.lower().startswith("chó")):
                self.add_error("breed", f"Loài đang chọn là 'Mèo', không thể gắn giống chó ('{breed}').")

        if image_url and not (
            image_url.startswith("http://")
            or image_url.startswith("https://")
            or image_url.startswith("data:image/")
            or image_url.startswith("/")
        ):
            self.add_error("image_url", "Đường dẫn ảnh phải bắt đầu bằng https://, http:// hoặc là file ảnh tải lên.")

        try:
            price = float(self.raw_data.get("price", 0))
            if price < 1000 or price > 500_000_000:
                self.add_error("price", "Giá bán phải từ 1.000đ đến 500.000.000đ.")
        except (ValueError, TypeError):
            price = 0.0
            self.add_error("price", "Giá bán phải là số hợp lệ.")

        try:
            stock = int(self.raw_data.get("stock", 0))
            if stock < 0 or stock > 10000:
                self.add_error("stock", "Số lượng tồn kho phải từ 0 đến 10.000.")
        except (ValueError, TypeError):
            stock = 0
            self.add_error("stock", "Số lượng tồn kho phải là số nguyên.")

        if len(description) > 1000:
            self.add_error("description", "Mô tả sản phẩm tối đa 1.000 ký tự.")

        self.data = {
            "sku": sku,
            "name": name,
            "category": category,
            "pet_type": pet_type,
            "breed": breed,
            "price": price,
            "stock": stock,
            "image_url": image_url,
            "description": description,
        }

