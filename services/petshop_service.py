"""
services/petshop_service.py
Tầng nghiệp vụ chính, áp dụng:
1. Generators & Custom Iterators cho tìm kiếm, lọc đa tiêu chí và phân trang.
2. List / Dict / Set Comprehensions & Generator Expressions để thống kê doanh thu, tồn kho.
3. Context Manager (`DatabaseSession`) để xử lý đặt hàng trừ tồn kho theo Transaction
   (nếu 1 sản phẩm vượt quá tồn kho thì rollback toàn bộ đơn hàng).
4. Xuất/Nhập dữ liệu CSV và JSON qua Generator streaming.
"""

from collections import defaultdict
import json
from typing import Any, Dict, Generator, List, Optional
from core.database import DatabaseSession
from core.orm import ValidationError
from core.paginator import (
    build_filter_pipeline,
    paginate_stream,
    parse_csv_stream,
    stream_csv_export,
)
from models.booking import BOOKING_STATUSES, SPA_SERVICES, SpaBooking
from models.email_log import EmailLog
from models.order import Order
from models.product import CATEGORIES, PET_TYPES, Product
from services.email_service import (
    send_booking_confirmation_email,
    send_order_confirmation_email,
)


def init_db_and_seed() -> None:
    """Khởi tạo các bảng SQLite và thêm dữ liệu mẫu nếu bảng đang trống."""
    Product.create_table()
    SpaBooking.create_table()
    Order.create_table()
    EmailLog.create_table()

    # Đảm bảo cột `email` tồn tại nếu nâng cấp từ file petshop.db cũ
    with DatabaseSession() as db:
        for tbl in ("spa_bookings", "orders"):
            cols = [r["name"] for r in db.execute(f"PRAGMA table_info({tbl})").fetchall()]
            if "email" not in cols:
                db.execute(f"ALTER TABLE {tbl} ADD COLUMN email TEXT DEFAULT ''")

    # Kiểm tra xem bảng products đã có dữ liệu chưa bằng next() trên Generator
    first_product = next(Product.iter_all(), None)
    if first_product is None:
        seed_products = [
            {
                "sku": "CAT-FD-001",
                "name": "Hạt Royal Canin Indoor 27 (2kg)",
                "category": "Thức ăn",
                "pet_type": "Mèo",
                "price": 465000,
                "stock": 18,
                "description": "Thức ăn hạt khô giảm mùi phân và kiểm soát búi lông cho mèo nuôi trong nhà.",
            },
            {
                "sku": "CAT-FD-002",
                "name": "Pate Mèo Ciao Churu Súp Thưởng (Gói 4 thanh)",
                "category": "Thức ăn",
                "pet_type": "Mèo",
                "price": 35000,
                "stock": 45,
                "description": "Súp thưởng vị cá ngừ và gà giúp kích thích vị giác và bổ sung nước cho mèo.",
            },
            {
                "sku": "DOG-FD-001",
                "name": "Hạt SmartHeart Adult Vị Bò Nướng (3kg)",
                "category": "Thức ăn",
                "pet_type": "Chó",
                "price": 215000,
                "stock": 22,
                "description": "Thức ăn dinh dưỡng cân bằng chứa Omega 3 & 6 cho chó trưởng thành.",
            },
            {
                "sku": "CAT-SAN-001",
                "name": "Cát Đậu Nành Hữu Cơ Tofu Cat Litter (6L)",
                "category": "Vệ sinh & Chăm sóc",
                "pet_type": "Mèo",
                "price": 125000,
                "stock": 30,
                "description": "Cát vệ sinh vón cục nhanh, ít bụi, mùi trà xanh tự nhiên, có thể xả bồn cầu.",
            },
            {
                "sku": "PET-ACC-001",
                "name": "Balo Phi Hành Gia Trong Suốt Có Lỗ Thoáng",
                "category": "Phụ kiện",
                "pet_type": "Chó & Mèo",
                "price": 240000,
                "stock": 9,
                "description": "Balo vận chuyển chó nhỏ và mèo dưới 7kg đi dạo hoặc đi khám thú y.",
            },
            {
                "sku": "PET-CARE-001",
                "name": "Sữa Tắm SOS Khử Mùi & Dưỡng Lông (530ml)",
                "category": "Vệ sinh & Chăm sóc",
                "pet_type": "Chó & Mèo",
                "price": 145000,
                "stock": 14,
                "description": "Sữa tắm chuyên dụng làm mềm lông, lưu hương lâu và hạn chế nấm da.",
            },
            {
                "sku": "CAT-TOY-001",
                "name": "Trụ Cào Móng Bọc Thừng Sisal Kèm Bóng Lông",
                "category": "Đồ chơi",
                "pet_type": "Mèo",
                "price": 190000,
                "stock": 4,
                "description": "Giúp mèo giải tỏa căng thẳng, mài móng tự nhiên và bảo vệ sofa gia đình.",
            },
            {
                "sku": "DOG-TOY-001",
                "name": "Xương Cao Su Sạch Răng Gặm Nhai Bền Bỉ",
                "category": "Đồ chơi",
                "pet_type": "Chó",
                "price": 68000,
                "stock": 16,
                "description": "Đồ chơi cao su tự nhiên hỗ trợ làm sạch mảng bám răng cho chó.",
            },
            {
                "sku": "PET-MED-001",
                "name": "Gel Dinh Dưỡng Nutri-Plus Gel Virbac (120g)",
                "category": "Y tế & Vitamin",
                "pet_type": "Chó & Mèo",
                "price": 185000,
                "stock": 11,
                "description": "Bổ sung năng lượng, vitamin và khoáng chất cho chó mèo biếng ăn hoặc mới ốm dậy.",
            },
            {
                "sku": "PET-MED-002",
                "name": "Nhỏ Gáy Trị Ve Rận Frontline Plus",
                "category": "Y tế & Vitamin",
                "pet_type": "Chó & Mèo",
                "price": 230000,
                "stock": 3,
                "description": "Phòng và diệt bọ chét, ve rận hiệu quả kéo dài trong 30 ngày.",
            },
        ]
        for item in seed_products:
            Product(**item).save()

    first_booking = next(SpaBooking.iter_all(), None)
    if first_booking is None:
        seed_bookings = [
            {
                "customer_name": "Nguyễn Minh Anh",
                "phone": "0905123456",
                "pet_name": "Mochi",
                "pet_type": "Mèo",
                "pet_weight_kg": 4.2,
                "service_name": "Tắm sấy & Vệ sinh tai móng",
                "appointment_date": "2026-10-27",
                "appointment_time": "09:30",
                "total_price": SpaBooking.calculate_service_price("Tắm sấy & Vệ sinh tai móng", 4.2),
                "status": "Đã xác nhận",
                "note": "Bé hơi nhát người lạ, nhờ kỹ thuật viên sấy nhiệt độ ấm vừa.",
            },
            {
                "customer_name": "Trần Hoàng Nam",
                "phone": "0988765432",
                "pet_name": "Lu",
                "pet_type": "Chó",
                "pet_weight_kg": 6.8,
                "service_name": "Cắt tỉa & Tạo kiểu lông (Grooming)",
                "appointment_date": "2026-10-28",
                "appointment_time": "14:00",
                "total_price": SpaBooking.calculate_service_price("Cắt tỉa & Tạo kiểu lông (Grooming)", 6.8),
                "status": "Chờ xác nhận",
                "note": "Tỉa gọn lông mặt và bàn chân kiểu Poodle Teddy.",
            },
        ]
        for b in seed_bookings:
            SpaBooking(**b).save()


def query_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    pet_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id_desc",
    page: int = 1,
    page_size: int = 6,
) -> Dict[str, Any]:
    """
    Kết hợp Generator SQLite (`Product.iter_all`) -> Generator Pipeline (`build_filter_pipeline`)
    -> Custom Iterator (`paginate_stream`).
    """
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
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
    )
    return paginate_stream(filtered_stream, page=page, page_size=page_size)


def create_order_transactional(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tạo đơn hàng và trừ tồn kho sản phẩm trong cùng 1 giao dịch SQLite (`DatabaseSession`).
    Nếu bất kỳ mặt hàng nào không đủ tồn kho, khối `with DatabaseSession()` sẽ ném
    `ValidationError` và tự động `rollback()` mọi lệnh UPDATE trước đó.
    """
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

        # Dùng Generator Expression tính tổng tiền đơn hàng
        total_amount = sum(item["subtotal"] for item in order_lines)

        order = Order(
            customer_name=customer_name,
            phone=phone,
            email=email,
            address=address,
            items_json=json.dumps(order_lines, ensure_ascii=False),
            total_amount=total_amount,
        )
        # Lưu đơn hàng ngay trong cùng transaction
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


def compute_dashboard_stats() -> Dict[str, Any]:
    """
    Minh họa sức mạnh của List/Dict/Set Comprehensions và Generator Expressions
    khi tổng hợp báo cáo thống kê.
    """
    products = list(Product.iter_all())
    bookings = list(SpaBooking.iter_all())
    orders = list(Order.iter_all())

    # 1. Generator Expression tính tổng giá trị tồn kho và tổng số lượng tồn
    total_inventory_value = sum(p.price * p.stock for p in products)
    total_stock_units = sum(p.stock for p in products)

    # 2. List Comprehension lọc các sản phẩm sắp hết hàng (stock <= 5)
    low_stock_products = [
        {"id": p.id, "sku": p.sku, "name": p.name, "stock": p.stock}
        for p in products
        if p.stock <= 5
    ]

    # 3. Dict Comprehension thống kê số lượng sản phẩm và giá trị kho theo từng danh mục
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

    # 4. Set Comprehension lấy tập hợp số điện thoại khách hàng duy nhất (cả mua hàng & đặt lịch Spa)
    unique_customer_phones = {b.phone for b in bookings} | {o.phone for o in orders}

    # 5. Generator Expression tính doanh thu từ đơn hàng & dịch vụ Spa (không tính lịch đã hủy)
    order_revenue = sum(o.total_amount for o in orders)
    spa_revenue = sum(b.total_price for b in bookings if b.status != "Đã hủy")

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
        "unique_customers_count": len(unique_customer_phones),
        "categories": CATEGORIES,
        "pet_types": PET_TYPES,
        "spa_services": SPA_SERVICES,
        "booking_statuses": BOOKING_STATUSES,
    }


def export_products_csv_generator() -> Generator[str, None, None]:
    """Trả về Generator xuất từng dòng CSV của danh sách sản phẩm."""
    fieldnames = ["sku", "name", "category", "pet_type", "price", "stock", "description"]
    record_stream = (p.to_dict() for p in Product.iter_all(order_by="id ASC"))
    return stream_csv_export(record_stream, fieldnames)


def import_products_from_csv(csv_text: str) -> Dict[str, Any]:
    """
    Sử dụng Generator `parse_csv_stream` đọc từng dòng CSV người dùng nhập vào,
    kiểm tra hợp lệ qua Descriptor của `Product` và lưu vào cơ sở dữ liệu.
    """
    imported_count = 0
    updated_count = 0
    errors: List[str] = []

    # Map SKU hiện có sang đối tượng Product bằng Dict Comprehension
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
                prod.price = row.get("price", prod.price)
                prod.stock = row.get("stock", prod.stock)
                prod.description = row.get("description", prod.description)
                prod.save()
                updated_count += 1
            else:
                new_prod = Product(
                    sku=sku,
                    name=row.get("name", ""),
                    category=row.get("category", "Thức ăn"),
                    pet_type=row.get("pet_type", "Chó & Mèo"),
                    price=row.get("price", 0),
                    stock=row.get("stock", 0),
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
