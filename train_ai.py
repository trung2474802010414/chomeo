# -*- coding: utf-8 -*-
"""
train_ai.py - Script Huấn Luyện & Đánh Giá Mô Hình AI Tư Vấn Meow & Woof
Thực hiện:
1. Nạp bộ dữ liệu `data/ai_training_scenarios.json` và huấn luyện TF-IDF + Char N-Gram Intent Classifier.
2. Chạy Leave-One-Out Cross-Validation (LOO-CV) trên toàn bộ tập huấn luyện.
3. Đánh giá 30 tình huống thực tế mới hoàn toàn (có dấu, không dấu, teencode, gộp câu).
4. Kiểm tra hội thoại nhiều lượt (Multi-turn Memory & Coreference Resolution).
"""

import os
import sys
from typing import List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai_advisor import (
    PetShopKnowledgeBase,
    SmartSemanticFallbackAdvisor,
    TrainedIntentClassifier,
)


def leave_one_out_cv(clf: TrainedIntentClassifier) -> Tuple[int, int, List[str]]:
    """Chạy kiểm thử chéo Leave-One-Out trên toàn bộ tập dữ liệu huấn luyện."""
    all_samples: List[Tuple[str, str]] = []
    for item in clf.intents:
        tag = str(item.get("tag", "")).strip()
        for pat in item.get("patterns", []):
            all_samples.append((tag, pat))

    correct = 0
    errors: List[str] = []
    eval_clf = TrainedIntentClassifier(clf.dataset_path)
    for i, (true_tag, pat) in enumerate(all_samples):
        train_subset = all_samples[:i] + all_samples[i + 1:]
        eval_clf.train(override_docs=train_subset)
        pred_tag, score, _ = eval_clf.predict(pat)
        if pred_tag == true_tag:
            correct += 1
        else:
            errors.append(f"  '{pat}' -> pred={pred_tag} ({score:.2f}), expected={true_tag}")
    return correct, len(all_samples), errors


def evaluate_holdout_scenarios(advisor: SmartSemanticFallbackAdvisor) -> Tuple[int, int]:
    """Đánh giá hiệu năng xử lý trên 30 câu hỏi thực tế chưa từng xuất hiện nguyên văn."""
    test_cases: List[Tuple[str, List[str], str]] = [
        ("tôi tên trung", ["Trung", "Meow & Woof"], "Giới thiệu tên thuần túy"),
        ("toi ten minh anh ne shop", ["Minh Anh"], "Giới thiệu tên không dấu nhiều từ"),
        ("chào shop mình tên Huy, cho xem giá chó Corgi đi", ["Huy", "Corgi", "7,900,000"], "Gộp giới thiệu tên + hỏi giống"),
        ("bạn có thể trả lời những câu nào", ["32 giống", "Spa", "Voucher"], "Hỏi khả năng của AI"),
        ("ban la ai the", ["Trợ lý AI Meow & Woof"], "Hỏi danh tính bot"),
        ("giá chó corgi bao nhiêu", ["Corgi", "7,900,000"], "Hỏi giá giống Corgi"),
        ("meo aln gia bn vay shop", ["Mèo Anh Lông Ngắn", "4,500,000"], "Teencode không dấu (aln, bn)"),
        ("tìm chó dưới 5 triệu nuôi chung cư", ["4,200,000", "4,800,000"], "Tìm chó theo ngân sách"),
        ("bé nào rẻ nhất ở cửa hàng vậy", ["3,800,000", "Mèo Xiêm"], "Tìm thú cưng rẻ nhất"),
        ("giống mèo nào đắt nhất shop", ["13,500,000", "Sphynx"], "Tìm thú cưng đắt nhất"),
        ("mới nuôi lần đầu ở chung cư chọn bé nào", ["Poodle", "4,800,000"], "Tư vấn chung cư/người mới"),
        ("so sánh giúp mình poodle và corgi", ["Poodle", "Corgi", "4,800,000", "7,900,000"], "So sánh 2 giống"),
        ("nên nuôi chó hay mèo vậy ad", ["Nuôi Chó", "Nuôi Mèo"], "So sánh chó vs mèo"),
        ("chó nhà em nặng 12kg tắm sấy hết bao nhiêu", ["12kg", "210,000"], "Tính phụ phí Spa >10kg"),
        ("mèo 6kg đi cắt tỉa lông giá sao", ["6kg", "336,000"], "Tính phụ phí Spa 5-10kg"),
        ("dat lich spa nhu the nao", ["/spa", "150,000"], "Hướng dẫn đặt lịch Spa không dấu"),
        ("bé poodle bị tiêu chảy bỏ ăn phải làm sao", ["Poodle", "tiêu chảy", "0905.123.456"], "Sơ cứu khẩn cấp kèm tên giống"),
        ("mèo bị ve rận ngứa nhiều quá", ["Frontline Plus", "230,000"], "Xử lý ve rận kèm sản phẩm y tế"),
        ("chó con 2 tháng ăn hạt gì tốt", ["SmartHeart", "215,000"], "Tư vấn dinh dưỡng cho chó"),
        ("cửa hàng bán đồ ăn phụ kiện gì không", ["Royal Canin", "Tofu"], "Danh mục thức ăn phụ kiện"),
        ("tôi muốn đặt mua hàng trên web thì làm sao", ["/cart", "GENZVIP20"], "Hướng dẫn quy trình đặt mua"),
        ("giá hơi chát có giảm thêm được không", ["GENZVIP20", "15 ngày"], "Xử lý khách mặc cả"),
        ("giao hàng chậm quá làm ăn tệ thật", ["xin lỗi", "0905.123.456"], "Xử lý khiếu nại đồng cảm"),
        ("co voucher giam gia ko", ["GENZVIP20", "MEOW50K", "FREESHIP30K"], "Tra cứu mã giảm giá teencode"),
        ("hạng kim cương cần chi tiêu bao nhiêu", ["15,000,000", "15%"], "Chính sách VIP"),
        ("chó bán ra có bảo hành tiêm phòng chưa", ["15 ngày", "Parvo", "vắc xin"], "Bảo hành & tiêm phòng"),
        ("có ship ra hà nội và thanh toán cod ko", ["Hà Nội", "FREESHIP30K"], "Giao hàng toàn quốc"),
        ("thanh toán quét mã qr vietqr hay cod", ["VietQR", "0905123456"], "Thanh toán VietQR / COD"),
        ("tôi muốn kiểm tra đơn hoặc hủy đơn hàng", ["/orders", "0905.123.456"], "Kiểm tra & hủy đơn"),
        ("bạn ăn cơm chưa hôm nay", ["24/7", "cún/mèo"], "Tán gẫu lịch sự ngoài lề"),
    ]

    passed = 0
    for q, expected_substrings, label in test_cases:
        reply = advisor.consult(q)
        ok = all(sub.lower() in reply.lower() for sub in expected_substrings)
        if ok:
            passed += 1
        else:
            print(f"[FAIL] ({label}) Q='{q}'\n  Missing: {expected_substrings}\n  Got: {reply[:140]}...")
    return passed, len(test_cases)


def evaluate_multiturn_dialogue(advisor: SmartSemanticFallbackAdvisor) -> Tuple[int, int]:
    """Mô phỏng hội thoại 6 lượt liên tiếp để kiểm tra trí nhớ ngữ cảnh & giải quyết đại từ."""
    history = []
    turns = [
        ("tôi tên trung", ["Trung"]),
        ("Shop có chó Corgi không?", ["Trung", "Corgi", "7,900,000"]),
        ("con đó ăn gì vậy?", ["Trung", "Corgi", "SmartHeart"]),
        ("giá hơi cao có giảm được không?", ["Trung", "Corgi", "GENZVIP20", "7,400,000"]),
        ("mua con này thì làm sao?", ["Trung", "Corgi", "7,400,000", "/cart"]),
        ("cảm ơn shop nhé", ["Trung", "0905.123.456"]),
    ]
    passed = 0
    for user_msg, expected in turns:
        reply = advisor.consult(user_msg, history=history)
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        if all(sub.lower() in reply.lower() for sub in expected):
            passed += 1
        else:
            print(f"[FAIL Multi-Turn] Q='{user_msg}' Expected={expected}\n  Got: {reply}")
    return passed, len(turns)


def main():
    print("=" * 70)
    print("   HUẤN LUYỆN & KIỂM ĐỊNH MÔ HÌNH AI TƯ VẤN MEOW & WOOF")
    print("=" * 70)

    clf = TrainedIntentClassifier()
    stats = clf.train()
    print(f"1. Dữ liệu huấn luyện : {stats['num_intents']} tình huống | {stats['num_patterns']} mẫu câu")
    print(f"2. Không gian đặc trưng: {stats['vocab_size']} chiều TF-IDF (Word 1-2gram + Char 3-4gram)")

    cv_ok, cv_total, cv_errs = leave_one_out_cv(clf)
    cv_acc = (cv_ok / cv_total * 100.0) if cv_total else 0.0
    print(f"3. Leave-One-Out CV    : {cv_ok}/{cv_total} ({cv_acc:.1f}%)")
    if cv_errs and len(cv_errs) <= 10:
        print("   Mẫu nhầm LOO-CV:\n" + "\n".join(cv_errs[:5]))

    kb = PetShopKnowledgeBase()
    advisor = SmartSemanticFallbackAdvisor(kb, classifier=clf)

    s_pass, s_total = evaluate_holdout_scenarios(advisor)
    m_pass, m_total = evaluate_multiturn_dialogue(advisor)

    total_ok = s_pass + m_pass
    total_all = s_total + m_total
    acc = (total_ok / total_all * 100.0) if total_all else 0.0

    print(f"4. Kịch bản thực tế mới: {s_pass}/{s_total} ĐẠT")
    print(f"5. Hội thoại đa lượt   : {m_pass}/{m_total} ĐẠT")
    print(f"=> TỔNG KẾT XỬ LÝ TÌNH HUỐNG: {acc:.1f}% ({total_ok}/{total_all})")
    print("=" * 70)

    if total_ok != total_all:
        sys.exit(1)


if __name__ == "__main__":
    main()
