# -*- coding: utf-8 -*-
"""
test_ai_advisor.py - Unit Test & Kiểm thử tự động cho Module AI LLaMA Advisor
"""

import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai_advisor import PetShopAIAdvisor, PetShopKnowledgeBase, LlamaHuggingFaceAdvisor


class TestPetShopAIAdvisor(unittest.TestCase):

    def setUp(self):
        self.advisor = PetShopAIAdvisor()
        self.kb = self.advisor.kb

    def test_1_knowledge_base_loading(self):
        """Kiểm tra tri thức RAG được tải chính xác từ dữ liệu của shop."""
        self.assertGreater(len(self.kb.pets), 0, "Danh sách thú cưng không được rỗng")
        self.assertIn("Tắm sấy & Vệ sinh tai móng", self.kb.spa_services, "Phải có dịch vụ tắm sấy")
        self.assertGreaterEqual(len(self.kb.vouchers), 3, "Phải có ít nhất 3 voucher khuyến mãi")
        self.assertIn("warranty", self.kb.policies, "Phải có chính sách bảo hành")

    def test_2_apartment_and_budget_pet_search(self):
        """Kiểm tra tư vấn giống chó phù hợp chung cư và dưới 5 triệu."""
        res = self.advisor.ask("Tôi muốn tìm chó dưới 5 triệu nuôi ở chung cư")
        reply = res["reply"]
        self.assertTrue(
            "Poodle" in reply or "Pug" in reply or "chung cư" in reply.lower(),
            "Câu trả lời phải gợi ý giống chó phù hợp chung cư (Poodle, Pug)"
        )
        self.assertIn("Meow & Woof", reply, "Phải có thông tin thương hiệu")

    def test_3_spa_service_pricing_consultation(self):
        """Kiểm tra tư vấn bảng giá Spa & Grooming."""
        res = self.advisor.ask("Giá dịch vụ tắm sấy và cắt tỉa lông là bao nhiêu?")
        reply = res["reply"]
        self.assertIn("150,000", reply, "Phải báo giá đúng 150,000 đ cho Tắm sấy")
        self.assertIn("280,000", reply, "Phải báo giá đúng 280,000 đ cho Cắt tỉa")

    def test_4_voucher_and_membership_tier(self):
        """Kiểm tra tư vấn mã giảm giá và hạng VIP."""
        res = self.advisor.ask("Shop có mã giảm giá voucher nào không?")
        reply = res["reply"]
        self.assertIn("MEOW10", reply, "Phải gợi ý mã MEOW10")
        self.assertIn("WOOF15", reply, "Phải gợi ý mã WOOF15")

    def test_5_health_warranty_policy(self):
        """Kiểm tra tư vấn chính sách bảo hành 15 ngày Parvo & Care."""
        res = self.advisor.ask("Chính sách bảo hành và tiêm chủng của shop như thế nào?")
        reply = res["reply"]
        self.assertIn("15 ngày", reply, "Phải nhắc đến bảo hành 15 ngày")
        self.assertIn("Parvo", reply, "Phải nhắc đến bệnh Parvo")
        self.assertIn("Care", reply, "Phải nhắc đến bệnh Care")

    def test_6_llama_prompt_formatting(self):
        """Kiểm tra Llama 3 Chat Template formatting."""
        llama = LlamaHuggingFaceAdvisor()
        prompt = llama._format_llama_prompt([
            {"role": "system", "content": "System prompt test"},
            {"role": "user", "content": "Hello Llama"}
        ])
        self.assertIn("<|begin_of_text|>", prompt)
        self.assertIn("<|start_header_id|>system<|end_header_id|>", prompt)
        self.assertIn("<|start_header_id|>user<|end_header_id|>", prompt)
        self.assertIn("<|start_header_id|>assistant<|end_header_id|>", prompt)


if __name__ == "__main__":
    unittest.main()

