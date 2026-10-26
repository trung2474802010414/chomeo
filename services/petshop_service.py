"""
services/petshop_service.py
Tầng nghiệp vụ chính, áp dụng:
1. Generators & Custom Iterators cho tìm kiếm, lọc đa tiêu chí (loài, giống, danh mục, giá) và phân trang.
2. List / Dict / Set Comprehensions & Generator Expressions để thống kê doanh thu theo kỳ báo cáo, tồn kho, gợi ý sản phẩm/thú cưng liên quan.
3. Context Manager (`DatabaseSession`) để xử lý đặt hàng trừ tồn kho theo Transaction.
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
from models.product import CATEGORIES, CAT_BREEDS, DOG_BREEDS, PET_TYPES, Product
from services.email_service import (
    send_booking_confirmation_email,
    send_order_confirmation_email,
)


SEED_CATALOG: List[Dict[str, Any]] = [
    # --- CHÓ CẢNH ---
    {
        "sku": "DOG-PET-001",
        "name": "Chó Schnauzer Tiêu Muối Thuần Chủng (2.5 tháng)",
        "category": "Chó cảnh",
        "pet_type": "Chó",
        "breed": "Chó Schnauzer",
        "price": 6500000,
        "stock": 3,
        "image_url": "https://images.unsplash.com/photo-1591768575198-88dac53fbd0a?auto=format&fit=crop&w=700&q=80",
        "description": "Bé Schnauzer lông xù màu tiêu muối cực kỳ thông minh, quấn chủ, đã tiêm 2 mũi vaccine Vanguard và tẩy giun đầy đủ.",
    },
    {
        "sku": "DOG-PET-002",
        "name": "Chó Poodle Tiny Màu Nâu Đỏ (2 tháng tuổi)",
        "category": "Chó cảnh",
        "pet_type": "Chó",
        "breed": "Chó Poodle",
        "price": 4800000,
        "stock": 4,
        "image_url": "https://images.unsplash.com/photo-1616149562385-1d84e79478bb?auto=format&fit=crop&w=700&q=80",
        "description": "Bé Poodle Tiny lông xoăn tít như gấu Teddy, không rụng lông, ăn hạt tốt và đã huấn luyện đi vệ sinh đúng chỗ.",
    },
    {
        "sku": "DOG-PET-003",
        "name": "Chó Corgi Pembroke Chân Lùn Vàng Trắng",
        "category": "Chó cảnh",
        "pet_type": "Chó",
        "breed": "Chó Corgi Chân Lùn",
        "price": 7900000,
        "stock": 2,
        "image_url": "https://images.unsplash.com/photo-1612536057832-2ff7ead58194?auto=format&fit=crop&w=700&q=80",
        "description": "Corgi mông trái tim thuần chủng, khung xương to, chân lùn đáng yêu, tính cách vui vẻ hoạt bát, bảo hành sức khỏe 30 ngày.",
    },
    {
        "sku": "DOG-PET-004",
        "name": "Chó Phốc Sóc Pomeranian Mặt Gấu Trắng Tuyết",
        "category": "Chó cảnh",
        "pet_type": "Chó",
        "breed": "Chó Phốc Sóc (Pomeranian)",
        "price": 7200000,
        "stock": 3,
        "image_url": "https://images.unsplash.com/photo-1583337130417-3346a1be7dee?auto=format&fit=crop&w=700&q=80",
        "description": "Bé Phốc Sóc mặt gấu bộ lông trắng bông xù dày dặn, lanh lợi, kèm sổ theo dõi sức khỏe thú y.",
    },
    {
        "sku": "DOG-PET-005",
        "name": "Chó Golden Retriever Thuần Chủng (2.5 tháng)",
        "category": "Chó cảnh",
        "pet_type": "Chó",
        "breed": "Chó Golden Retriever",
        "price": 6200000,
        "stock": 3,
        "image_url": "https://images.unsplash.com/photo-1552053831-71594a27632d?auto=format&fit=crop&w=700&q=80",
        "description": "Golden Retriever hiền lành, thông minh, cực kỳ thân thiện với trẻ nhỏ và dễ dạy lệnh cơ bản.",
    },
    {
        "sku": "DOG-PET-006",
        "name": "Chó Shiba Inu Vàng Đỏ Chuẩn Form Nhật",
        "category": "Chó cảnh",
        "pet_type": "Chó",
        "breed": "Chó Shiba Inu",
        "price": 9500000,
        "stock": 2,
        "image_url": "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?auto=format&fit=crop&w=700&q=80",
        "description": "Shiba Inu mặt bánh bao hay cười, tính cách sạch sẽ, trung thành, đầy đủ giấy tờ tiêm chủng.",
    },
    # --- MÈO CẢNH ---
    {
        "sku": "CAT-PET-001",
        "name": "Mèo Anh Lông Ngắn Màu Xám Xanh (British Shorthair)",
        "category": "Mèo cảnh",
        "pet_type": "Mèo",
        "breed": "Mèo Anh Lông Ngắn (ALN)",
        "price": 4500000,
        "stock": 4,
        "image_url": "https://images.unsplash.com/photo-1573865526739-10659fec78a5?auto=format&fit=crop&w=700&q=80",
        "description": "Mèo Anh Lông Ngắn má phệ, lông dày mượt màu xám xanh cổ điển, tính cách điềm tĩnh, biết đi vệ sinh vào thau cát.",
    },
    {
        "sku": "CAT-PET-002",
        "name": "Mèo Tai Cụp Scottish Fold Màu Bicolor Hồng Phấn",
        "category": "Mèo cảnh",
        "pet_type": "Mèo",
        "breed": "Mèo Tai Cụp Scottish Fold",
        "price": 5600000,
        "stock": 3,
        "image_url": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?auto=format&fit=crop&w=700&q=80",
        "description": "Bé mèo Scottish Fold tai cụp sát đầu, mắt to tròn long lanh, rất quấn người và thích được vuốt ve.",
    },
    {
        "sku": "CAT-PET-003",
        "name": "Mèo Chân Ngắn Munchkin Màu Kem Sữa",
        "category": "Mèo cảnh",
        "pet_type": "Mèo",
        "breed": "Mèo Chân Ngắn Munchkin",
        "price": 8200000,
        "stock": 2,
        "image_url": "https://images.unsplash.com/photo-1533738363-b7f9aef128ce?auto=format&fit=crop&w=700&q=80",
        "description": "Bé Munchkin 4 chân ngắn lũn cũn chạy nhảy siêu đáng yêu, ăn hạt Royal Canin và pate rất ngoan.",
    },
    {
        "sku": "CAT-PET-004",
        "name": "Mèo Ragdoll Mắt Xanh Ngọc Bích",
        "category": "Mèo cảnh",
        "pet_type": "Mèo",
        "breed": "Mèo Ragdoll",
        "price": 7500000,
        "stock": 2,
        "image_url": "https://images.unsplash.com/photo-1543852786-1cf6624b9987?auto=format&fit=crop&w=700&q=80",
        "description": "Giống mèo công chúa Ragdoll bộ lông dài mềm mại và đôi mắt xanh biếc, hiền lành và dịu dàng.",
    },
    # --- THỨC ĂN, VỆ SINH, PHỤ KIỆN, ĐỒ CHƠI, Y TẾ ---
    {
        "sku": "CAT-FD-001",
        "name": "Hạt Royal Canin Indoor 27 Cho Mèo (2kg)",
        "category": "Thức ăn",
        "pet_type": "Mèo",
        "breed": "Mèo Anh Lông Ngắn (ALN)",
        "price": 465000,
        "stock": 18,
        "image_url": "https://images.unsplash.com/photo-1589924691995-400dc9ecc119?auto=format&fit=crop&w=700&q=80",
        "description": "Thức ăn hạt khô giảm mùi phân và kiểm soát búi lông cho mèo nuôi trong nhà (Mèo Anh, Scottish, Munchkin).",
    },
    {
        "sku": "CAT-FD-002",
        "name": "Pate Mèo Ciao Churu Súp Thưởng (Gói 4 thanh)",
        "category": "Thức ăn",
        "pet_type": "Mèo",
        "breed": "Mèo Tai Cụp Scottish Fold",
        "price": 35000,
        "stock": 45,
        "image_url": "https://images.unsplash.com/photo-1574158622682-e40e69881006?auto=format&fit=crop&w=700&q=80",
        "description": "Súp thưởng vị cá ngừ và gà giúp kích thích vị giác và bổ sung nước cho mèo mọi lứa tuổi.",
    },
    {
        "sku": "DOG-FD-001",
        "name": "Hạt SmartHeart Adult Vị Bò Nướng Cho Chó (3kg)",
        "category": "Thức ăn",
        "pet_type": "Chó",
        "breed": "Chó Poodle",
        "price": 215000,
        "stock": 22,
        "image_url": "https://images.unsplash.com/photo-1568640347023-a616a30bc3bd?auto=format&fit=crop&w=700&q=80",
        "description": "Thức ăn dinh dưỡng cân bằng chứa Omega 3 & 6 dưỡng lông bóng mượt cho Poodle, Schnauzer, Corgi, Golden.",
    },
    {
        "sku": "CAT-SAN-001",
        "name": "Cát Đậu Nành Hữu Cơ Tofu Cat Litter (6L)",
        "category": "Vệ sinh & Chăm sóc",
        "pet_type": "Mèo",
        "breed": "Mèo Anh Lông Ngắn (ALN)",
        "price": 125000,
        "stock": 30,
        "image_url": "https://images.unsplash.com/photo-1513360371669-4adf3dd7dff8?auto=format&fit=crop&w=700&q=80",
        "description": "Cát vệ sinh vón cục nhanh, ít bụi, mùi trà xanh tự nhiên, có thể xả bồn cầu tiện lợi.",
    },
    {
        "sku": "PET-ACC-001",
        "name": "Balo Phi Hành Gia Trong Suốt Có Lỗ Thoáng",
        "category": "Phụ kiện",
        "pet_type": "Chó & Mèo",
        "breed": "",
        "price": 240000,
        "stock": 9,
        "image_url": "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=700&q=80",
        "description": "Balo vận chuyển chó nhỏ (Poodle, Phốc Sóc, Schnauzer) và mèo dưới 7kg đi dạo hoặc đi khám thú y.",
    },
    {
        "sku": "PET-CARE-001",
        "name": "Sữa Tắm SOS Khử Mùi & Dưỡng Lông (530ml)",
        "category": "Vệ sinh & Chăm sóc",
        "pet_type": "Chó & Mèo",
        "breed": "Chó Schnauzer",
        "price": 145000,
        "stock": 14,
        "image_url": "https://images.unsplash.com/photo-1516734212186-a967f81ad0d7?auto=format&fit=crop&w=700&q=80",
        "description": "Sữa tắm chuyên dụng làm mềm lông, lưu hương lâu và hạn chế nấm da cho chó mèo.",
    },
    {
        "sku": "CAT-TOY-001",
        "name": "Trụ Cào Móng Bọc Thừng Sisal Kèm Bóng Lông",
        "category": "Đồ chơi",
        "pet_type": "Mèo",
        "breed": "Mèo Chân Ngắn Munchkin",
        "price": 190000,
        "stock": 4,
        "image_url": "https://images.unsplash.com/photo-1545249390-6bdfa286032f?auto=format&fit=crop&w=700&q=80",
        "description": "Giúp mèo giải tỏa căng thẳng, mài móng tự nhiên và bảo vệ sofa gia đình.",
    },
    {
        "sku": "DOG-TOY-001",
        "name": "Xương Cao Su Sạch Răng Gặm Nhai Bền Bỉ",
        "category": "Đồ chơi",
        "pet_type": "Chó",
        "breed": "Chó Corgi Chân Lùn",
        "price": 68000,
        "stock": 16,
        "image_url": "https://images.unsplash.com/photo-1576201836106-db1758fd1c97?auto=format&fit=crop&w=700&q=80",
        "description": "Đồ chơi cao su tự nhiên hỗ trợ làm sạch mảng bám răng cho chó ngứa răng.",
    },
    {
        "sku": "PET-MED-001",
        "name": "Gel Dinh Dưỡng Nutri-Plus Gel Virbac (120g)",
        "category": "Y tế & Vitamin",
        "pet_type": "Chó & Mèo",
        "breed": "",
        "price": 185000,
        "stock": 11,
        "image_url": "https://images.unsplash.com/photo-1628009368231-7bb7cfcb0def?auto=format&fit=crop&w=700&q=80",
        "description": "Bổ sung năng lượng, vitamin và khoáng chất cho chó mèo biếng ăn hoặc mới ốm dậy.",
    },
    {
        "sku": "PET-MED-002",
        "name": "Nhỏ Gáy Trị Ve Rận Frontline Plus",
        "category": "Y tế & Vitamin",
        "pet_type": "Chó & Mèo",
        "breed": "",
        "price": 230000,
        "stock": 3,
        "image_url": "https://images.unsplash.com/photo-1583337130417-3346a1be7dee?auto=format&fit=crop&w=700&q=80",
        "description": "Phòng và diệt bọ chét, ve rận hiệu quả kéo dài trong 30 ngày.",
    },
]


def init_db_and_seed() -> None:
    """Khởi tạo các bảng SQLite, tự động nâng cấp cột mới và nạp dữ liệu mẫu."""
    Product.create_table()
    SpaBooking.create_table()
    Order.create_table()
    EmailLog.create_table()

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

    # Đồng bộ hoặc bổ sung các sản phẩm/thú cưng mẫu nếu chưa có hoặc chưa có ảnh
    existing_by_sku = {p.sku: p for p in Product.iter_all()}
    for item in SEED_CATALOG:
        sku = item["sku"]
        if sku not in existing_by_sku:
            Product(**item).save()
        else:
            existing = existing_by_sku[sku]
            changed = False
            if not getattr(existing, "image_url", ""):
                existing.image_url = item["image_url"]
                changed = True
            if not getattr(existing, "breed", "") and item.get("breed"):
                existing.breed = item["breed"]
                changed = True
            if changed:
                existing.save()

    first_booking = next(SpaBooking.iter_all(), None)
    if first_booking is None:
        seed_bookings = [
            {
                "customer_name": "Nguyễn Minh Anh",
                "phone": "0905123456",
                "email": "minhanh@gmail.com",
                "pet_name": "Mochi",
                "pet_type": "Mèo",
                "pet_weight_kg": 4.2,
                "service_name": "Tắm sấy & Vệ sinh tai móng",
                "appointment_date": "2026-10-26",
                "appointment_time": "09:30",
                "total_price": SpaBooking.calculate_service_price("Tắm sấy & Vệ sinh tai móng", 4.2),
                "status": "Đã xác nhận",
                "note": "Bé hơi nhát người lạ, nhờ kỹ thuật viên sấy nhiệt độ ấm vừa.",
            },
            {
                "customer_name": "Trần Hoàng Nam",
                "phone": "0988765432",
                "email": "hoangnam@gmail.com",
                "pet_name": "Lu",
                "pet_type": "Chó",
                "pet_weight_kg": 6.8,
                "service_name": "Cắt tỉa & Tạo kiểu lông (Grooming)",
                "appointment_date": "2026-10-26",
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
    breed: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = False,
    sort_by: str = "id_desc",
    page: int = 1,
    page_size: int = 9,
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
        breed=breed,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
    )
    return paginate_stream(filtered_stream, page=page, page_size=page_size)


def get_product_detail_and_related(product_id: int) -> Optional[Dict[str, Any]]:
    """
    Lấy thông tin chi tiết của 1 Thú cưng hoặc Sản phẩm cùng với:
    1. `related_pets`: Các giống Chó / Mèo cảnh liên quan (cùng loài hoặc cùng giống).
    2. `related_supplies`: Các đồ vật, thức ăn, phụ kiện liên quan phù hợp với thú cưng đó.
    Sử dụng List Comprehension trên Generator `Product.iter_all()`.
    """
    target = Product.get_by_id(product_id)
    if not target:
        return None

    all_items = [p.to_dict() for p in Product.iter_all(order_by="id DESC") if p.id != product_id]

    # Các thú cưng (Chó cảnh / Mèo cảnh) cùng loài
    related_pets = [
        item for item in all_items
        if item["category"] in ("Chó cảnh", "Mèo cảnh")
        and (target.pet_type == "Chó & Mèo" or item["pet_type"] == target.pet_type)
    ][:4]

    # Các đồ dùng, thức ăn, phụ kiện liên quan cho loài đó
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


def create_order_transactional(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tạo đơn hàng và trừ tồn kho sản phẩm trong cùng 1 giao dịch SQLite (`DatabaseSession`).
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


def compute_dashboard_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Minh họa sức mạnh của List/Dict/Set Comprehensions và Generator Expressions
    khi tổng hợp báo cáo thống kê (hỗ trợ lọc theo khoảng ngày `start_date` .. `end_date`).
    """
    products = list(Product.iter_all())
    all_bookings = list(SpaBooking.iter_all())
    all_orders = list(Order.iter_all())

    # Lọc đơn hàng và lịch hẹn theo khoảng ngày nếu người dùng chọn trên thanh Kỳ báo cáo
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

    unique_customer_phones = {b.phone for b in bookings} | {o.phone for o in orders}

    order_revenue = sum(o.total_amount for o in orders)
    spa_revenue = sum(b.total_price for b in bookings if b.status != "Đã hủy")
    net_revenue = order_revenue + spa_revenue

    active_bookings = [b for b in bookings if b.status != "Đã hủy"]
    pending_bookings_count = sum(1 for b in bookings if b.status in ("Chờ xác nhận", "Đã xác nhận"))
    cancelled_bookings_count = sum(1 for b in bookings if b.status == "Đã hủy")
    total_transactions = len(orders) + len(active_bookings)
    avg_order_value = round(net_revenue / total_transactions, 0) if total_transactions > 0 else 0
    total_items_sold = sum(item.get("quantity", 0) for o in orders for item in o.items)

    customers_map: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        c = customers_map.setdefault(
            o.phone,
            {"name": o.customer_name, "phone": o.phone, "email": o.email, "orders_count": 0, "bookings_count": 0, "total_spent": 0.0},
        )
        c["orders_count"] += 1
        c["total_spent"] += o.total_amount
    for b in bookings:
        c = customers_map.setdefault(
            b.phone,
            {"name": b.customer_name, "phone": b.phone, "email": b.email, "orders_count": 0, "bookings_count": 0, "total_spent": 0.0},
        )
        c["bookings_count"] += 1
        if b.status != "Đã hủy":
            c["total_spent"] += b.total_price

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
        "categories": CATEGORIES,
        "pet_types": PET_TYPES,
        "dog_breeds": DOG_BREEDS,
        "cat_breeds": CAT_BREEDS,
        "spa_services": SPA_SERVICES,
        "booking_statuses": BOOKING_STATUSES,
    }


def export_products_csv_generator() -> Generator[str, None, None]:
    """Trả về Generator xuất từng dòng CSV của danh sách sản phẩm."""
    fieldnames = ["sku", "name", "category", "pet_type", "breed", "price", "stock", "image_url", "description"]
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
