# -*- coding: utf-8 -*-
"""
test_ai_advisor.py - Unit Test & Kiểm thử tự động cho Module AI Gemini 3.8 Flash & Trained NLP
"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ai_advisor import (
    GeminiFlashAdvisor,
    PetShopAIAdvisor,
    PetShopKnowledgeBase,
    SmartSemanticFallbackAdvisor,
    TrainedIntentClassifier,
)


class TestPetShopAIAdvisor(unittest.TestCase):

    def setUp(self):
        self.advisor = PetShopAIAdvisor()
        self.kb = self.advisor.kb
        self.fallback = self.advisor.fallback

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

    def test_3_trained_classifier_loaded(self):
        """Kiểm tra mô hình NLP TF-IDF đã huấn luyện từ tập dữ liệu tình huống."""
        clf = TrainedIntentClassifier()
        self.assertTrue(clf.is_trained)
        self.assertGreaterEqual(len(clf.intents), 20)
        tag, score, _ = clf.predict("chó bị tiêu chảy phải làm sao")
        self.assertEqual(tag, "pet_emergency_health")
        self.assertGreater(score, 0.3)

    def test_4_fallback_precision_corgi_and_poodle(self):
        """Kiểm tra bộ não dự phòng trả lời chính xác Corgi và Poodle (có dấu & không dấu)."""
        res_corgi = self.fallback.consult("Shop có chó Corgi không?")
        self.assertIn("Corgi", res_corgi)
        self.assertIn("7,900,000", res_corgi)

        res_poodle = self.fallback.consult("gia cho poodle bn vay shop")
        self.assertIn("Poodle", res_poodle)
        self.assertIn("4,800,000", res_poodle)

    def test_5_situational_handling_and_spa_weight(self):
        """Kiểm tra xử lý tình huống: giới thiệu tên, hỏi khả năng, mặc cả, khiếu nại, y tế, Spa theo kg."""
        res_name = self.fallback.consult("tôi tên trung")
        self.assertIn("Trung", res_name)
        self.assertNotIn("Tắm sấy 150K", res_name)

        res_cap = self.fallback.consult("bạn có thể trả lời những câu nào")
        self.assertIn("Spa", res_cap)
        self.assertIn("Voucher", res_cap)

        res_spa_heavy = self.fallback.consult("chó nặng 12kg tắm sấy bao nhiêu tiền?")
        self.assertIn("210,000", res_spa_heavy)

        res_sick = self.fallback.consult("bé Poodle bị tiêu chảy bỏ ăn phải làm sao")
        self.assertIn("Poodle", res_sick)
        self.assertIn("0905.123.456", res_sick)

        res_complaint = self.fallback.consult("giao hàng chậm quá thất vọng thật")
        self.assertIn("xin lỗi", res_complaint.lower())

        res_bargain = self.fallback.consult("giá mắc quá giảm thêm đi shop")
        self.assertIn("GENZVIP20", res_bargain)

    def test_6_multiturn_context_memory(self):
        """Kiểm tra bộ nhớ hội thoại đa lượt: nhớ tên & giống thú cưng vừa hỏi."""
        history = [
            {"role": "user", "content": "tôi tên trung"},
            {"role": "assistant", "content": "Chào bạn Trung!"},
            {"role": "user", "content": "Shop có chó Corgi không?"},
            {"role": "assistant", "content": "Chó Corgi Pembroke (`DOG-PET-003`) giá 7,900,000 đ"},
        ]
        res_follow = self.fallback.consult("con đó ăn gì shop?", history=history)
        self.assertIn("Trung", res_follow)
        self.assertIn("Corgi", res_follow)
        self.assertIn("SmartHeart", res_follow)

    def test_7_full_system_context_generation(self):
        """Kiểm tra ngữ cảnh RAG tổng hợp đầy đủ danh mục."""
        ctx = self.kb.build_full_system_context()
        self.assertIn("Meow & Woof", ctx)
        self.assertIn("GENZVIP20", ctx)
        self.assertIn("150,000 đ", ctx)


if __name__ == "__main__":
    unittest.main()
