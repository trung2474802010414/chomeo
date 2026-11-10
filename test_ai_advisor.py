# -*- coding: utf-8 -*-
"""
test_ai_advisor.py - Unit Test & Kiểm thử tự động cho Module AI Gemini 3.8 Flash
"""

import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai_advisor import PetShopAIAdvisor, PetShopKnowledgeBase, GeminiFlashAdvisor, SmartSemanticFallbackAdvisor


class TestPetShopAIAdvisor(unittest.TestCase):

    def setUp(self):
        self.advisor = PetShopAIAdvisor()
        self.kb = self.advisor.kb
        self.fallback = SmartSemanticFallbackAdvisor(self.kb)

    def test_1_knowledge_base_loading(self):
        """Kiểm tra tri thức RAG được tải chính xác từ dữ liệu của shop."""
        self.assertGreater(len(self.kb.pets), 0, "Danh sách thú cưng không được rỗng")
        self.assertIn("Tắm sấy & Vệ sinh tai móng", self.kb.spa_services)
        self.assertGreaterEqual(len(self.kb.vouchers), 3)
        self.assertIn("warranty", self.kb.policies)

    def test_2_gemini_config(self):
        """Kiểm tra cấu hình model Gemini 3.8 Flash."""
        gem = GeminiFlashAdvisor(api_key="TEST_KEY_123")
        self.assertEqual(gem.model, "gemini-3.8-flash")
        self.assertEqual(gem.api_key, "TEST_KEY_123")

    def test_3_fallback_precision_corgi_and_poodle(self):
        """Kiểm tra bộ não dự phòng trả lời chính xác Corgi và Poodle."""
        res_corgi = self.fallback.consult("Shop có chó Corgi không?")
        self.assertIn("Corgi", res_corgi)
        self.assertIn("7,900,000", res_corgi)

        res_poodle = self.fallback.consult("Giá chó Poodle bao nhiêu?")
        self.assertIn("Poodle", res_poodle)
        self.assertIn("4,800,000", res_poodle)

    def test_4_fallback_spa_and_address(self):
        """Kiểm tra tra cứu giá Spa và địa chỉ shop."""
        res_spa = self.fallback.consult("Tắm chó bao nhiêu tiền?")
        self.assertIn("150,000", res_spa)

        res_addr = self.fallback.consult("Địa chỉ shop ở đâu?")
        self.assertIn("245 Nguyễn Thị Minh Khai", res_addr)

    def test_5_full_system_context_generation(self):
        """Kiểm tra ngữ cảnh RAG tổng hợp đầy đủ danh mục."""
        ctx = self.kb.build_full_system_context()
        self.assertIn("Meow & Woof", ctx)
        self.assertIn("MEOW10", ctx)
        self.assertIn("150,000 đ", ctx)


if __name__ == "__main__":
    unittest.main()
