"""
services/pet_service.py
Dịch vụ nghiệp vụ chuyên biệt dành riêng cho Thú cưng (Chó cảnh & Mèo cảnh).
Tuân thủ các quy tắc kiến trúc:
- file-size.md: File dưới 200 dòng, hàm dưới 50 dòng.
- no-any.md: Type Hints đầy đủ cho tham số và kiểu trả về.
- api-design.md: Định dạng response chuẩn mực.
"""

from typing import Any, Dict, List, Optional, Tuple
from models.product import Product


def search_pets_by_price(
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    pet_type: Optional[str] = None,
    sort_by: str = "price_asc",
    page: int = 1,
    page_size: int = 10,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Tìm kiếm và lọc danh sách thú cưng theo khoảng giá (min_price - max_price).
    
    Trả về Tuple 3 phần tử: (thành_công, thông_điệp, dữ_liệu_kết_quả).
    """
    if min_price is not None and min_price < 0:
        return False, "Giá tối thiểu (min_price) không được là số âm.", {}
    if max_price is not None and max_price < 0:
        return False, "Giá tối đa (max_price) không được là số âm.", {}
    if min_price is not None and max_price is not None and min_price > max_price:
        return False, "Giá tối thiểu (min_price) không được lớn hơn giá tối đa (max_price).", {}

    # Lọc các danh mục thuộc Thú cưng cảnh (Chó cảnh / Mèo cảnh)
    pet_categories = {"Chó cảnh", "Mèo cảnh"}

    def matches(p: Product) -> bool:
        if p.category not in pet_categories:
            return False
        if pet_type and pet_type.strip() and pet_type != "ALL":
            if p.pet_type != pet_type:
                return False
        if min_price is not None and p.price < min_price:
            return False
        if max_price is not None and p.price > max_price:
            return False
        return True

    matched_pets = [p for p in Product.iter_all() if matches(p)]

    # Sắp xếp danh sách theo giá
    if sort_by == "price_desc":
        matched_pets.sort(key=lambda x: x.price, reverse=True)
    else:
        matched_pets.sort(key=lambda x: x.price)

    # Phân trang kết quả
    total = len(matched_pets)
    safe_page = max(1, page)
    safe_size = max(1, min(100, page_size))
    start_idx = (safe_page - 1) * safe_size
    items = [p.to_dict() for p in matched_pets[start_idx : start_idx + safe_size]]
    total_pages = (total + safe_size - 1) // safe_size if total > 0 else 1

    return True, f"Tìm thấy {total} thú cưng phù hợp với tiêu chí lọc.", {
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": safe_size,
        "total_pages": total_pages,
    }

