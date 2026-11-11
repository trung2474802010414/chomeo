# -*- coding: utf-8 -*-
"""
train_ai.py - Script Huấn Luyện, Tự Dạy Thêm & Đánh Giá Mô Hình AI Tư Vấn Meow & Woof
Thực hiện:
1. Nạp bộ dữ liệu `data/ai_training_scenarios.json` và huấn luyện TF-IDF + Char N-Gram + RAG.
2. Hỗ trợ dạy thêm câu hỏi mới ngay lập tức qua CLI:
   - `python train_ai.py --add-qa "Câu hỏi" "Câu trả lời chuẩn"`
   - `python train_ai.py --add-pattern <intent_tag> "Mẫu câu mới"`
   - `python train_ai.py --list`
3. Chạy Leave-One-Out Cross-Validation (LOO-CV), 44 kịch bản thực tế & hội thoại đa lượt.
"""

import argparse
import json
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

SCENARIOS_PATH = os.path.join(BASE_DIR, "data", "ai_training_scenarios.json")


def add_custom_qa(question: str, answer: str) -> None:
    """Dạy thêm cặp Q&A mới vào `data/ai_training_scenarios.json` và lưu lại."""
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    qas = data.setdefault("custom_qas", [])
    q_clean = question.strip()
    a_clean = answer.strip()
    for item in qas:
        if item.get("question", "").strip().lower() == q_clean.lower():
            item["answer"] = a_clean
            break
    else:
        qas.append({"question": q_clean, "patterns": [q_clean], "answer": a_clean})
    with open(SCENARIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã dạy AI câu hỏi mới: '{q_clean}' (Tổng custom Q&A: {len(qas)})")


def add_intent_pattern(tag: str, pattern: str) -> None:
    """Thêm mẫu câu mới vào một nhóm tình huống (intent) có sẵn hoặc tạo nhóm mới."""
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    intents = data.setdefault("intents", [])
    pat_clean = pattern.strip()
    for item in intents:
        if item.get("tag") == tag:
            if pat_clean not in item["patterns"]:
                item["patterns"].append(pat_clean)
            break
    else:
        intents.append({"tag": tag, "priority": 85, "patterns": [pat_clean]})
    with open(SCENARIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã thêm mẫu câu '{pat_clean}' vào nhóm intent '{tag}'")


def list_training_summary() -> None:
    """Liệt kê toàn bộ 40 nhóm tình huống và kiến thức tự dạy hiện có."""
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    intents = data.get("intents", [])
    qas = data.get("custom_qas", [])
    print(f"=== DANH SÁCH TẬP HUẤN LUYỆN ({len(intents)} intents | {len(qas)} custom Q&A) ===")
    for idx, item in enumerate(intents, 1):
        print(f" {idx:2d}. {item['tag']:<28s} ({len(item.get('patterns', [])):2d} mẫu)")
    if qas:
        print("\n--- Custom Q&A đã dạy ---")
        for i, qa in enumerate(qas, 1):
            print(f" {i:2d}. Hỏi: {qa.get('question')}")


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
    """Đánh giá hiệu năng xử lý trên 44 câu hỏi thực tế chưa từng xuất hiện nguyên văn."""
    test_cases: List[Tuple[str, List[str], str]] = [
        ("tôi tên trung", ["Trung", "Meow & Woof"], "Giới thiệu tên thuần túy"),
        ("toi ten minh anh ne shop", ["Minh Anh"], "Giới thiệu tên không dấu nhiều từ"),
        ("chào shop mình tên Huy, cho xem giá chó Corgi đi", ["Huy", "Corgi", "7,900,000"], "Gộp giới thiệu tên + hỏi giống"),
        ("bạn có thể trả lời những câu nào", ["32 giống", "Spa", "Voucher"], "Hỏi khả năng của AI"),
        ("ban la ai the", ["Trợ lý AI Meow & Woof"], "Hỏi danh tính bot"),
        ("tôi muốn mua chó", ["20 giống Chó", "4,200,000", "Poodle"], "Hỏi mua chó tổng quát"),
        ("cho mình xem mua mèo bên shop", ["12 giống Mèo", "3,800,000", "Anh Lông Ngắn"], "Hỏi mua mèo (không nhầm chữ 'cho')"),
        ("tôi muốn đón một bé thú cưng về nuôi", ["32 giống Chó Mèo", "GENZVIP20"], "Hỏi mua thú cưng tổng quát"),
        ("có chó nào màu trắng tuyết không?", ["Phốc Sóc", "Samoyed"], "RAG thuộc tính màu trắng cho chó"),
        ("bên mình có mèo nào mắt xanh không", ["Ragdoll", "Xiêm"], "RAG thuộc tính mắt xanh cho mèo"),
        ("mèo nào bắt chuột giỏi nhất shop", ["Mèo Mỹ Lông Ngắn", "4,900,000"], "RAG khả năng bắt chuột"),
        ("giá chó corgi bao nhiêu", ["Corgi", "7,900,000"], "Hỏi giá giống Corgi"),
        ("meo aln gia bn vay shop", ["Mèo Anh Lông Ngắn", "4,500,000"], "Teencode không dấu (aln, bn)"),
        ("tìm chó dưới 5 triệu nuôi chung cư", ["4,200,000", "4,800,000"], "Tìm chó theo ngân sách"),
        ("cho mình xem mèo dưới 5 triệu đi", ["3,800,000", "4,500,000"], "Tìm mèo không bị nhầm chữ 'cho'"),
        ("bé nào rẻ nhất ở cửa hàng vậy", ["3,800,000", "Mèo Xiêm"], "Tìm thú cưng rẻ nhất"),
        ("cho hỏi bé mèo nào rẻ nhất shop", ["3,800,000", "Mèo Xiêm"], "Tìm mèo rẻ nhất không bị nhầm chữ 'cho'"),
        ("giống mèo nào đắt nhất shop", ["13,500,000", "Sphynx"], "Tìm thú cưng đắt nhất"),
        ("mới nuôi lần đầu ở chung cư chọn bé nào", ["Poodle", "4,800,000"], "Tư vấn chung cư/người mới"),
        ("so sánh giúp mình poodle và corgi", ["Poodle", "Corgi", "4,800,000", "7,900,000"], "So sánh 2 giống"),
        ("nên nuôi chó hay mèo vậy ad", ["Nuôi Chó", "Nuôi Mèo"], "So sánh chó vs mèo"),
        ("chó nhà em nặng 12kg tắm sấy hết bao nhiêu", ["12kg", "210,000"], "Tính phụ phí Spa >10kg"),
        ("mèo 6kg đi cắt tỉa lông giá sao", ["6kg", "336,000"], "Tính phụ phí Spa 5-10kg"),
        ("dat lich spa nhu the nao", ["/spa", "150,000"], "Hướng dẫn đặt lịch Spa không dấu"),
        ("chó bên shop mấy tháng tuổi rồi, chọn bé đực cái được không", ["2 – 2.5 tháng", "Đực", "0905.123.456"], "Hỏi tuổi, giới tính, nguồn gốc"),
        ("nuôi mèo một tháng tốn khoảng bao nhiêu tiền", ["250,000", "465,000"], "Ước tính chi phí nuôi hàng tháng"),
        ("cách dạy chó con đi vệ sinh đúng chỗ", ["7 ngày", "Xương Cao Su"], "Huấn luyện hành vi đi vệ sinh"),
        ("mèo hay cào ghế sofa phải làm sao", ["Trụ Cào Móng", "190,000"], "Khắc phục hành vi mèo cào sofa"),
        ("chó rụng lông nhiều quá bao lâu tắm một lần", ["7–10 ngày", "Sữa tắm SOS"], "Chăm sóc giảm rụng lông & tần suất tắm"),
        ("lịch tiêm phòng cho chó con gồm mấy mũi vậy ad", ["6–8 tuần", "1–2 mũi"], "Lịch tiêm phòng & tẩy giun chi tiết"),
        ("mèo mấy tháng thì đi triệt sản được", ["5–7 tháng", "viêm tử cung"], "Tư vấn triệt sản & sinh sản"),
        ("gợi ý đặt tên gì cho bé mèo dễ thương", ["Mochi", "Milo"], "Gợi ý đặt tên cho thú cưng"),
        ("nhà đang nuôi mèo đón thêm chó nuôi chung có đánh nhau không", ["3–5 ngày", "Pate Ciao"], "Tư vấn nuôi chung nhiều bé"),
        ("shop có làm giấy vka hay gắn microchip không", ["VKA", "Microchip", "0905.123.456"], "Custom Q&A đã dạy"),
        ("bé poodle bị tiêu chảy bỏ ăn phải làm sao", ["Poodle", "tiêu chảy", "0905.123.456"], "Sơ cứu khẩn cấp kèm tên giống"),
        ("mèo bị ve rận ngứa nhiều quá", ["Frontline Plus", "230,000"], "Xử lý ve rận kèm sản phẩm y tế"),
        ("chó con 2 tháng ăn hạt gì tốt", ["SmartHeart", "215,000"], "Tư vấn dinh dưỡng cho chó"),
        ("cửa hàng bán đồ ăn phụ kiện gì không", ["Royal Canin", "Tofu"], "Danh mục thức ăn phụ kiện"),
        ("tôi muốn đặt mua hàng trên web thì làm sao", ["/cart", "GENZVIP20"], "Hướng dẫn quy trình đặt mua"),
        ("giá hơi chát có giảm thêm được không", ["GENZVIP20", "15 ngày"], "Xử lý khách mặc cả"),
        ("giao hàng chậm quá làm ăn tệ thật", ["xin lỗi", "0905.123.456"], "Xử lý khiếu nại đồng cảm"),
        ("co voucher giam gia ko", ["GENZVIP20", "MEOW50K", "FREESHIP30K"], "Tra cứu mã giảm giá teencode"),
        ("chó bán ra có bảo hành tiêm phòng chưa", ["15 ngày", "Parvo", "vắc xin"], "Bảo hành & tiêm phòng"),
        ("bạn ăn cơm chưa hôm nay", ["24/7", "cún/mèo"], "Tán gẫu lịch sự ngoài lề"),
    ]

    passed = 0
    for q, expected_substrings, label in test_cases:
        reply = advisor.consult(q)
        ok = all(sub.lower() in reply.lower() for sub in expected_substrings)
        if ok:
            passed += 1
        else:
            print(f"[FAIL] ({label}) Q='{q}'\n  Missing: {expected_substrings}\n  Got: {reply[:180]}...")
    return passed, len(test_cases)


def evaluate_multiturn_dialogue(advisor: SmartSemanticFallbackAdvisor) -> Tuple[int, int]:
    """Mô phỏng hội thoại 7 lượt liên tiếp để kiểm tra trí nhớ ngữ cảnh, đại từ & từ ngắn 'ok'."""
    history = []
    turns = [
        ("tôi tên trung", ["Trung"]),
        ("Shop có chó Corgi không?", ["Trung", "Corgi", "7,900,000"]),
        ("ok", ["Trung", "Corgi", "7,400,000", "FREESHIP30K"]),
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
    parser = argparse.ArgumentParser(description="Huấn luyện & Tự dạy AI Meow & Woof")
    parser.add_argument("--add-qa", nargs=2, metavar=("QUESTION", "ANSWER"), help="Dạy thêm cặp câu hỏi & trả lời mới")
    parser.add_argument("--add-pattern", nargs=2, metavar=("INTENT_TAG", "PATTERN"), help="Thêm mẫu câu mới vào 1 intent")
    parser.add_argument("--list", action="store_true", help="Liệt kê danh sách intent & Q&A đã huấn luyện")
    args = parser.parse_args()

    if args.add_qa:
        add_custom_qa(args.add_qa[0], args.add_qa[1])
    if args.add_pattern:
        add_intent_pattern(args.add_pattern[0], args.add_pattern[1])
    if args.list:
        list_training_summary()
        return

    print("=" * 72)
    print("   HUẤN LUYỆN & KIỂM ĐỊNH MÔ HÌNH AI TƯ VẤN MEOW & WOOF")
    print("=" * 72)

    clf = TrainedIntentClassifier()
    stats = clf.train()
    print(f"1. Dữ liệu huấn luyện : {stats['num_intents']} tình huống | {stats['num_patterns']} mẫu câu")
    print(f"2. Không gian đặc trưng: {stats['vocab_size']} chiều TF-IDF (Word 1-2gram + Char 3-gram)")

    cv_ok, cv_total, cv_errs = leave_one_out_cv(clf)
    cv_acc = (cv_ok / cv_total * 100.0) if cv_total else 0.0
    print(f"3. Leave-One-Out CV    : {cv_ok}/{cv_total} ({cv_acc:.1f}%)")
    if cv_errs:
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
    print("=" * 72)

    if total_ok != total_all:
        sys.exit(1)


if __name__ == "__main__":
    main()
