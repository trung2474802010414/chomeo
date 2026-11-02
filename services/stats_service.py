"""
services/stats_service.py
Tổng hợp báo cáo thống kê cho Admin Dashboard bằng Comprehensions và Generator Expressions.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional
from models.booking import BOOKING_STATUSES, SPA_SERVICES, SpaBooking
from models.order import Order
from models.product import CATEGORIES, CAT_BREEDS, DOG_BREEDS, PET_TYPES, Product
from models.user import User


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

    # Tính toán tọa độ biểu đồ danh mục thực tế từ kho hàng
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

