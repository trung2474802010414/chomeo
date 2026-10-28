"""
Package models: Định nghĩa các bảng dữ liệu kế thừa từ `BaseModel` (Mini-ORM).
"""

from models.booking import SpaBooking
from models.email_log import EmailLog
from models.order import Order
from models.product import Product
from models.user import User

__all__ = ["Product", "SpaBooking", "Order", "EmailLog", "User"]
