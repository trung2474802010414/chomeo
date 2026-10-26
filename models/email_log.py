"""
models/email_log.py
Model lưu lịch sử Email xác nhận đơn hàng & lịch hẹn Spa (Đáp ứng CLO2: Database + Email).
"""

from datetime import datetime
from core.orm import BaseModel, IntField, StringField


class EmailLog(BaseModel):
    __tablename__ = "email_logs"

    id = IntField(primary_key=True)
    recipient = StringField(max_length=150)
    subject = StringField(max_length=200)
    body = StringField(max_length=4000)
    delivery_status = StringField(max_length=60, default="Đã lưu & Gửi")
    created_at = StringField(
        max_length=40,
        default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

