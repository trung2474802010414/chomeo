"""
tests.py
Bộ kiểm thử tự động (`unittest` + `Flask test_client`) kiểm tra toàn bộ tiêu chí trong Rubric học phần:
- CLO2 (50%): Flask Web (Template, Form validation, SQLite Database, Email confirmation log)
- CLO3 (10%): Lập trình mạng (`urllib`, `API Key`, xuất/nhập dữ liệu `JSON` & `XML`)
- CLO4 & CLO5: Custom Iterator (`PageIterator`), Generator Pipeline, Comprehensions, Descriptor ORM
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, router
from core.orm import ValidationError
from core.paginator import PageIterator, parse_csv_stream, stream_csv_export
from forms.petshop_forms import SpaBookingForm
from models.booking import SpaBooking
from models.email_log import EmailLog
from models.product import Product
from services.network_service import (
    export_products_to_xml,
    fetch_pet_breeds_via_urllib,
    import_products_from_xml,
)
from services.petshop_service import (
    compute_dashboard_stats,
    create_order_transactional,
    init_db_and_seed,
    query_products,
)


class TestAdvancedPythonPetShop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db_and_seed()
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_descriptor_validation(self) -> None:
        """Kiểm tra Descriptor tự động chặn dữ liệu sai kiểu hoặc vi phạm điều kiện."""
        with self.assertRaises(ValidationError):
            Product(
                sku="ERR-01",
                name="Sản phẩm lỗi giá",
                category="Thức ăn",
                pet_type="Mèo",
                price=-500,
                stock=5,
            )

        with self.assertRaises(ValidationError):
            Product(
                sku="ERR-02",
                name="Sản phẩm sai danh mục",
                category="Danh mục không tồn tại",
                pet_type="Mèo",
                price=50000,
                stock=5,
            )

    def test_custom_page_iterator(self) -> None:
        """Kiểm tra `PageIterator` cài đặt đúng `__iter__`, `__next__` và `StopIteration`."""
        sample_stream = (x for x in range(1, 8))
        pager = PageIterator(sample_stream, page_size=3)

        self.assertIs(iter(pager), pager)
        self.assertEqual(next(pager), [1, 2, 3])
        self.assertEqual(next(pager), [4, 5, 6])
        self.assertEqual(next(pager), [7])
        with self.assertRaises(StopIteration):
            next(pager)

    def test_generator_filter_pipeline_and_pagination(self) -> None:
        """Kiểm tra lọc sản phẩm cho Mèo kết hợp phân trang."""
        res = query_products(pet_type="Mèo", page=1, page_size=4)
        self.assertTrue(len(res["items"]) <= 4)
        for item in res["items"]:
            self.assertIn(item["pet_type"], ("Mèo", "Chó & Mèo"))

    def test_transactional_order_rollback_on_insufficient_stock(self) -> None:
        """Kiểm tra Context Manager `DatabaseSession` tự động rollback khi tồn kho không đủ."""
        first_prod = next(Product.iter_all())
        original_stock = first_prod.stock

        with self.assertRaises(ValidationError):
            create_order_transactional(
                {
                    "customer_name": "Khách Test Rollback",
                    "phone": "0999888777",
                    "address": "123 Đường Test",
                    "items": [{"product_id": first_prod.id, "quantity": original_stock + 999}],
                }
            )

        reloaded = Product.get_by_id(first_prod.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.stock, original_stock)

    def test_csv_generator_export_and_parse(self) -> None:
        """Kiểm tra xuất và đọc CSV bằng Generator."""
        rows = [
            {"sku": "TEST-1", "name": "Hạt Mèo A", "price": 100000},
            {"sku": "TEST-2", "name": "Hạt Chó B", "price": 150000},
        ]
        csv_chunks = list(stream_csv_export(rows, fieldnames=["sku", "name", "price"]))
        self.assertEqual(len(csv_chunks), 3)

        full_csv = "".join(csv_chunks)
        parsed = list(parse_csv_stream(full_csv))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["sku"], "TEST-1")

    def test_clo2_flask_pages_and_forms_and_email(self) -> None:
        """Kiểm tra CLO2: Các trang Flask Template, Form Validation và gửi Email xác nhận."""
        for route in ("/", "/shop", "/spa", "/cart", "/network", "/admin"):
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Trang {route} phải trả về HTTP 200")

        # Kiểm tra Form Validation bắt lỗi SĐT sai
        bad_form = SpaBookingForm({"customer_name": "A", "phone": "abc"})
        self.assertFalse(bad_form.validate())
        self.assertIn("phone", bad_form.errors)

        # Kiểm tra đặt lịch Spa qua POST tạo bản ghi EmailLog
        before_emails = len(list(EmailLog.iter_all()))
        resp = self.client.post(
            "/spa",
            data={
                "customer_name": "Lê Thanh Trúc",
                "phone": "0912345678",
                "email": "thanhtruc@example.com",
                "pet_name": "Bơ",
                "pet_type": "Mèo",
                "pet_weight_kg": "4.5",
                "service_name": "Tắm sấy & Vệ sinh tai móng",
                "appointment_date": "2026-10-30",
                "appointment_time": "10:00",
                "note": "Test CLO2 Email",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        after_emails = len(list(EmailLog.iter_all()))
        self.assertGreater(after_emails, before_emails)

    def test_clo3_urllib_api_key_and_xml(self) -> None:
        """Kiểm tra CLO3: Lập trình mạng urllib + API Key và xử lý XML ElementTree."""
        breed_res = fetch_pet_breeds_via_urllib(species="cat", api_key="MY-SECRET-KEY-123")
        self.assertGreater(len(breed_res["breeds"]), 0)
        self.assertEqual(breed_res["api_key_masked"], "MY-SEC***")

        xml_str = export_products_to_xml()
        self.assertIn("<petshop_catalog", xml_str)
        self.assertIn("<product", xml_str)

        import_res = import_products_from_xml(xml_str)
        self.assertGreater(import_res["updated"], 0)

    def test_dashboard_comprehensions_and_router(self) -> None:
        """Kiểm tra hàm thống kê dùng Comprehensions và bộ Decorator Router."""
        stats = compute_dashboard_stats()
        self.assertGreater(stats["total_products"], 0)
        self.assertIn("Thức ăn", stats["category_breakdown"])

        handler, params = router.resolve("GET", "/api/products")
        self.assertIsNotNone(handler)
        status, payload = handler({"pet_type": "Mèo", "page": "1"}, {}, params)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
