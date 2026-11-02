"""
services/petshop_service.py
Tầng nghiệp vụ chính của cửa hàng thú cưng Meow & Woof:
1. Generators & Custom Iterators cho tìm kiếm, lọc đa tiêu chí và phân trang.
2. Tách nhỏ module chuyên biệt:
   - Thống kê doanh thu & Dashboard: `services.stats_service`
   - Đặt hàng & Transaction: `services.order_service`
   - Nhập/Xuất CSV: `services.csv_service`
   - Nghiệp vụ thú cưng: `services.pet_service`
"""

from typing import Any, Dict, List, Optional
from core.database import DatabaseSession
from core.paginator import build_filter_pipeline, paginate_stream
from data.seeds import SEED_CATALOG, get_seed_bookings, get_seed_users
from models.booking import SpaBooking
from models.email_log import EmailLog
from models.order import Order
from models.product import Product
from models.user import User
from services.csv_service import (
    export_products_csv_generator,
    import_products_from_csv,
)
from services.order_service import create_order_transactional
from services.stats_service import compute_dashboard_stats

__all__ = [
    "SEED_CATALOG",
    "init_db_and_seed",
    "query_products",
    "get_product_detail_and_related",
    "create_order_transactional",
    "compute_dashboard_stats",
    "export_products_csv_generator",
    "import_products_from_csv",
]


def init_db_and_seed() -> None:
    """Khởi tạo các bảng SQLite, tự động nâng cấp cột mới và nạp dữ liệu mẫu."""
    Product.create_table()
    SpaBooking.create_table()
    Order.create_table()
    EmailLog.create_table()
    User.create_table()

    with DatabaseSession() as db:
        for tbl in ("spa_bookings", "orders"):
            cols = [r["name"] for r in db.execute(f"PRAGMA table_info({tbl})").fetchall()]
            if "email" not in cols:
                db.execute(f"ALTER TABLE {tbl} ADD COLUMN email TEXT DEFAULT ''")

        prod_cols = [r["name"] for r in db.execute("PRAGMA table_info(products)").fetchall()]
        if "breed" not in prod_cols:
            db.execute("ALTER TABLE products ADD COLUMN breed TEXT DEFAULT ''")
        if "image_url" not in prod_cols:
            db.execute("ALTER TABLE products ADD COLUMN image_url TEXT DEFAULT ''")

    # Tự động đồng bộ các sản phẩm/thú cưng từ SEED_CATALOG sang Database
    existing_by_sku = {p.sku: p for p in Product.iter_all()}
    for item in SEED_CATALOG:
        sku = item["sku"]
        if sku not in existing_by_sku:
            Product(**item).save()
        else:
            existing = existing_by_sku[sku]
            changed = False
            if item.get("image_url") and getattr(existing, "image_url", "") != item["image_url"]:
                existing.image_url = item["image_url"]
                changed = True
            if item.get("breed") and getattr(existing, "breed", "") != item["breed"]:
                existing.breed = item["breed"]
                changed = True
            if changed:
                existing.save()

    first_booking = next(SpaBooking.iter_all(), None)
    if first_booking is None:
        for b in get_seed_bookings():
            SpaBooking(**b).save()

    first_user = next(User.iter_all(), None)
    if first_user is None:
        for u in get_seed_users():
            User(**u).save()


def query_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    pet_type: Optional[str] = None,
    breed: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id_desc",
    page: int = 1,
    page_size: int = 9,
) -> Dict[str, Any]:
    """Kết hợp Generator SQLite -> Generator Pipeline -> Custom Iterator (`paginate_stream`)."""
    order_mapping = {
        "id_desc": "id DESC",
        "price_asc": "price ASC",
        "price_desc": "price DESC",
        "stock_asc": "stock ASC",
        "name_asc": "name ASC",
    }
    sql_order = order_mapping.get(sort_by, "id DESC")
    raw_stream = Product.iter_all(order_by=sql_order)
    filtered_stream = build_filter_pipeline(
        source_stream=raw_stream,
        keyword=keyword,
        category=category,
        pet_type=pet_type,
        breed=breed,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
    )
    return paginate_stream(filtered_stream, page=page, page_size=page_size)


def get_product_detail_and_related(product_id: int) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết của 1 Thú cưng/Sản phẩm và các thú cưng/phụ kiện liên quan."""
    target = Product.get_by_id(product_id)
    if not target:
        return None

    all_items = [p.to_dict() for p in Product.iter_all(order_by="id DESC") if p.id != product_id]

    related_pets = [
        item for item in all_items
        if item["category"] in ("Chó cảnh", "Mèo cảnh")
        and (target.pet_type == "Chó & Mèo" or item["pet_type"] == target.pet_type)
    ][:4]

    related_supplies = [
        item for item in all_items
        if item["category"] not in ("Chó cảnh", "Mèo cảnh")
        and (item["pet_type"] in (target.pet_type, "Chó & Mèo") or target.pet_type == "Chó & Mèo")
    ][:4]

    return {
        "product": target.to_dict(),
        "related_pets": related_pets,
        "related_supplies": related_supplies,
    }
