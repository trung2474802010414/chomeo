"""
models/booking.py
Model Lịch hẹn Spa & Chăm sóc thú cưng (Chó / Mèo).
"""

from datetime import datetime
from typing import Dict
from core.orm import BaseModel, FloatField, IntField, StringField

SPA_SERVICES: Dict[str, float] = {
    "Tắm sấy & Vệ sinh tai móng": 150000.0,
    "Cắt tỉa & Tạo kiểu lông (Grooming)": 280000.0,
    "Cạo lông máu / Cạo vệ sinh": 180000.0,
    "Khám sức khỏe & Tư vấn dinh dưỡng": 120000.0,
    "Trông giữ thú cưng (1 ngày)": 200000.0,
}

BOOKING_STATUSES = ["Chờ xác nhận", "Đã xác nhận", "Hoàn thành", "Đã hủy"]


class SpaBooking(BaseModel):
    __tablename__ = "spa_bookings"

    id = IntField(primary_key=True)
    customer_name = StringField(max_length=100)
    phone = StringField(max_length=20)
    email = StringField(max_length=120, nullable=True, default="")
    pet_name = StringField(max_length=60)
    pet_type = StringField(max_length=20, choices=["Chó", "Mèo"])
    pet_weight_kg = FloatField(min_value=0.2)
    service_name = StringField(max_length=100, choices=list(SPA_SERVICES.keys()))
    appointment_date = StringField(max_length=30)
    appointment_time = StringField(max_length=20)
    total_price = FloatField(min_value=0.0, default=0.0)
    status = StringField(max_length=40, choices=BOOKING_STATUSES, default="Chờ xác nhận")
    note = StringField(max_length=300, nullable=True, default="")
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    @staticmethod
    def calculate_service_price(service_name: str, weight_kg: float) -> float:
        """
        Tính phí dịch vụ dựa vào giá gốc + phụ phí cân nặng thú cưng:
        - Dưới 5kg: giá gốc
        - Từ 5kg đến 10kg: +20%
        - Trên 10kg: +40%
        """
        base_price = SPA_SERVICES.get(service_name, 150000.0)
        if weight_kg > 10:
            multiplier = 1.4
        elif weight_kg >= 5:
            multiplier = 1.2
        else:
            multiplier = 1.0
        return round(base_price * multiplier, 0)
