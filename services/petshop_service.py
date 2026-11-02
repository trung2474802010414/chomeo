"""
services/petshop_service.py
Tầng nghiệp vụ hợp nhất của cửa hàng thú cưng Meow & Woof:
1. Khởi tạo CSDL SQLite & nạp dữ liệu mẫu (`init_db_and_seed`).
2. Truy vấn, lọc đa tiêu chí & phân trang sản phẩm (`query_products`, `get_product_detail_and_related`, `search_pets_by_price`).
3. Đặt hàng theo Transaction SQLite & gửi thông báo về Email Admin (`create_order_transactional`).
4. Xuất / Nhập CSV bằng Generator Streaming (`export_products_csv_generator`, `import_products_from_csv`).
5. Báo cáo thống kê Dashboard & Danh sách tài khoản khách hàng (`compute_dashboard_stats`).
6. Quản lý cấu hình Ngân hàng & Mã QR VietQR động (`SUPPORTED_BANKS`, `get_bank_config`, `save_bank_config`, `generate_vietqr_url`).
"""

from collections import defaultdict
import json
import os
from typing import Any, Dict, Generator, List, Optional, Tuple
import urllib.parse

from core.database import DatabaseSession, resolve_writable_json_path
from core.orm import ValidationError
from core.paginator import (
    build_filter_pipeline,
    paginate_stream,
    parse_csv_stream,
    stream_csv_export,
)
from data.seeds import SEED_CATALOG, get_seed_bookings, get_seed_users
from models.entities import (
    BOOKING_STATUSES,
    CATEGORIES,
    CAT_BREEDS,
    DOG_BREEDS,
    EmailLog,
    Order,
    PET_TYPES,
    Product,
    SPA_SERVICES,
    SpaBooking,
    User,
)
from services.email_service import send_order_confirmation_email

BANK_CONFIG_PATH = resolve_writable_json_path("bank_config.json")

SUPPORTED_BANKS: List[Dict[str, str]] = [
    {"bin": "970422", "code": "970422", "short_name": "MB", "name": "MB Bank (Ngân hàng Quân Đội)"},
    {"bin": "970436", "code": "970436", "short_name": "VCB", "name": "Vietcombank (Ngoại Thương)"},
    {"bin": "970407", "code": "970407", "short_name": "TCB", "name": "Techcombank (Kỹ Thương)"},
    {"bin": "970416", "code": "970416", "short_name": "ACB", "name": "ACB (Á Châu)"},
    {"bin": "970432", "code": "970432", "short_name": "VPB", "name": "VPBank (Việt Nam Thịnh Vượng)"},
    {"bin": "970423", "code": "970423", "short_name": "TPB", "name": "TPBank (Tiên Phong)"},
    {"bin": "970418", "code": "970418", "short_name": "BIDV", "name": "BIDV (Đầu tư & Phát triển)"},
    {"bin": "970415", "code": "970415", "short_name": "CTG", "name": "VietinBank (Công Thương)"},
    {"bin": "970405", "code": "970405", "short_name": "VBA", "name": "Agribank (Nông Nghiệp & PTNT)"},
    {"bin": "970443", "code": "970443", "short_name": "SHB", "name": "SHB (Sài Gòn - Hà Nội)"},
    {"bin": "970437", "code": "970437", "short_name": "HDB", "name": "HDBank (Phát triển TP.HCM)"},
    {"bin": "970426", "code": "970426", "short_name": "MSB", "name": "MSB (Hàng Hải)"},
    {"bin": "970441", "code": "970441", "short_name": "VIB", "name": "VIB (Quốc Tế)"},
    {"bin": "970403", "code": "970403", "short_name": "STB", "name": "Sacombank (Sài Gòn Thương Tín)"},
]

DEFAULT_BANK_CONFIG: Dict[str, Any] = {
    "bank_bin": "970422",
    "bank_name": "MB Bank (Ngân hàng Quân Đội)",
    "account_number": "0905123456",
    "account_name": "MEOW AND WOOF PET HOUSE",
    "syntax_prefix": "MEOW",
    "template": "compact2",
    "is_active": True,
}


def get_bank_config() -> Dict[str, Any]:
    """Lấy cấu hình ngân hàng hiện tại (ưu tiên biến môi trường / file JSON, trả về mặc định nếu chưa có)."""
    merged = dict(DEFAULT_BANK_CONFIG)
    env_raw = os.environ.get("PETSHOP_BANK_CONFIG", "").strip()
    if env_raw:
        try:
            data = json.loads(env_raw)
            if isinstance(data, dict):
                merged.update(data)
                return merged
        except Exception:
            pass

    if os.path.exists(BANK_CONFIG_PATH):
        try:
            with open(BANK_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged.update(data)
                    return merged
        except Exception:
            pass
    return merged


def save_bank_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Lưu cấu hình ngân hàng do Quản trị viên tùy chỉnh (tương thích 100% với Vercel Serverless & Local)."""
    current = get_bank_config()
    current["bank_bin"] = str(payload.get("bank_bin", current["bank_bin"])).strip()
    current["bank_name"] = str(payload.get("bank_name", current["bank_name"])).strip()
    current["account_number"] = str(
        payload.get("account_number", current["account_number"])
    ).strip()
    current["account_name"] = (
        str(payload.get("account_name", current["account_name"])).strip().upper()
    )
    current["syntax_prefix"] = (
        str(payload.get("syntax_prefix", current["syntax_prefix"])).strip().upper() or "MEOW"
    )
    current["template"] = str(payload.get("template", "compact2")).strip()
    current["is_active"] = bool(payload.get("is_active", True))

    os.environ["PETSHOP_BANK_CONFIG"] = json.dumps(current, ensure_ascii=False)
    try:
        os.makedirs(os.path.dirname(BANK_CONFIG_PATH), exist_ok=True)
        with open(BANK_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return current


def generate_vietqr_url(amount: float, memo: str) -> str:
    """Tạo link ảnh VietQR Napas247 động theo cấu hình ngân hàng hiện tại."""
    cfg = get_bank_config()
    bin_code = cfg.get("bank_bin", "970422")
    acc_num = cfg.get("account_number", "0905123456")
    template = cfg.get("template", "compact2")
    acc_name = cfg.get("account_name", "MEOW AND WOOF PET HOUSE")

    encoded_memo = urllib.parse.quote(memo.strip())
    encoded_name = urllib.parse.quote(acc_name)
    amt_int = int(amount)

    return (
        f"https://api.vietqr.io/image/{bin_code}-{acc_num}-{template}.png"
        f"?amount={amt_int}&addInfo={encoded_memo}&accountName={encoded_name}"
    )


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

    User.sync_from_json_store()
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


def search_pets_by_price(
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    pet_type: Optional[str] = None,
    sort_by: str = "price_asc",
    page: int = 1,
    page_size: int = 10,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Tìm kiếm và lọc danh sách thú cưng theo khoảng giá (min_price - max_price)."""
    if min_price is not None and min_price < 0:
        return False, "Giá tối thiểu (min_price) không được là số âm.", {}
    if max_price is not None and max_price < 0:
        return False, "Giá tối đa (max_price) không được là số âm.", {}
    if min_price is not None and max_price is not None and min_price > max_price:
        return False, "Giá tối thiểu (min_price) không được lớn hơn giá tối đa (max_price).", {}

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
    if sort_by == "price_desc":
        matched_pets.sort(key=lambda x: x.price, reverse=True)
    else:
        matched_pets.sort(key=lambda x: x.price)

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


def export_products_csv_generator() -> Generator[str, None, None]:
    """Trả về Generator xuất từng dòng CSV của danh sách sản phẩm."""
    fieldnames = ["sku", "name", "category", "pet_type", "breed", "price", "stock", "image_url", "description"]
    record_stream = (p.to_dict() for p in Product.iter_all(order_by="id ASC"))
    return stream_csv_export(record_stream, fieldnames)


def import_products_from_csv(csv_text: str) -> Dict[str, Any]:
    """Đọc từng dòng CSV qua Generator và lưu vào cơ sở dữ liệu."""
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


def compute_dashboard_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Tổng hợp báo cáo thống kê cho Admin Dashboard và danh sách tài khoản khách hàng."""
    products = list(Product.iter_all())
    all_bookings = list(SpaBooking.iter_all())
    all_orders = list(Order.iter_all())

    def _in_date_range(date_str: str) -> bool:
        d_only = str(date_str or "")[:10]
        if start_date and d_only < start_date:
            return False
        if end_date and d_only > end_date:
            return False
        return True

    bookings = [b for b in all_bookings if _in_date_range(b.appointment_date or b.created_at)]
    orders = [o for o in all_orders if _in_date_range(o.created_at)]

    total_inventory_value = sum(p.price * p.stock for p in products)
    total_stock_units = sum(p.stock for p in products)

    low_stock_products = [
        {"id": p.id, "sku": p.sku, "name": p.name, "stock": p.stock}
        for p in products
        if p.stock <= 5
    ]

    category_groups: Dict[str, List[Product]] = defaultdict(list)
    for p in products:
        category_groups[p.category].append(p)

    category_breakdown = {
        cat: {
            "product_count": len(items),
            "stock_units": sum(x.stock for x in items),
            "inventory_value": sum(x.price * x.stock for x in items),
        }
        for cat, items in category_groups.items()
    }

    User.sync_from_json_store()
    all_users = [u for u in User.iter_all() if u.role != "admin"]
    unique_customer_phones = (
        {b.phone for b in bookings}
        | {o.phone for o in orders}
        | {u.phone for u in all_users if u.phone}
    )

    order_revenue = sum(o.total_amount for o in orders)
    spa_revenue = sum(b.total_price for b in bookings if b.status != "Đã hủy")
    net_revenue = order_revenue + spa_revenue

    active_bookings = [b for b in bookings if b.status != "Đã hủy"]
    pending_bookings_count = sum(1 for b in bookings if b.status in ("Chờ xác nhận", "Đã xác nhận"))
    cancelled_bookings_count = sum(1 for b in bookings if b.status == "Đã hủy")
    total_transactions = len(orders) + len(active_bookings)
    avg_order_value = round(net_revenue / total_transactions, 0) if total_transactions > 0 else 0
    total_items_sold = sum(item.get("quantity", 0) for o in orders for item in o.items)

    order_pct = round((len(orders) / total_transactions) * 100) if total_transactions > 0 else 0
    spa_pct = 100 - order_pct if total_transactions > 0 else 0

    v1 = category_breakdown.get("Thức ăn", {}).get("inventory_value", 0.0)
    v2 = category_breakdown.get("Phụ kiện", {}).get("inventory_value", 0.0)
    v3 = category_breakdown.get("Vệ sinh & Chăm sóc", {}).get("inventory_value", 0.0)
    v4 = category_breakdown.get("Đồ chơi", {}).get("inventory_value", 0.0) + category_breakdown.get("Y tế & Vitamin", {}).get("inventory_value", 0.0)
    max_v = max(v1, v2, v3, v4, 1.0)
    chart_y = {
        "y1": round(160 - (v1 / max_v) * 110),
        "y2": round(160 - (v2 / max_v) * 110),
        "y3": round(160 - (v3 / max_v) * 110),
        "y4": round(160 - (v4 / max_v) * 110),
    }

    customers_map: Dict[str, Dict[str, Any]] = {}
    for u in all_users:
        key = u.phone or u.username
        customers_map[key] = {
            "username": u.username,
            "name": u.fullname,
            "phone": u.phone,
            "email": u.email,
            "created_at": u.created_at,
            "orders_count": 0,
            "bookings_count": 0,
            "total_spent": 0.0,
        }
    for o in orders:
        c = customers_map.setdefault(
            o.phone,
            {"username": "-", "name": o.customer_name, "phone": o.phone, "email": o.email, "created_at": o.created_at, "orders_count": 0, "bookings_count": 0, "total_spent": 0.0},
        )
        c["orders_count"] += 1
        c["total_spent"] += o.total_amount
    for b in bookings:
        c = customers_map.setdefault(
            b.phone,
            {"username": "-", "name": b.customer_name, "phone": b.phone, "email": b.email, "created_at": b.created_at, "orders_count": 0, "bookings_count": 0, "total_spent": 0.0},
        )
        c["bookings_count"] += 1
        if b.status != "Đã hủy":
            c["total_spent"] += b.total_price

    for c_info in customers_map.values():
        spent = c_info["total_spent"]
        if spent >= 15000000:
            c_info["vip_tier"] = "Kim Cương"
        elif spent >= 5000000:
            c_info["vip_tier"] = "Vàng"
        elif spent >= 1000000:
            c_info["vip_tier"] = "Bạc"
        else:
            c_info["vip_tier"] = "Đồng"

    return {
        "total_products": len(products),
        "total_stock_units": total_stock_units,
        "total_inventory_value": total_inventory_value,
        "low_stock_count": len(low_stock_products),
        "low_stock_products": low_stock_products,
        "category_breakdown": category_breakdown,
        "total_orders": len(orders),
        "order_revenue": order_revenue,
        "total_bookings": len(bookings),
        "spa_revenue": spa_revenue,
        "net_revenue": net_revenue,
        "total_transactions": total_transactions,
        "avg_order_value": avg_order_value,
        "pending_bookings_count": pending_bookings_count,
        "cancelled_bookings_count": cancelled_bookings_count,
        "total_items_sold": total_items_sold,
        "unique_customers_count": len(unique_customer_phones),
        "customers_list": list(customers_map.values()),
        "order_pct": order_pct,
        "spa_pct": spa_pct,
        "chart_y": chart_y,
        "categories": CATEGORIES,
        "pet_types": PET_TYPES,
        "dog_breeds": DOG_BREEDS,
        "cat_breeds": CAT_BREEDS,
        "spa_services": SPA_SERVICES,
        "booking_statuses": BOOKING_STATUSES,
    }
