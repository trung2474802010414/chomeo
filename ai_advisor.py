# -*- coding: utf-8 -*-
"""
ai_advisor.py - Module AI Tư Vấn Khách Hàng Thông Minh (Google Gemini 3.8 Flash + Trained NLP Engine + RAG)
Dành cho đồ án Meow & Woof Pet House - Học phần Python Nâng Cao

Kiến trúc AI 3 tầng xử lý tình huống mượt mà:
1. Tầng Ngôn Ngữ Lớn (Google Gemini 3.8 Flash + Waterfall Fallback):
   - Kết nối trực tiếp REST API bằng thư viện chuẩn `urllib.request`.
   - System Instruction tích hợp Playbook xử lý tình huống (chăm sóc y tế, khiếu nại, mặc cả, so sánh, nhớ tên).
2. Tầng Mô Hình Học Máy NLP Nội Bộ (TrainedIntentClassifier - TF-IDF + Character N-Gram Cosine Similarity):
   - Huấn luyện trực tiếp từ bộ dữ liệu tình huống `data/ai_training_scenarios.json` bằng Pure Python.
   - Hỗ trợ chuẩn hóa tiếng Việt không dấu/có dấu, mở rộng viết tắt/teencode (`ko`, `bn`, `tr`, `aln`, `dc`...).
3. Tầng Bộ Nhớ Hội Thoại & RAG Tri Thức Cửa Hàng (Context Memory & PetShopKnowledgeBase):
   - Nhớ tên khách hàng (`tôi tên trung`), nhớ giống thú cưng vừa hỏi để giải quyết đại từ (`con đó`, `nó ăn gì`, `giá giảm không`).
   - Đồng bộ toàn bộ 42 thú cưng/sản phẩm, bảng giá Spa theo cân nặng, mã Voucher & chính sách bảo hành 15 ngày.
"""

import json
import math
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


def _load_local_env():
    """Tự động nạp biến môi trường từ tệp .env cục bộ nếu tồn tại."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


_load_local_env()


# =============================================================================
# 0. TIỆN ÍCH CHUẨN HÓA TIẾNG VIỆT & TIỀN XỬ LÝ NLP
# =============================================================================

DEFAULT_SYNONYMS: Dict[str, str] = {
    "ko": "khong", "k": "khong", "kh": "khong", "hok": "khong", "hem": "khong",
    "bn": "bao nhieu", "bnh": "bao nhieu", "bnhiu": "bao nhieu",
    "tr": "trieu", "cu": "trieu", "dc": "duoc", "dk": "duoc",
    "ntn": "nhu the nao", "ad": "admin", "sd": "su dung",
    "sdt": "so dien thoai", "dt": "dien thoai", "km": "khuyen mai",
    "gg": "giam gia", "ck": "chuyen khoan", "qr": "vietqr",
    "vs": "ve sinh", "bs": "bac si", "aln": "anh long ngan",
    "ald": "anh long dai", "pom": "phoc soc", "pomeranian": "phoc soc",
    "frenchie": "bull phap", "dachshund": "lap xuong",
    "scottish": "tai cup", "persian": "ba tu", "siamese": "xiem",
}


def normalize_vi(text: str) -> str:
    """Chuẩn hóa tiếng Việt về chữ thường không dấu (đ -> d) để khớp cả có dấu và không dấu."""
    if not text:
        return ""
    s = str(text).lower().strip()
    s = s.replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def preprocess_vi_tokens(text: str, synonyms: Optional[Dict[str, str]] = None) -> List[str]:
    """Tách token chuẩn hóa, tách ranh giới số-chữ (`5tr` -> `5`, `trieu`) và mở rộng viết tắt."""
    norm = normalize_vi(text)
    if not norm:
        return []
    norm = re.sub(r"(\d+)([a-z]+)", r"\1 \2", norm)
    syn_map = synonyms if synonyms is not None else DEFAULT_SYNONYMS
    raw_tokens = norm.split()
    expanded: List[str] = []
    for tok in raw_tokens:
        mapped = syn_map.get(tok, tok)
        expanded.extend(mapped.split())
    return expanded


# =============================================================================
# 1. MÔ HÌNH PHÂN LOẠI Ý ĐỊNH NLP (TF-IDF + CHAR N-GRAM COSINE SIMILARITY)
# =============================================================================

class TrainedIntentClassifier:
    """Mô hình phân loại tình huống hội thoại thuần Python dựa trên TF-IDF & Character N-gram."""

    DEFAULT_SCENARIOS_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data",
        "ai_training_scenarios.json",
    )

    def __init__(self, dataset_path: Optional[str] = None):
        self.dataset_path = dataset_path or self.DEFAULT_SCENARIOS_PATH
        self.synonyms: Dict[str, str] = dict(DEFAULT_SYNONYMS)
        self.intents: List[Dict[str, Any]] = []
        self.priorities: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Tuple[str, Dict[str, float], float]] = []
        self.is_trained: bool = False
        self.train()

    FILLER_TOKENS = {
        "shop", "ad", "admin", "oi", "nha", "nhe", "a", "vay", "the",
        "toi", "minh", "ban", "em", "anh", "chi", "giup", "minh",
    }

    def _featurize(self, text: str) -> Counter:
        """Trích xuất đặc trưng kết hợp Word Unigram, Word Bigram và Intra-word Char 3-gram."""
        tokens = preprocess_vi_tokens(text, self.synonyms)
        feats: Counter = Counter()
        for t in tokens:
            w_weight = 0.7 if t in self.FILLER_TOKENS else 2.2
            feats[f"w:{t}"] += w_weight
            if len(t) >= 3 and t not in self.FILLER_TOKENS:
                for i in range(len(t) - 2):
                    feats[f"c3:{t[i:i + 3]}"] += 0.12
        for i in range(len(tokens) - 1):
            feats[f"bg:{tokens[i]}_{tokens[i + 1]}"] += 3.0
        return feats

    def train(self, override_docs: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
        """Nạp tập dữ liệu tình huống và huấn luyện chỉ số TF-IDF + Intent Centroids."""
        self.priorities = {}
        self.doc_vectors = []
        self.centroids: Dict[str, Tuple[Dict[str, float], float]] = {}
        self.idf = {}

        docs: List[Tuple[str, Counter]] = []
        if override_docs is None:
            self.intents = []
            if os.path.exists(self.dataset_path):
                try:
                    with open(self.dataset_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data.get("synonyms"), dict):
                        self.synonyms.update({normalize_vi(k): normalize_vi(v) for k, v in data["synonyms"].items()})
                    self.intents = data.get("intents", [])
                except Exception:
                    self.intents = []

            for item in self.intents:
                tag = str(item.get("tag", "")).strip()
                if not tag:
                    continue
                self.priorities[tag] = int(item.get("priority", 50))
                for pat in item.get("patterns", []):
                    feats = self._featurize(pat)
                    if feats:
                        docs.append((tag, feats))
        else:
            for item in self.intents:
                tag = str(item.get("tag", "")).strip()
                if tag:
                    self.priorities[tag] = int(item.get("priority", 50))
            for tag, pat in override_docs:
                feats = self._featurize(pat)
                if feats:
                    docs.append((tag, feats))

        df: Counter = Counter()
        for _, feats in docs:
            for feat_key in feats.keys():
                df[feat_key] += 1

        total_docs = max(len(docs), 1)
        for feat_key, doc_freq in df.items():
            self.idf[feat_key] = math.log((1.0 + total_docs) / (1.0 + doc_freq)) + 1.0

        centroid_sums: Dict[str, Counter] = {}
        for tag, raw_tf in docs:
            vec: Dict[str, float] = {}
            sq_sum = 0.0
            for k, tf_val in raw_tf.items():
                w = tf_val * self.idf.get(k, 1.0)
                vec[k] = w
                sq_sum += w * w
            norm = math.sqrt(sq_sum) or 1.0
            self.doc_vectors.append((tag, vec, norm))
            csum = centroid_sums.setdefault(tag, Counter())
            for k, w in vec.items():
                csum[k] += w / norm

        for tag, csum in centroid_sums.items():
            c_sq = sum(v * v for v in csum.values())
            c_norm = math.sqrt(c_sq) or 1.0
            self.centroids[tag] = (dict(csum), c_norm)

        self.is_trained = len(self.doc_vectors) > 0
        return {
            "num_intents": len(self.intents),
            "num_patterns": len(self.doc_vectors),
            "vocab_size": len(self.idf),
        }

    def predict(self, query: str) -> Tuple[str, float, Dict[str, float]]:
        """Dự đoán tình huống bằng kết hợp Cosine Similarity (1-NN Pattern + Intent Centroid)."""
        if not self.is_trained or not query or not query.strip():
            return "unknown", 0.0, {}

        raw_tf = self._featurize(query)
        if not raw_tf:
            return "unknown", 0.0, {}

        q_vec: Dict[str, float] = {}
        q_sq = 0.0
        for k, tf_val in raw_tf.items():
            if k in self.idf:
                w = tf_val * self.idf[k]
                q_vec[k] = w
                q_sq += w * w

        if not q_vec:
            return "unknown", 0.0, {}
        q_norm = math.sqrt(q_sq) or 1.0

        max_pattern_sim: Dict[str, float] = {}
        for tag, d_vec, d_norm in self.doc_vectors:
            dot = 0.0
            for k, q_w in q_vec.items():
                d_w = d_vec.get(k)
                if d_w:
                    dot += q_w * d_w
            sim = dot / (q_norm * d_norm)
            if sim > max_pattern_sim.get(tag, 0.0):
                max_pattern_sim[tag] = sim

        intent_scores: Dict[str, float] = {}
        for tag, (c_vec, c_norm) in self.centroids.items():
            cdot = 0.0
            for k, q_w in q_vec.items():
                c_w = c_vec.get(k)
                if c_w:
                    cdot += q_w * c_w
            csim = cdot / (q_norm * c_norm)
            psim = max_pattern_sim.get(tag, 0.0)
            combined = 0.72 * psim + 0.28 * csim
            if combined > 0:
                intent_scores[tag] = round(combined, 4)

        if not intent_scores:
            return "unknown", 0.0, {}

        ranked = sorted(
            intent_scores.items(),
            key=lambda kv: (kv[1], self.priorities.get(kv[0], 50)),
            reverse=True,
        )
        best_tag, best_score = ranked[0]
        return best_tag, best_score, intent_scores


class TrainedCatalogRAGRetriever:
    """
    Bộ tìm kiếm ngữ nghĩa TF-IDF + Coverage trực tiếp trên toàn bộ 42 sản phẩm/thú cưng & Q&A tự dạy.
    Cho phép khách hỏi theo ngoại hình, màu sắc, tính cách, công dụng (`màu trắng`, `bắt chuột`, `mắt xanh`...).
    """

    STOPWORDS = {
        "cho", "meo", "cun", "pet", "thu", "cung", "toi", "minh", "em", "anh", "chi",
        "ban", "shop", "ad", "admin", "muon", "mua", "tim", "xem", "co", "khong",
        "nao", "gi", "gia", "bao", "nhieu", "ben", "cua", "hang", "be", "con",
        "duoc", "nha", "nhe", "a", "oi", "va", "la", "thi", "voi", "ve", "mot",
        "hay", "hoac", "rat", "sieu", "cuc", "ky", "nhat", "the", "vay", "sao",
        "mau", "loai", "giong", "tinh", "cach", "canh", "thuan", "chung", "dep",
        "xinh", "de", "thuong", "dang", "yeu", "ngo", "tot", "cac", "nhung", "chu",
        "tu", "van", "chon", "nuoi", "giup", "hoi", "biet", "coi", "nay", "kia", "do",
    }

    def __init__(self, pets: List[Dict[str, Any]], dataset_path: Optional[str] = None):
        self.pets = pets
        self.dataset_path = dataset_path or TrainedIntentClassifier.DEFAULT_SCENARIOS_PATH
        self.custom_qas: List[Dict[str, Any]] = []
        self.idf: Dict[str, float] = {}
        self.pet_docs: List[Tuple[Dict[str, Any], set, set, Dict[str, float], float]] = []
        self.qa_docs: List[Tuple[Dict[str, Any], set, set, Dict[str, float], float]] = []
        self._build_index()

    def _tokenize_content(self, text: str) -> Tuple[List[str], List[str]]:
        tokens = [t for t in preprocess_vi_tokens(text) if t not in self.STOPWORDS and len(t) >= 2]
        bigrams = [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
        return tokens, bigrams

    def _content_feats(self, text: str) -> Tuple[Counter, set, set]:
        tokens, bigrams = self._tokenize_content(text)
        feats: Counter = Counter()
        for t in tokens:
            feats[f"w:{t}"] += 1.0
        for bg in bigrams:
            feats[f"bg:{bg}"] += 1.5
        return feats, set(tokens), set(bigrams)

    def _load_custom_qas(self):
        self.custom_qas = []
        if self.dataset_path and os.path.exists(self.dataset_path):
            try:
                with open(self.dataset_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                qas = data.get("custom_qas", [])
                if isinstance(qas, list):
                    self.custom_qas = [q for q in qas if isinstance(q, dict) and q.get("answer")]
            except Exception:
                pass

    def _build_index(self):
        self._load_custom_qas()
        raw_pet_docs: List[Tuple[Dict[str, Any], Counter, set, set]] = []
        raw_qa_docs: List[Tuple[Dict[str, Any], Counter, set, set]] = []
        df: Counter = Counter()

        for p in self.pets:
            doc_text = f"{p.get('name', '')} {p.get('breed', '')} {p.get('category', '')} {p.get('description', '')}"
            feats, tok_set, bg_set = self._content_feats(doc_text)
            if feats:
                raw_pet_docs.append((p, feats, tok_set, bg_set))
                for k in feats:
                    df[k] += 1

        for qa in self.custom_qas:
            q_text = " ".join(qa.get("patterns", [])) + " " + str(qa.get("question", ""))
            feats, tok_set, bg_set = self._content_feats(q_text)
            if feats:
                raw_qa_docs.append((qa, feats, tok_set, bg_set))
                for k in feats:
                    df[k] += 1

        total = max(len(raw_pet_docs) + len(raw_qa_docs), 1)
        self.default_idf = math.log(1.0 + total) + 1.0
        for k, freq in df.items():
            self.idf[k] = math.log((1.0 + total) / (1.0 + freq)) + 1.0

        def _vec(feats: Counter) -> Tuple[Dict[str, float], float]:
            v: Dict[str, float] = {}
            sq = 0.0
            for k, tf_val in feats.items():
                w = (1.0 + math.log(tf_val)) * self.idf.get(k, 1.0)
                v[k] = w
                sq += w * w
            return v, (math.sqrt(sq) or 1.0)

        self.pet_docs = [(p, tok_set, bg_set, *_vec(feats)) for p, feats, tok_set, bg_set in raw_pet_docs]
        self.qa_docs = [(qa, tok_set, bg_set, *_vec(feats)) for qa, feats, tok_set, bg_set in raw_qa_docs]

    def _score_query_against_doc(
        self,
        q_tok_set: set,
        q_bg_set: set,
        q_vec: Dict[str, float],
        q_norm: float,
        doc_tok_set: set,
        doc_bg_set: set,
        d_vec: Dict[str, float],
        d_norm: float,
    ) -> float:
        if not q_tok_set:
            return 0.0
        total_q_idf = sum(self.idf.get(f"w:{t}", self.default_idf) for t in q_tok_set) or 1.0
        matched_q_idf = sum(self.idf.get(f"w:{t}", self.default_idf) for t in (q_tok_set & doc_tok_set))
        if matched_q_idf <= 0.0:
            return 0.0
        coverage = matched_q_idf / total_q_idf
        cos_sim = 0.0
        if q_vec:
            dot = sum(q_w * d_vec.get(k, 0.0) for k, q_w in q_vec.items())
            cos_sim = dot / (q_norm * d_norm)
        bg_hits = len(q_bg_set & doc_bg_set)
        bg_bonus = min(0.18, 0.09 * bg_hits)
        return round(0.65 * coverage + 0.35 * cos_sim + bg_bonus, 4)

    def _build_query_vec(self, feats: Counter) -> Tuple[Dict[str, float], float]:
        q_vec: Dict[str, float] = {}
        q_sq = 0.0
        for k, tf_val in feats.items():
            if k in self.idf:
                w = (1.0 + math.log(tf_val)) * self.idf[k]
                q_vec[k] = w
                q_sq += w * w
        return q_vec, (math.sqrt(q_sq) or 1.0)

    def search_custom_qa(self, query: str) -> Tuple[Optional[Dict[str, Any]], float]:
        if not self.qa_docs:
            return None, 0.0
        # Đối với Q&A tự dạy giữ lại cả 'cho', 'meo' để khớp chính xác câu hỏi đã dạy
        raw_toks = [t for t in preprocess_vi_tokens(query) if len(t) >= 2 and t not in {"toi", "minh", "em", "anh", "chi", "ban", "shop", "ad", "oi", "nha", "nhe", "a"}]
        raw_bgs = [f"{raw_toks[i]}_{raw_toks[i + 1]}" for i in range(len(raw_toks) - 1)]
        feats: Counter = Counter()
        for t in raw_toks:
            feats[f"w:{t}"] += 1.0
        for bg in raw_bgs:
            feats[f"bg:{bg}"] += 1.5
        if not raw_toks:
            return None, 0.0
        q_vec, q_norm = self._build_query_vec(feats)
        q_tok_set, q_bg_set = set(raw_toks), set(raw_bgs)

        best_qa, best_sim = None, 0.0
        for qa, d_tok_set, d_bg_set, d_vec, d_norm in self.qa_docs:
            qa_text = " ".join(qa.get("patterns", [])) + " " + str(qa.get("question", ""))
            qa_raw_toks = {t for t in preprocess_vi_tokens(qa_text) if len(t) >= 2}
            combined_tok_set = d_tok_set | qa_raw_toks
            sim = self._score_query_against_doc(
                q_tok_set, q_bg_set, q_vec, q_norm,
                combined_tok_set, d_bg_set, d_vec, d_norm,
            )
            if sim > best_sim:
                best_sim = sim
                best_qa = qa
        return best_qa, best_sim

    def retrieve_pets(
        self,
        query: str,
        pet_type_filter: Optional[str] = None,
        top_k: int = 4,
    ) -> List[Tuple[Dict[str, Any], float]]:
        feats, q_tok_set, q_bg_set = self._content_feats(query)
        if not q_tok_set:
            return []
        q_vec, q_norm = self._build_query_vec(feats)

        scored: List[Tuple[Dict[str, Any], float]] = []
        for p, d_tok_set, d_bg_set, d_vec, d_norm in self.pet_docs:
            if pet_type_filter in ("Chó", "Mèo"):
                if p.get("pet_type") != pet_type_filter and "Chó & Mèo" not in str(p.get("pet_type", "")):
                    continue
            sim = self._score_query_against_doc(
                q_tok_set, q_bg_set, q_vec, q_norm,
                d_tok_set, d_bg_set, d_vec, d_norm,
            )
            if sim > 0:
                scored.append((p, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


# =============================================================================
# 2. KNOWLEDGE BASE RAG (TRÍCH XUẤT TOÀN BỘ DỮ LIỆU THỰC TẾ CỦA CỬA HÀNG)
# =============================================================================

class PetShopKnowledgeBase:
    """Kho tri thức tổng hợp toàn bộ sản phẩm, dịch vụ, voucher và chính sách Meow & Woof."""

    def __init__(self):
        self.pets: List[Dict[str, Any]] = []
        self.spa_services: Dict[str, float] = {}
        self.vouchers: List[Dict[str, Any]] = []
        self.policies: Dict[str, str] = {}
        self.membership_tiers: List[Dict[str, Any]] = []
        self.shop_info: Dict[str, str] = {}
        self._load_knowledge()

    def _load_knowledge(self):
        self.shop_info = {
            "name": "Meow & Woof Pet House & Spa Chó Mèo",
            "hotline": "0905.123.456",
            "email": "trungvt040106@gmail.com",
            "address": "245 Nguyễn Thị Minh Khai, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh",
            "hours": "08:00 - 21:00 (Tất cả các ngày trong tuần kể cả Thứ 7, Chủ Nhật và ngày Lễ)",
            "website": "https://chomeo.vercel.app",
        }

        self.spa_services = {
            "Tắm sấy & Vệ sinh tai móng": 150000.0,
            "Cắt tỉa & Tạo kiểu lông (Grooming)": 280000.0,
            "Cạo lông máu / Cạo vệ sinh": 180000.0,
            "Trông giữ thú cưng (1 ngày)": 200000.0,
            "Khám sức khỏe & Tư vấn dinh dưỡng": 120000.0,
        }

        self.vouchers = self._load_live_vouchers()

        self.membership_tiers = [
            {"tier": "Thành Viên Mới", "min_spend": 0, "benefit": "Gia nhập hệ thống & Tư vấn dinh dưỡng miễn phí"},
            {"tier": "Hạng Bạc (Silver)", "min_spend": 1000000, "benefit": "Giảm 5% dịch vụ Tắm sấy Spa & Phụ kiện"},
            {"tier": "Hạng Vàng (Gold)", "min_spend": 5000000, "benefit": "Giảm 10% dịch vụ Cắt tỉa Spa & Phụ kiện"},
            {"tier": "Hạng Kim Cương (Diamond)", "min_spend": 15000000, "benefit": "Giảm 15% tất cả đơn hàng & dịch vụ Spa + Đưa đón tận nhà"},
        ]

        self.policies = {
            "warranty": "Bảo hành sức khỏe thuần chủng 15 ngày toàn diện đối với 2 bệnh nguy hiểm Parvo và Care. Đổi trả 1-1 nếu phát hiện lỗi di truyền.",
            "vaccination": "100% Chó Mèo bán ra đều đã được tiêm phòng ít nhất 1-2 mũi vắc xin và tẩy giun định kỳ, kèm sổ theo dõi sức khỏe thú y chuẩn.",
            "shipping": "Giao hỏa tốc 2 giờ tại khu vực TP.HCM bằng xe điều hòa. Giao an toàn toàn quốc (Hà Nội, Đà Nẵng, Cần Thơ...) có nhân viên/thú y chăm sóc suốt hành trình.",
            "payment": "Hỗ trợ thanh toán linh hoạt: Chuyển khoản ngân hàng VietQR 24/7 (tự động tạo mã QR chuẩn xác từng đồng, MB Bank 0905123456) hoặc Trả tiền mặt khi nhận hàng (COD).",
        }

        try:
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            seeds_path = os.path.join(cur_dir, "data", "seeds.py")
            if os.path.exists(seeds_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("seeds_module", seeds_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self.pets = getattr(mod, "SEED_CATALOG", [])
        except Exception:
            pass

        if not self.pets:
            self._load_fallback_pets()

    def _load_live_vouchers(self) -> List[Dict[str, Any]]:
        """Đồng bộ Voucher thực tế đang hoạt động từ `data/vouchers_store.json` hoặc cấu hình chuẩn."""
        defaults = [
            {
                "code": "GENZVIP20",
                "discount_pct": 20,
                "min_order": 100000,
                "max_discount": 500000,
                "desc": "Giảm 20% toàn bộ đơn hàng & Spa (đơn từ 100,000 đ, tối đa 500,000 đ)",
            },
            {
                "code": "MEOW50K",
                "discount_pct": 0,
                "discount_fixed": 50000,
                "min_order": 200000,
                "desc": "Giảm thẳng 50,000 đ cho đơn hàng từ 200,000 đ",
            },
            {
                "code": "FREESHIP30K",
                "discount_pct": 0,
                "discount_fixed": 30000,
                "min_order": 0,
                "desc": "Trợ giá vận chuyển 30,000 đ cho mọi đơn hàng",
            },
        ]
        v_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vouchers_store.json")
        if not os.path.exists(v_path):
            return defaults
        try:
            with open(v_path, "r", encoding="utf-8") as f:
                rows = json.load(f)
            if not isinstance(rows, list):
                return defaults
            loaded: List[Dict[str, Any]] = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                code = str(r.get("code", "")).strip().upper()
                if not code or not r.get("is_active", 1) or "TEST" in code:
                    continue
                dtype = r.get("discount_type", "fixed")
                dval = float(r.get("discount_value", 0) or 0)
                min_ord = float(r.get("min_order_value", 0) or 0)
                max_disc = float(r.get("max_discount", 0) or 0)
                title = str(r.get("title", "")).strip()
                loaded.append({
                    "code": code,
                    "discount_pct": int(dval) if dtype == "percent" else 0,
                    "discount_fixed": int(dval) if dtype == "fixed" else 0,
                    "min_order": int(min_ord),
                    "max_discount": int(max_disc),
                    "desc": title or (f"Giảm {int(dval)}%" if dtype == "percent" else f"Giảm {int(dval):,} đ"),
                })
            return loaded if loaded else defaults
        except Exception:
            return defaults

    def _load_fallback_pets(self):
        self.pets = [
            {"sku": "DOG-PET-001", "name": "Chó Schnauzer Tiêu Muối Thuần Chủng (2.5 tháng)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Schnauzer", "price": 6500000, "stock": 3, "description": "Lông xù hai màu tiêu muối, thông minh, lanh lợi, không rụng lông."},
            {"sku": "DOG-PET-002", "name": "Chó Poodle Tiny Màu Nâu Đỏ (2 tháng tuổi)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Poodle", "price": 4800000, "stock": 4, "description": "Poodle Tiny siêu quấn chủ, không rụng lông, rất hợp nuôi chung cư."},
            {"sku": "DOG-PET-003", "name": "Chó Corgi Pembroke Chân Lùn Vàng Trắng", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Corgi Chân Lùn", "price": 7900000, "stock": 2, "description": "Mông trái tim siêu cưng, chân lùn đáng yêu, thích hợp gia đình có trẻ em."},
            {"sku": "DOG-PET-004", "name": "Chó Phốc Sóc Pomeranian Mặt Gấu Trắng Tuyết", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Phốc Sóc (Pomeranian)", "price": 7200000, "stock": 3, "description": "Bộ lông trắng bông xù như cục bông tuyết, mặt gấu ngây thơ."},
            {"sku": "DOG-PET-005", "name": "Chó Golden Retriever Thuần Chủng (2.5 tháng)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Golden Retriever", "price": 6200000, "stock": 3, "description": "Thân thiện, hiền lành, thông minh, bạn đồng hành tuyệt vời của trẻ nhỏ."},
            {"sku": "DOG-PET-006", "name": "Chó Shiba Inu Vàng Đỏ Chuẩn Form Nhật", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Shiba Inu", "price": 9500000, "stock": 2, "description": "Quốc khuyển Nhật Bản mặt cười, sạch sẽ, trung thành tuyệt đối."},
            {"sku": "DOG-PET-014", "name": "Chó Pug Mặt Xệ Màu Vàng Kim (2 tháng tuổi)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Pug Mặt Xệ", "price": 4500000, "stock": 4, "description": "Pug mặt xệ ngộ nghĩnh, hiền lành, ít sủa, cực kỳ thích hợp nuôi chung cư."},
            {"sku": "CAT-PET-001", "name": "Mèo Anh Lông Ngắn Màu Xám Xanh (British Shorthair)", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Anh Lông Ngắn (ALN)", "price": 4500000, "stock": 4, "description": "Má phúng phính, lông dày mượt, điềm tĩnh, ngoan ngoãn và sạch sẽ."},
            {"sku": "CAT-PET-004", "name": "Mèo Ragdoll Mắt Xanh Ngọc Bích", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Ragdoll", "price": 7500000, "stock": 2, "description": "Công chúa mèo lông dài óng mượt, mắt xanh ngọc bích, hiền lành dịu dàng."},
        ]

    @staticmethod
    def calculate_spa_price(service_name: str, weight_kg: float, base_services: Dict[str, float]) -> Tuple[float, float]:
        """Tính đúng phụ phí cân nặng giống hệ thống đặt lịch `/spa` (<5kg x1.0, 5-10kg x1.2, >10kg x1.4)."""
        base = float(base_services.get(service_name, 150000.0))
        if weight_kg > 10:
            mult = 1.4
        elif weight_kg >= 5:
            mult = 1.2
        else:
            mult = 1.0
        return round(base * mult, 0), mult

    def search_pets(
        self,
        keyword: str = "",
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        category: Optional[str] = None,
        pets_only: bool = False,
    ) -> List[Dict[str, Any]]:
        kw = normalize_vi(keyword)
        cat_norm = normalize_vi(category or "")
        results = []
        for p in self.pets:
            name = normalize_vi(str(p.get("name", "")))
            breed = normalize_vi(str(p.get("breed", "")))
            cat = normalize_vi(str(p.get("category", "")))
            ptype = normalize_vi(str(p.get("pet_type", "")))
            desc = normalize_vi(str(p.get("description", "")))
            p_price = float(p.get("price", 0) or 0)

            if pets_only and p.get("category") not in ("Chó cảnh", "Mèo cảnh"):
                continue
            if max_price is not None and p_price > max_price:
                continue
            if min_price is not None and p_price < min_price:
                continue
            if cat_norm and (cat_norm not in cat) and (cat_norm not in ptype):
                continue
            if kw and (kw not in name) and (kw not in breed) and (kw not in cat) and (kw not in desc):
                continue
            results.append(p)
        return results

    def build_full_system_context(self) -> str:
        """Tạo ngữ cảnh đầy đủ toàn bộ cửa hàng để nạp vào System Instruction của Gemini."""
        lines = [
            f"Tên cửa hàng: {self.shop_info['name']}",
            f"Địa chỉ: {self.shop_info['address']}",
            f"Giờ mở cửa: {self.shop_info['hours']}",
            f"Hotline / Zalo: {self.shop_info['hotline']} | Email: {self.shop_info['email']}",
            f"Website: {self.shop_info['website']}",
            f"Chính sách bảo hành: {self.policies['warranty']}",
            f"Tiêm phòng: {self.policies['vaccination']}",
            f"Giao hàng: {self.policies['shipping']}",
            f"Thanh toán: {self.policies['payment']}",
            "\n--- BẢNG GIÁ DỊCH VỤ SPA & GROOMING (Dưới 5kg: giá gốc | 5-10kg: +20% | Trên 10kg: +40%) ---",
        ]
        for s_name, s_price in self.spa_services.items():
            lines.append(f"• {s_name}: {int(s_price):,} đ")

        lines.append("\n--- MÃ GIẢM GIÁ VOUCHER ĐANG HOẠT ĐỘNG ---")
        for v in self.vouchers:
            lines.append(f"• Mã {v['code']}: {v['desc']}")

        lines.append("\n--- HẠNG THÀNH VIÊN VIP ---")
        for t in self.membership_tiers:
            lines.append(f"• {t['tier']} (từ {int(t['min_spend']):,} đ): {t['benefit']}")

        lines.append("\n--- DANH SÁCH TOÀN BỘ SẢN PHẨM & THÚ CƯNG HIỆN CÓ ---")
        for p in self.pets:
            lines.append(
                f"• [{p.get('sku', '')}] {p.get('name', '')} | Phân loại: {p.get('category', '')} "
                f"| Giá: {int(p.get('price', 0)):,} đ | Tồn kho: {p.get('stock', 1)} "
                f"| Mô tả: {p.get('description', '')}"
            )

        sc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ai_training_scenarios.json")
        if os.path.exists(sc_path):
            try:
                with open(sc_path, "r", encoding="utf-8") as f:
                    qas = json.load(f).get("custom_qas", [])
                if qas:
                    lines.append("\n--- KIẾN THỨC BỔ SUNG TỪ HUẤN LUYỆN CỬA HÀNG ---")
                    for qa in qas:
                        if isinstance(qa, dict) and qa.get("question") and qa.get("answer"):
                            lines.append(f"• Hỏi: {qa['question']} => Đáp: {qa['answer']}")
            except Exception:
                pass
        return "\n".join(lines)


# =============================================================================
# 3. BỘ ĐIỀU PHỐI MÔ HÌNH GEMINI 3.8 FLASH + PLAYBOOK XỬ LÝ TÌNH HUỐNG
# =============================================================================

class GeminiFlashAdvisor:
    """Tích hợp mô hình Google Gemini 3.8 Flash qua REST API bằng urllib."""

    PRIMARY_MODEL = "gemini-3.8-flash"
    FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-3.1-flash-lite"]

    def __init__(self, api_key: Optional[str] = None):
        _load_local_env()
        raw_key = api_key or os.environ.get("GEMINI_API_KEY") or ""
        self.api_key = raw_key.rstrip("|").strip()
        self.model = self.PRIMARY_MODEL

    def set_api_key(self, key: str):
        self.api_key = key.rstrip("|").strip()

    def generate(
        self,
        user_query: str,
        system_context: str,
        history: Optional[List[Dict[str, str]]] = None,
        situation_hint: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        """Gọi API Gemini 3.8 Flash kèm Playbook xử lý tình huống & ngữ cảnh hội thoại."""
        if not self.api_key:
            return None, "Chưa cấu hình Gemini API Key"

        playbook = (
            "PLAYBOOK XỬ LÝ TÌNH HUỐNG MƯỢT MÀ:\n"
            "- Khách xưng tên (VD 'tôi tên Trung'): Chào đúng tên khách thân mật, nhớ tên ở các câu sau.\n"
            "- Khách khiếu nại / bực mình / giao chậm / lỗi: Xin lỗi chân thành ngay, đồng cảm, không đổ lỗi, "
            "hướng dẫn xử lý ngay và cung cấp Hotline 0905.123.456 + Email trungvt040106@gmail.com.\n"
            "- Khách mặc cả / chê đắt: Khéo léo nêu giá trị (thuần chủng, tiêm đủ mũi, sổ thú y, bảo hành 15 ngày Parvo/Care) "
            "và chủ động gợi ý ngay mã giảm giá GENZVIP20 (giảm 20% tối đa 500K), MEOW50K, FREESHIP30K.\n"
            "- Thú cưng bị ốm / tiêu chảy / nôn / bỏ ăn / ve rận: Hướng dẫn sơ cứu an toàn (bù nước, giữ ấm, cách ly, không cho ăn đồ lạ), "
            "nhắc bảo hành 15 ngày nếu mới đón về, gợi ý sản phẩm y tế phù hợp trong shop (Nutri-Plus Gel / Frontline Plus) và khuyên đi thú y ngay.\n"
            "- Đại từ nối tiếp ('con đó', 'nó ăn gì', 'giá giảm không'): Dựa vào lịch sử hội thoại trước đó để trả lời liền mạch.\n"
            "- Câu hỏi ngoài lề / tán gẫu: Đáp duyên dáng, hài hước 1 câu rồi kéo khéo về chủ đề chăm sóc thú cưng.\n"
            "- Tuyệt đối chỉ sử dụng giá, SKU, Voucher và chính sách có trong DỮ LIỆU CỬA HÀNG bên dưới."
        )

        hint_block = f"\n[PHÂN TÍCH NGỮ CẢNH HIỆN TẠI]: {situation_hint}" if situation_hint else ""
        system_instruction = (
            "Bạn là Trợ lý AI tư vấn khách hàng chính thức của cửa hàng thú cưng Meow & Woof Pet House.\n"
            "Hãy trả lời TRỰC TIẾP, TỰ NHIÊN, ẤM ÁP, NGẮN GỌN và CHÍNH XÁC 100% bằng tiếng Việt.\n"
            "Trình bày gọn gàng (dùng gạch đầu dòng ngắn gọn, in đậm **tên/giá tiền**, dùng backtick cho `SKU` / `MÃ VOUCHER`).\n\n"
            f"{playbook}{hint_block}\n\n"
            f"=== DỮ LIỆU CỬA HÀNG ===\n{system_context}"
        )

        contents = []
        if history:
            for turn in history[-8:]:
                role = "model" if turn.get("role") == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": turn.get("content", "")}],
                })

        contents.append({
            "role": "user",
            "parts": [{"text": user_query}],
        })

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.45,
                "topP": 0.9,
                "maxOutputTokens": 650,
            },
        }
        req_bytes = json.dumps(payload).encode("utf-8")

        last_err = ""
        timeouts = {"gemini-3.8-flash": 2.2, "gemini-3-flash-preview": 4.5, "gemini-3.1-flash-lite": 2.0}
        for model_name in self.FALLBACK_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={urllib.parse.quote(self.api_key)}"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "MeowWoof-GeminiAdvisor/3.8",
            }
            timeout_sec = timeouts.get(model_name, 3.5)
            try:
                req = urllib.request.Request(url, data=req_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                    resp_json = json.loads(response.read().decode("utf-8"))
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip(), model_name
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                continue
            except Exception as e:
                last_err = str(e)
                continue

        return None, f"{last_err or 'Offline'}"


# =============================================================================
# 4. BỘ NÃO TÌNH HUỐNG HUẤN LUYỆN CHUYÊN SÂU (TRAINED SCENARIO & MEMORY ENGINE)
# =============================================================================

class SmartSemanticFallbackAdvisor:
    """
    Bộ não xử lý tình huống kết hợp:
    - Mô hình học máy `TrainedIntentClassifier` (huấn luyện từ `ai_training_scenarios.json`)
    - Bộ trích xuất thực thể tiếng Việt (giống chó/mèo, sản phẩm, cân nặng kg, khoảng giá, tên khách)
    - Bộ nhớ hội thoại đa lượt (`history`) giải quyết đại từ (`con đó`, `nó ăn gì`, `giảm thêm không`)
    """

    BREED_ALIASES: List[Tuple[str, List[str]]] = [
        ("DOG-PET-001", ["schnauzer", "tieu muoi"]),
        ("DOG-PET-002", ["poodle", "tiny", "teacup"]),
        ("DOG-PET-003", ["corgi", "pembroke", "chan lun", "mong trai tim"]),
        ("DOG-PET-004", ["phoc soc", "pomeranian", "pom", "mat gau trang tuyet"]),
        ("DOG-PET-005", ["golden", "retriever"]),
        ("DOG-PET-006", ["shiba", "shiba inu"]),
        ("DOG-PET-007", ["chihuahua"]),
        ("DOG-PET-008", ["labrador"]),
        ("DOG-PET-009", ["alaska", "malamute", "giant"]),
        ("DOG-PET-010", ["husky", "sibir"]),
        ("DOG-PET-011", ["akita"]),
        ("DOG-PET-012", ["samoyed", "cuoi thien than"]),
        ("DOG-PET-013", ["chow chow", "su tu xu"]),
        ("DOG-PET-014", ["pug", "mat xe"]),
        ("DOG-PET-015", ["bull phap", "french bulldog", "frenchie"]),
        ("DOG-PET-016", ["phu quoc", "xoay lung"]),
        ("DOG-PET-017", ["becgie", "german shepherd"]),
        ("DOG-PET-018", ["beagle", "san tho"]),
        ("DOG-PET-019", ["bichon", "bichon frise"]),
        ("DOG-PET-020", ["lap xuong", "dachshund", "cho xuc xich"]),
        ("CAT-PET-001", ["meo anh long ngan", "anh long ngan", "aln", "british shorthair", "meo xam xanh"]),
        ("CAT-PET-002", ["tai cup", "scottish fold", "scottish"]),
        ("CAT-PET-003", ["munchkin", "meo chan ngan"]),
        ("CAT-PET-004", ["ragdoll", "ngoc bich"]),
        ("CAT-PET-005", ["meo anh long dai", "anh long dai", "ald"]),
        ("CAT-PET-006", ["ba tu", "persian", "mat tit"]),
        ("CAT-PET-007", ["bengal", "van bao"]),
        ("CAT-PET-008", ["maine coon", "rung na uy"]),
        ("CAT-PET-009", ["meo xiem", "siamese", "xiem"]),
        ("CAT-PET-010", ["nga mat xanh", "russian blue"]),
        ("CAT-PET-011", ["sphynx", "meo khong long", "khong long ai cap"]),
        ("CAT-PET-012", ["meo my long ngan", "my long ngan", "american shorthair", "tabby"]),
    ]

    SUPPLY_ALIASES: List[Tuple[str, List[str]]] = [
        ("CAT-FD-001", ["royal canin", "indoor 27", "hat cho meo"]),
        ("CAT-FD-002", ["ciao churu", "ciao", "churu", "sup thuong", "pate meo", "pate"]),
        ("DOG-FD-001", ["smartheart", "hat cho cho", "vi bo nuong"]),
        ("CAT-SAN-001", ["cat dau nanh", "tofu", "cat meo", "cat ve sinh"]),
        ("PET-ACC-001", ["balo", "phi hanh gia", "tui van chuyen"]),
        ("PET-CARE-001", ["sua tam", "sos"]),
        ("CAT-TOY-001", ["tru cao mong", "sisal", "ban cao mong"]),
        ("DOG-TOY-001", ["xuong cao su", "xuong gam"]),
        ("PET-MED-001", ["nutri plus", "virbac", "gel dinh duong"]),
        ("PET-MED-002", ["frontline", "nho gay", "ve ran", "bo chet"]),
    ]

    NON_NAME_WORDS = {
        "khach", "sinh", "nguoi", "ban", "shop", "admin", "ad", "cho", "meo",
        "fan", "nam", "nu", "ai", "gi", "moi", "cu", "thanh", "hcm",
        "ha", "da", "can", "khachhang", "member",
    }

    NAME_TRAILING_STOPWORDS = {"nhe", "nha", "a", "oi", "day", "ne", "ah", "ak", "vua", "xong"}

    COREF_PATTERNS = [
        r"\bcon do\b", r"\bbe do\b", r"\bem do\b", r"\bgiong do\b",
        r"\bcon nay\b", r"\bbe nay\b", r"\bem nay\b", r"\bgiong nay\b",
        r"\bcon ay\b", r"\bbe ay\b", r"\bno\b", r"\bchung no\b",
    ]

    def __init__(self, kb: PetShopKnowledgeBase, classifier: Optional[TrainedIntentClassifier] = None):
        self.kb = kb
        self.classifier = classifier or TrainedIntentClassifier()
        self.sku_map: Dict[str, Dict[str, Any]] = {
            str(p.get("sku", "")): p for p in self.kb.pets if p.get("sku")
        }
        self.rag = TrainedCatalogRAGRetriever(
            self.kb.pets,
            dataset_path=self.classifier.dataset_path,
        )

    # ------------------------------------------------------------------
    # Trích xuất thực thể & Bộ nhớ hội thoại
    # ------------------------------------------------------------------

    def _extract_person_name(self, raw_text: str) -> Optional[str]:
        if not raw_text:
            return None
        patterns = [
            r"(?:tôi|mình|em|anh|chị|tui|tao)\s+(?:tên|tên\s+là)\s+([a-zA-ZÀ-ỹ0-9_]+(?:\s+[a-zA-ZÀ-ỹ0-9_]+){0,2})",
            r"(?:toi|minh|em|anh|chi|tui)\s+(?:ten|ten\s+la)\s+([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+){0,2})",
            r"tên\s+(?:tôi|mình|em|anh|chị)\s+là\s+([a-zA-ZÀ-ỹ0-9_]+(?:\s+[a-zA-ZÀ-ỹ0-9_]+){0,2})",
            r"gọi\s+(?:tôi|mình|em|anh|chị)\s+là\s+([a-zA-ZÀ-ỹ0-9_]+(?:\s+[a-zA-ZÀ-ỹ0-9_]+){0,1})",
            r"(?:tôi|mình|em)\s+là\s+([a-zA-ZÀ-ỹ]+)\b",
        ]
        for pat in patterns:
            m = re.search(pat, raw_text.strip(), flags=re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                parts = [w for w in candidate.split() if normalize_vi(w) not in self.NAME_TRAILING_STOPWORDS]
                if not parts:
                    continue
                first_norm = normalize_vi(parts[0])
                if first_norm in self.NON_NAME_WORDS:
                    continue
                clean_words = []
                for w in parts:
                    wn = normalize_vi(w)
                    if wn in {"muon", "can", "tim", "hoi", "mua", "dat", "xem", "bao", "o", "cho", "co", "tu"}:
                        break
                    clean_words.append(w.capitalize())
                if clean_words:
                    return " ".join(clean_words)
        return None

    def _is_pure_name_intro(self, raw_text: str, extracted_name: Optional[str]) -> bool:
        """Kiểm tra khách chỉ đơn thuần giới thiệu tên hay có hỏi thêm thông tin trong cùng câu."""
        if not extracted_name:
            return False
        norm = normalize_vi(raw_text)
        name_norm = normalize_vi(extracted_name)
        cleaned = re.sub(
            r"\b(?:chao|xin chao|hi|hello|alo|shop|ad|admin|toi|minh|em|anh|chi|tui|ten|la|goi|day|nhe|nha|a|oi|ne|vui|lam|quen)\b",
            " ",
            norm,
        )
        if name_norm:
            cleaned = cleaned.replace(name_norm, " ")
        remaining_tokens = [t for t in cleaned.split() if len(t) > 0]
        return len(remaining_tokens) <= 1

    def _find_items_by_alias(self, text: str, aliases: List[Tuple[str, List[str]]]) -> List[Dict[str, Any]]:
        norm = " " + normalize_vi(text) + " "
        found: List[Dict[str, Any]] = []
        seen_skus = set()
        for sku, kws in aliases:
            for kw in kws:
                kw_n = normalize_vi(kw)
                if not kw_n:
                    continue
                if re.search(r"(?:^|\s)" + re.escape(kw_n) + r"(?:\s|$)", norm):
                    pet = self.sku_map.get(sku)
                    if pet and sku not in seen_skus:
                        found.append(pet)
                        seen_skus.add(sku)
                    break
        return found

    def _extract_weight_kg(self, text: str) -> Optional[float]:
        norm = normalize_vi(text)
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|ky|can)\b", norm)
        if m:
            try:
                val = float(m.group(1))
                if 0.2 <= val <= 100:
                    return val
            except ValueError:
                pass
        return None

    def _extract_price_filter(self, text: str) -> Optional[Tuple[Optional[float], Optional[float], str]]:
        norm = normalize_vi(text)
        m_between = re.search(r"(?:tu|khoang)\s*(\d+(?:\.\d+)?)\s*(?:den|-|toi)\s*(\d+(?:\.\d+)?)\s*(tr|trieu|cu|k)\b", norm)
        if m_between:
            v1, v2, unit = float(m_between.group(1)), float(m_between.group(2)), m_between.group(3)
            mult = 1000000.0 if unit in {"tr", "trieu", "cu"} else 1000.0
            lo, hi = min(v1, v2) * mult, max(v1, v2) * mult
            return lo, hi, f"từ **{int(lo):,} đ** đến **{int(hi):,} đ**"

        m_under = re.search(r"(duoi|<|tam|khoang|toi da|ngan sach)\s*(\d+(?:\.\d+)?)\s*(tr|trieu|cu|k)\b", norm)
        if m_under:
            op = m_under.group(1)
            val = float(m_under.group(2))
            unit = m_under.group(3)
            mult = 1000000.0 if unit in {"tr", "trieu", "cu"} else 1000.0
            amt = val * mult
            if op in {"tam", "khoang"}:
                lo, hi = max(0.0, amt * 0.78), amt * 1.25
                return lo, hi, f"tầm **{int(amt):,} đ**"
            return None, amt, f"dưới **{int(amt):,} đ**"

        m_over = re.search(r"(tren|>|tu)\s*(\d+(?:\.\d+)?)\s*(tr|trieu|cu|k)\b", norm)
        if m_over:
            val = float(m_over.group(2))
            unit = m_over.group(3)
            mult = 1000000.0 if unit in {"tr", "trieu", "cu"} else 1000.0
            amt = val * mult
            return amt, None, f"từ **{int(amt):,} đ** trở lên"

        return None

    def _has_coref_pronoun(self, text: str) -> bool:
        norm = normalize_vi(text)
        return any(re.search(pat, norm) for pat in self.COREF_PATTERNS)

    def _detect_pet_type_intent(self, raw_q: str, norm_q: str) -> Optional[str]:
        """Phân biệt chính xác khách hỏi Chó hay Mèo (tránh nhầm từ 'cho' trong 'cho mình xem mèo')."""
        low = str(raw_q or "").lower()
        has_dog = bool(re.search(r"\b(?:chó|cún|cậu vàng)\b", low))
        has_cat = bool(re.search(r"\b(?:mèo|hoàng thượng|boss mèo)\b", low))

        if not has_cat and re.search(r"\bmeo\b", norm_q):
            has_cat = True

        if not has_dog:
            if re.search(r"\bcun\b", norm_q):
                has_dog = True
            else:
                prep_guard = r"(?!\s*(?:minh|toi|em|anh|chi|ban|khach|nha|nguoi|ai|biet|xem|hoi|thay|meo|be|con|cun|no|chung|an|uong|tam|ngu|lam|duoc))"
                has_vi_accents = bool(re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", low))
                if re.search(rf"\b(?:giong|mua|tim|ban|nuoi|con|be|em|thich|gia|tam)\s+cho\b{prep_guard}", norm_q):
                    has_dog = True
                elif not has_vi_accents and re.search(r"\bcho\s+(?:duoi|tren|tam|khoang|gia|mau|long|chan|tai|mat|nao|de|khon|re|dat|dep|xinh|nho|to|con|canh|hay|khong|meo)\b", norm_q):
                    if not re.search(r"\b(?:hat|thuc an|pate|cat|sua tam|do choi|phu kien|thuoc|tam|cat tia|tiem|tay giun|triet san|dat ten|danh|gui|kham)\s+cho\s+meo\b", norm_q):
                        has_dog = True
                elif re.search(r"\bcho\s+(?:va|hay)\s+meo\b", norm_q):
                    has_dog = True

        if has_dog and has_cat:
            return "BOTH"
        if has_dog:
            return "Chó"
        if has_cat:
            return "Mèo"
        return None

    def _compatible_context_pet(self, raw_q: str, norm_q: str, last_pet: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Kiểm tra thú cưng trong trí nhớ có mâu thuẫn loại (chó vs mèo) với câu hiện tại không."""
        if not last_pet:
            return None
        ptype = normalize_vi(str(last_pet.get("pet_type", "")))
        detected = self._detect_pet_type_intent(raw_q, norm_q)
        if detected == "Mèo" and ptype == "cho":
            return None
        if detected == "Chó" and ptype == "meo":
            return None
        return last_pet

    def _extract_conversation_memory(self, history: Optional[List[Dict[str, str]]]) -> Dict[str, Any]:
        """Khôi phục tên khách hàng và thú cưng vừa nhắc tới từ lịch sử trò chuyện."""
        mem: Dict[str, Any] = {
            "user_name": None,
            "last_pet": None,
            "last_assistant_reply": "",
        }
        if not history:
            return mem

        for turn in history:
            role = turn.get("role", "")
            content = str(turn.get("content", ""))
            if not content:
                continue
            if role == "user":
                nm = self._extract_person_name(content)
                if nm:
                    mem["user_name"] = nm
                breeds = self._find_items_by_alias(content, self.BREED_ALIASES)
                if breeds:
                    mem["last_pet"] = breeds[-1]
                else:
                    supplies = self._find_items_by_alias(content, self.SUPPLY_ALIASES)
                    if supplies:
                        mem["last_pet"] = supplies[-1]
            elif role == "assistant":
                mem["last_assistant_reply"] = content
                skus = re.findall(r"`((?:DOG|CAT|PET)-[A-Z]+-\d+)`", content)
                pet_skus = [s for s in set(skus) if "-PET-" in s and s in self.sku_map]
                if len(pet_skus) == 1:
                    mem["last_pet"] = self.sku_map[pet_skus[0]]
                elif (
                    mem.get("last_pet") is None
                    and len(set(skus)) == 1
                    and skus[0] in self.sku_map
                ):
                    mem["last_pet"] = self.sku_map[skus[0]]
        return mem

    # ------------------------------------------------------------------
    # Trình phân tích ngữ cảnh & Xây dựng câu trả lời mượt mà
    # ------------------------------------------------------------------

    def build_situation_hint(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """Tạo gợi ý tình huống cho Gemini hoặc cho mục đích kiểm thử phân tích."""
        mem = self._extract_conversation_memory(history)
        cur_name = self._extract_person_name(query) or mem["user_name"]
        tag, score, _ = self.classifier.predict(query)
        breeds = self._find_items_by_alias(query, self.BREED_ALIASES)
        context_pet = breeds[0] if breeds else self._compatible_context_pet(query, normalize_vi(query), mem.get("last_pet"))

        parts = [f"Intent={tag} ({score:.2f})"]
        if cur_name:
            parts.append(f"Tên khách={cur_name}")
        if context_pet:
            parts.append(f"Sản phẩm đang bàn={context_pet.get('name')} ({context_pet.get('sku')})")
        return " | ".join(parts)

    def _greeting_prefix(self, user_name: Optional[str]) -> str:
        if user_name:
            return f"Chào bạn **{user_name}**! "
        return ""

    def _format_pet_card(self, p: Dict[str, Any], prefix: str = "") -> str:
        warranty_line = (
            "• **Bảo hành**: 15 ngày Parvo & Care, đã tiêm phòng 1-2 mũi và tẩy giun kèm sổ thú y.\n"
            if p.get("category") in ("Chó cảnh", "Mèo cảnh")
            else "• **Ưu đãi**: Nhập mã **`GENZVIP20`** giảm 20% (đơn từ 100K) hoặc **`MEOW50K`** giảm 50K.\n"
        )
        return (
            f"{prefix}🐾 **{p['name']}** (`{p['sku']}`)\n"
            f"• **Giá niêm yết**: **{int(p['price']):,} đ** (Còn {p.get('stock', 1)} sản phẩm)\n"
            f"• **Đặc điểm**: {p.get('description', '')}\n"
            f"{warranty_line}"
            f"👉 Bạn có muốn mình tư vấn thêm cách chăm sóc, phí giao hàng hay áp mã giảm giá cho sản phẩm này không?"
        )

    def consult(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """Xử lý yêu cầu khách hàng bằng NLP Classifier + Bộ nhớ đa lượt + RAG Dữ liệu."""
        raw_q = str(query or "").strip()
        if not raw_q:
            return "Bạn cứ nhắn câu hỏi bất kỳ về thú cưng, giá cả hoặc dịch vụ Spa để mình hỗ trợ nhé! 🐾"

        norm_q = normalize_vi(raw_q)
        mem = self._extract_conversation_memory(history)
        cur_name = self._extract_person_name(raw_q)
        user_name = cur_name or mem.get("user_name")
        prefix = self._greeting_prefix(user_name)

        breeds_in_q = self._find_items_by_alias(raw_q, self.BREED_ALIASES)
        supplies_in_q = self._find_items_by_alias(raw_q, self.SUPPLY_ALIASES)
        is_coref = self._has_coref_pronoun(raw_q)
        explicit_item = breeds_in_q[0] if breeds_in_q else (supplies_in_q[0] if supplies_in_q else None)
        pet_type_intent = self._detect_pet_type_intent(raw_q, norm_q)
        compat_mem_pet = self._compatible_context_pet(raw_q, norm_q, mem.get("last_pet"))
        active_pet = explicit_item if explicit_item else (compat_mem_pet if is_coref else None)
        topic_pet = explicit_item or compat_mem_pet

        weight_kg = self._extract_weight_kg(raw_q)
        price_filter = self._extract_price_filter(raw_q)
        intent, confidence, _ = self.classifier.predict(raw_q)

        # ----- Tình huống 1: Khách giới thiệu tên thuần túy ("tôi tên trung") -----
        if cur_name and self._is_pure_name_intro(raw_q, cur_name):
            return (
                f"Chào bạn **{cur_name}**! 🐾 Rất vui được làm quen và phục vụ bạn tại **Meow & Woof**.\n"
                f"Mình sẽ ghi nhớ tên bạn trong suốt cuộc trò chuyện này! "
                f"Hôm nay {cur_name} muốn tìm hiểu bé cún/mèo nào, đặt lịch Spa hay xem mã giảm giá ạ?"
            )

        # ----- Tình huống 1b: Phản hồi theo tri thức Q&A tự dạy trong custom_qas -----
        qa_match, qa_score = self.rag.search_custom_qa(raw_q)
        if qa_match and qa_score >= 0.62:
            return f"{prefix}{qa_match['answer']}"

        # ----- Tình huống 2: Tình huống khẩn cấp y tế / thú cưng có dấu hiệu bệnh -----
        medical_cues = any(w in norm_q for w in [
            "tieu chay", "non mua", "non oi", "di ngoai", "bo an", "bi sot",
            "ho khac", "chay nuoc mui", "hat hoi", "ve ran", "bo chet",
            "nam da", "bi parvo", "bi care", "benh parvo", "benh care",
            "bi benh", "bi om", "cap cuu", "soc nhiet"
        ])
        if medical_cues or (intent == "pet_emergency_health" and confidence >= 0.30):
            return self._handle_emergency_health(norm_q, topic_pet, user_name)

        # ----- Tình huống 3: Khách khiếu nại / bực mình / giao chậm / hàng lỗi -----
        complaint_cues = any(w in norm_q for w in [
            "khieu nai", "cham qua", "te qua", "that vong", "khong hai long",
            "buc minh", "giao sai", "giao nham", "bi hu", "hong roi", "thai do"
        ])
        if complaint_cues or (intent == "complaint_issue" and confidence >= 0.34):
            return self._handle_complaint(user_name)

        # ----- Tình huống 4: Khách mặc cả / chê giá đắt / xin giảm thêm -----
        bargain_cues = any(w in norm_q for w in [
            "mac qua", "dat qua", "dat the", "bot di", "bot chut", "giam them",
            "fix gia", "chat qua", "thuong luong", "giam gia them"
        ])
        if bargain_cues or (intent == "bargain_discount" and confidence >= 0.32):
            return self._handle_bargain(topic_pet, user_name)

        # ----- Tình huống 5: So sánh 2 giống thú cưng hoặc chó vs mèo -----
        compare_cues = any(w in norm_q for w in ["so sanh", "khac nhau", "hay la", "chon giua", "phan van"]) or (
            len(breeds_in_q) >= 2
        )
        if compare_cues or (intent == "breed_comparison" and confidence >= 0.30):
            return self._handle_comparison(norm_q, breeds_in_q, mem.get("last_pet"), user_name)

        # ----- Tình huống 6: Con rẻ nhất / đắt nhất -----
        q_tok_set = set(preprocess_vi_tokens(norm_q))
        cheap_cues = any(w in norm_q for w in ["re nhat", "thap nhat", "mem nhat"]) or (
            intent == "cheapest_pet"
            and confidence >= 0.35
            and bool(q_tok_set & {"re", "thap", "mem", "gia", "tien"})
        )
        if cheap_cues:
            return self._handle_cheapest_or_expensive(raw_q, norm_q, mode="cheapest", user_name=user_name)

        exp_cues = any(w in norm_q for w in ["dat nhat", "cao nhat", "xin nhat", "cao cap nhat"]) or (
            intent == "most_expensive_pet"
            and confidence >= 0.35
            and bool(q_tok_set & {"dat", "cao", "mac", "xin", "vip", "gia", "sang"})
        )
        if exp_cues:
            return self._handle_cheapest_or_expensive(raw_q, norm_q, mode="expensive", user_name=user_name)

        # ----- Tình huống 7: Hỏi ăn gì / chăm sóc dinh dưỡng (bao gồm "con đó ăn gì?") -----
        nutrition_cues = any(w in norm_q for w in ["an gi", "an hat", "bieng an", "ken an", "cham soc", "uong sua", "xuong ga", "thuc don"])
        if nutrition_cues or (intent == "pet_nutrition_care" and confidence >= 0.34):
            return self._handle_nutrition_care(topic_pet, user_name)

        # ----- Tình huống 8: Kiểm tra đơn hàng / hủy đơn / đổi địa chỉ / cách đặt mua -----
        order_cues = any(w in norm_q for w in ["don hang", "kiem tra don", "huy don", "doi dia chi", "lich hen cua toi", "ho so don"])
        if order_cues or (intent == "order_tracking_cancel" and confidence >= 0.33):
            return (
                f"{prefix}📦 **Tra cứu, chỉnh sửa hoặc hủy đơn hàng / lịch hẹn Spa**:\n"
                "• Bạn vào mục **Hồ sơ & Đơn mua** (`/orders`) trên thanh menu — hệ thống tự đồng bộ trạng thái đơn hàng & hạng VIP theo SĐT/Email của bạn.\n"
                "• Nếu cần **đổi địa chỉ giao gấp** hoặc **hủy đơn/lịch Spa vừa đặt**, bạn gọi ngay Hotline/Zalo **`0905.123.456`** để nhân viên xử lý ngay lập tức nhé!"
            )

        buy_cues = any(w in norm_q for w in ["dat mua", "cach mua", "mua hang", "chot don", "mua con nay", "mua be nay", "mua em nay", "gio hang lam gi", "mua online", "dat hang"])
        has_howto_word = any(w in norm_q for w in ["dat", "cach", "online", "gio hang", "con nay", "be nay"])
        if buy_cues or (intent == "how_to_buy_order" and confidence >= 0.36 and (has_howto_word or explicit_item is not None)):
            return self._handle_how_to_buy(topic_pet, user_name)

        # ----- Tình huống 9: Tra cứu khoảng giá ("tìm chó dưới 5 triệu") -----
        if price_filter:
            min_p, max_p, range_label = price_filter
            cat_f = pet_type_intent if pet_type_intent in ("Chó", "Mèo") else None
            matched = sorted(
                self.kb.search_pets(min_price=min_p, max_price=max_p, category=cat_f, pets_only=True),
                key=lambda x: float(x.get("price", 0)),
            )
            if matched:
                lines = [f"{prefix}🐾 **Các bé phù hợp ngân sách {range_label}**:"]
                for p in matched[:6]:
                    lines.append(f"• **{p['name']}** (`{p['sku']}`): **{int(p['price']):,} đ** (Còn {p.get('stock', 1)} bé)")
                lines.append("💡 Bạn muốn xem chi tiết bé nào trong danh sách trên?")
                return "\n".join(lines)
            cheapest = sorted(self.kb.search_pets(category=cat_f, pets_only=True), key=lambda x: float(x.get("price", 0)))
            if cheapest:
                top_cheap = cheapest[0]
                return (
                    f"{prefix}Hiện tại các bé thuần chủng {cat_f or 'chó mèo'} tại Meow & Woof có mức giá thấp nhất từ "
                    f"**{int(top_cheap['price']):,} đ** ({top_cheap['name']}).\n"
                    f"Nếu bạn áp thêm mã **`GENZVIP20`** (giảm 20%, tối đa 500,000 đ) sẽ tiết kiệm đáng kể đó ạ! 🎁"
                )

        # ----- Tình huống 10: Hỏi Spa (có tính cân nặng kg nếu khách cung cấp!) -----
        spa_cues = any(w in norm_q for w in ["spa", "tam say", "tam cho", "tam meo", "cat tia", "tia long", "grooming", "cao long", "trong giu", "khach san", "kham suc khoe"])
        if spa_cues or weight_kg is not None or (intent in {"spa_booking_howto", "spa_pricing"} and confidence >= 0.31):
            return self._handle_spa(norm_q, weight_kg, topic_pet, intent, user_name)

        # ----- Tình huống 10b: Các câu hỏi thực tế chuyên sâu về nuôi dưỡng & chăm sóc -----
        vac_sched_cues = any(w in norm_q for w in ["lich tiem", "may mui", "thang thu may", "tay giun", "phong dai", "5 benh", "7 benh", "4 benh"])
        if vac_sched_cues or (intent == "vaccination_schedule" and confidence >= 0.34):
            return self._handle_vaccination_schedule(pet_type_intent, topic_pet, user_name)

        if any(w in norm_q for w in ["bao hanh", "tiem phong", "vac xin", "parvo", "care", "thuan chung", "doi tra", "so suc khoe"]) or (
            intent == "warranty_health_policy" and confidence >= 0.34
        ):
            pet_note = (
                f"Đối với **{topic_pet['name']}** và toàn bộ chó mèo tại shop:\n"
                if topic_pet and topic_pet.get("category") in ("Chó cảnh", "Mèo cảnh")
                else ""
            )
            return (
                f"{prefix}{pet_note}"
                f"🛡️ **Bảo hành**: {self.kb.policies['warranty']}\n"
                f"💉 **Tiêm phòng**: {self.kb.policies['vaccination']}"
            )

        cost_cues = any(w in norm_q for w in ["ton bao nhieu", "chi phi nuoi", "1 thang", "moi thang", "tien an", "ton kem", "sinh vien nuoi"])
        if cost_cues or (intent == "monthly_cost_estimate" and confidence >= 0.34):
            return self._handle_monthly_cost(pet_type_intent, topic_pet, user_name)

        train_cues = any(w in norm_q for w in ["di ve sinh", "i bay", "dai bay", "thau cat", "cao ghe", "sofa", "hay sua", "sua nhieu", "can dep", "can do", "huan luyen", "day cho", "day meo", "bat tay"])
        if train_cues or (intent == "pet_training_behavior" and confidence >= 0.34):
            return self._handle_training_behavior(norm_q, pet_type_intent, user_name)

        shedding_cues = ("it rung long" not in norm_q) and any(
            w in norm_q for w in ["rung long", "bao lau tam", "may ngay tam", "may tuan tam", "ve sinh tai", "cat mong", "hoi mieng", "mui co the", "mui hoi"]
        )
        if shedding_cues or (intent == "shedding_grooming_tips" and confidence >= 0.34):
            return self._handle_shedding_grooming(norm_q, pet_type_intent, user_name)

        spay_cues = any(w in norm_q for w in ["triet san", "gao duc", "dong duc", "phoi giong", "mang thai", "may ngay de"])
        if spay_cues or (intent == "spay_neuter_breeding" and confidence >= 0.34):
            return self._handle_spay_neuter(pet_type_intent, user_name)

        naming_cues = any(w in norm_q for w in ["dat ten", "ten hay cho", "ten cute"])
        if naming_cues or (intent == "pet_naming_ideas" and confidence >= 0.34):
            return self._handle_pet_naming(pet_type_intent, user_name)

        cohab_cues = any(w in norm_q for w in ["nuoi chung", "danh nhau", "lam quen", "meo cu", "meo moi"])
        if cohab_cues or (intent == "cohabitation_multi_pet" and confidence >= 0.34):
            return self._handle_cohabitation(user_name)

        age_cues = any(w in norm_q for w in ["may thang", "bao nhieu thang", "duc cai", "duc hay cai", "gioi tinh", "truong thanh", "nguon goc", "xuat xu", "xem video", "xem mat"])
        if age_cues or (intent == "pet_age_gender_origin" and confidence >= 0.34):
            return self._handle_pet_age_gender_origin(pet_type_intent, topic_pet, user_name)

        # ----- Tình huống 11: Giao hàng / thanh toán / VIP / voucher / địa chỉ -----
        if any(w in norm_q for w in ["ship", "giao hang", "van chuyen", "hoa toc", "ha noi", "tinh xa"]) or (
            intent == "shipping_delivery" and confidence >= 0.34
        ):
            return (
                f"{prefix}🚚 **Chính sách vận chuyển**: {self.kb.policies['shipping']}\n"
                f"🎁 Mẹo: Nhập mã **`FREESHIP30K`** ở bước thanh toán để được trợ giá vận chuyển **30,000 đ** cho mọi đơn hàng nhé!"
            )

        if any(w in norm_q for w in ["thanh toan", "vietqr", "cod", "chuyen khoan", "tra gop", "dat coc", "quet qr", "so tai khoan"]) or (
            intent == "payment_vietqr_cod" and confidence >= 0.34
        ):
            installment_note = (
                "\n• *Lưu ý trả góp / đặt cọc giữ bé*: Bạn liên hệ trực tiếp Hotline **`0905.123.456`** để nhân viên hỗ trợ linh hoạt theo nhu cầu nhé."
                if ("tra gop" in norm_q or "dat coc" in norm_q)
                else ""
            )
            return f"{prefix}💳 **Hình thức thanh toán**: {self.kb.policies['payment']}{installment_note}"

        if any(w in norm_q for w in ["voucher", "ma giam gia", "khuyen mai", "code giam", "genzvip", "meow50k"]) or (
            intent == "voucher_promo" and confidence >= 0.34
        ):
            return self._format_vouchers_reply(user_name)

        if any(w in norm_q for w in ["hang vip", "thanh vien", "kim cuong", "hang vang", "hang bac", "tich diem"]) or (
            intent == "vip_membership" and confidence >= 0.34
        ):
            lines = [f"{prefix}👑 **Đặc quyền Hạng Thành Viên VIP (tự động tích lũy theo tổng chi tiêu)**:"]
            for t in self.kb.membership_tiers:
                lines.append(f"• **{t['tier']}** (Từ **{int(t['min_spend']):,} đ**): {t['benefit']}")
            return "\n".join(lines)

        if any(w in norm_q for w in ["dia chi", "o dau", "chi duong", "may gio", "gio mo cua", "gio lam viec", "hotline", "so dien thoai", "email lien he"]) or (
            intent == "shop_contact_hours" and confidence >= 0.34
        ):
            return (
                f"{prefix}📍 **Địa chỉ**: {self.kb.shop_info['address']}\n"
                f"⏰ **Giờ mở cửa**: {self.kb.shop_info['hours']}\n"
                f"📞 **Hotline / Zalo**: **{self.kb.shop_info['hotline']}** | **Email**: `{self.kb.shop_info['email']}`"
            )

        # ----- Tình huống 12: Hỏi khả năng AI / Danh tính AI / Chung cư / Menu giống / Phụ kiện -----
        if intent == "capabilities_faq" and confidence >= 0.30:
            return self._handle_capabilities(user_name)

        if intent == "ask_bot_identity" and confidence >= 0.30:
            return (
                f"{prefix}🤖 Mình là **Trợ lý AI Meow & Woof** (tích hợp Gemini & kho dữ liệu cửa hàng).\n"
                "Mình trực 24/7 để báo giá 42 sản phẩm/thú cưng, tính phí Spa theo cân nặng, tư vấn chăm sóc và săn mã giảm giá cho bạn!"
            )

        if any(w in norm_q for w in ["chung cu", "it rung long", "it sua", "moi nuoi", "phong tro", "tre nho", "di ung long"]) or (
            intent == "apartment_beginner_advice" and confidence >= 0.32
        ):
            return (
                f"{prefix}🏢 **Gợi ý tuyệt vời cho chung cư / người mới nuôi**:\n"
                "• **Chó Poodle Tiny** (`DOG-PET-002`): **4,800,000 đ** — Không rụng lông, không hôi, siêu thông minh.\n"
                "• **Chó Pug Mặt Xệ** (`DOG-PET-014`): **4,500,000 đ** — Hiền lành, ít sủa, ít vận động nặng.\n"
                "• **Mèo Anh Lông Ngắn (ALN)** (`CAT-PET-001`): **4,500,000 đ** — Điềm đạm, tự biết đi vệ sinh đúng chỗ.\n"
                "• **Mèo Sphynx Không Lông** (`CAT-PET-011`): **13,500,000 đ** — Lý tưởng cho người dị ứng lông.\n"
                "👉 Bạn thích bé nào nhất để mình gửi thêm thông tin chi tiết?"
            )

        if any(w in norm_q for w in ["nhung giong", "cac loai", "danh sach", "liet ke", "menu thu cung", "ban nhung con gi"]) or (
            intent == "pet_list_menu" and confidence >= 0.32
        ):
            return self._handle_pet_list_menu(raw_q, norm_q, user_name)

        # ----- Tình huống 13: Tra cứu cụ thể giống chó/mèo, phụ kiện hoặc câu nối tiếp -----
        if active_pet and (
            breeds_in_q
            or supplies_in_q
            or is_coref
            or intent == "catalog_lookup"
        ):
            return self._format_pet_card(active_pet, prefix=prefix)

        supplies_cues = bool(re.search(
            r"\b(?:do an|phu kien|thuc an|do choi|do dung|y te|cat ve sinh|sua tam|balo|tru cao|xuong gam|hat|pate)\b",
            norm_q,
        ))
        if supplies_cues:
            return self._handle_supplies_list(user_name)

        # ----- Tình huống 13b: Hội thoại gật đầu / từ chối ngắn gọn ("ok", "có", "kể thêm đi", "không") -----
        word_count = len(norm_q.split())
        if word_count <= 5 and pet_type_intent is None and explicit_item is None and not price_filter and not weight_kg:
            aff_set = {"ok", "oke", "okay", "co", "co a", "da co", "da vang", "vang", "vang a", "u", "uh", "duoc", "duoc a", "tiep di", "ke them", "ok shop", "ok ban"}
            neg_set = {"khong", "ko", "k", "da khong", "thoi", "khong can", "chua can", "de sau", "thoi cam on"}
            if norm_q in aff_set or (intent == "short_affirmative" and confidence >= 0.36):
                return self._handle_short_affirmative(mem, user_name)
            if norm_q in neg_set or (intent == "short_negative" and confidence >= 0.36):
                return f"Dạ vâng {f'**{user_name}**' if user_name else 'bạn'}! Khi nào cần tư vấn chọn bé, đặt Spa hoặc lấy mã giảm giá cứ nhắn mình ngay nhé! 🐾"

        # ----- Tình huống 13c: RAG Tìm kiếm ngữ nghĩa theo đặc điểm ngoại hình / màu sắc / tính cách -----
        rag_hits = self.rag.retrieve_pets(raw_q, pet_type_filter=pet_type_intent, top_k=4)
        if rag_hits and rag_hits[0][1] >= 0.52 and intent not in {"greeting_intro", "thanks_goodbye", "smalltalk_chitchat"}:
            top_score = rag_hits[0][1]
            selected = [p for p, sc in rag_hits if sc >= max(0.52, top_score * 0.78)][:4]
            return self._handle_rag_matches(raw_q, selected, pet_type_intent, user_name)

        if intent == "accessories_supplies" and confidence >= 0.40:
            return self._handle_supplies_list(user_name)

        # ----- Tình huống 13d: Hỏi mua / tìm hiểu chung về Chó, Mèo hoặc Thú cưng ("tôi muốn mua chó") -----
        if intent == "buy_dog_general" and (pet_type_intent == "Chó" or confidence >= 0.34):
            return self._handle_buy_category("Chó", user_name)
        if intent == "buy_cat_general" and (pet_type_intent == "Mèo" or confidence >= 0.34):
            return self._handle_buy_category("Mèo", user_name)
        if intent == "buy_pet_general" and confidence >= 0.34:
            return self._handle_buy_category(pet_type_intent or "BOTH", user_name)

        # ----- Tình huống 14: Chào hỏi, Cảm ơn / Tạm biệt, Tán gẫu ngoài lề -----
        if intent == "greeting_intro" and confidence >= 0.32 and pet_type_intent is None:
            return (
                f"Xin chào {f'**{user_name}**' if user_name else 'bạn'}! 🐶🐱 Mình là Trợ lý AI của Meow & Woof.\n"
                "Bạn đang muốn tìm giống chó mèo nào, xem bảng giá Spa hay nhận mã giảm giá hôm nay ạ?"
            )

        if intent == "thanks_goodbye" and confidence >= 0.32 and pet_type_intent is None:
            return (
                f"Dạ không có gì đâu {f'**{user_name}**' if user_name else 'bạn'} ơi! ❤️ Rất vui được hỗ trợ bạn.\n"
                f"Khi nào cần đón bé cưng hoặc đặt lịch Spa, cứ nhắn mình hoặc gọi Hotline **{self.kb.shop_info['hotline']}** nhé!"
            )

        if intent == "smalltalk_chitchat" and confidence >= 0.31 and pet_type_intent is None:
            return self._handle_smalltalk(raw_q, user_name)

        # ----- Lưới an toàn miền thú cưng trước Out-of-scope -----
        if pet_type_intent in ("Chó", "Mèo", "BOTH"):
            return self._handle_buy_category(pet_type_intent, user_name)
        if any(w in norm_q for w in ["thu cung", "ban pet", "mua pet", "tu van giup", "shop co gi", "co nhung gi"]):
            return self._handle_buy_category("BOTH", user_name)

        # ----- Tình huống 15: Tin nhắn thực sự ngoài phạm vi / vô nghĩa -----
        return self._handle_out_of_scope(raw_q, user_name, mem.get("last_assistant_reply", ""))

    # ------------------------------------------------------------------
    # Các hàm chuyên biệt xử lý từng tình huống
    # ------------------------------------------------------------------

    def _handle_emergency_health(self, norm_q: str, active_pet: Optional[Dict[str, Any]], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        pet_label = f"**{active_pet['name']}**" if active_pet else "bé cưng"

        if any(w in norm_q for w in ["ve ran", "bo chet", "nam da", "ngua", "rung long tung mang"]):
            return (
                f"{prefix}🩺 **Hướng dẫn xử lý khi {pet_label} bị ve rận / nấm da**:\n"
                "1. Cách ly tạm thời với các bé khác và giặt phơi nắng toàn bộ nệm, ổ nằm bằng nước ấm.\n"
                "2. Dùng ngay **Nhỏ Gáy Trị Ve Rận Frontline Plus** (`PET-MED-002` — **230,000 đ**) để diệt tận gốc ve rận trong 30 ngày.\n"
                "3. Kết hợp tắm **Sữa Tắm SOS Khử Mùi & Dưỡng Lông** (`PET-CARE-001` — **145,000 đ**) hoặc đặt gói **Khám sức khỏe (`120,000 đ`)** tại shop.\n"
                f"📞 Cần tư vấn trực tiếp với bác sĩ thú y, bạn gọi ngay Hotline **{self.kb.shop_info['hotline']}** nhé!"
            )

        return (
            f"{prefix}🚨 **Lưu ý xử lý gấp khi {pet_label} có dấu hiệu mệt / tiêu chảy / bỏ ăn / nôn**:\n"
            "1. **Ngừng ngay** thức ăn lạ, sữa tươi hoặc đồ tanh/mỡ; chỉ cho uống nước ấm hoặc điện giải (Oresol thú y) từng chút một.\n"
            "2. **Giữ ấm** nơi nằm, tránh gió lùa/máy lạnh trực tiếp và tách riêng nếu nhà có nhiều bé.\n"
            "3. Nếu bé mới đón tại **Meow & Woof** trong **15 ngày bảo hành (Parvo & Care)**, vui lòng liên hệ ngay để được thăm khám miễn phí/đổi trả 1-1.\n"
            "4. Trường hợp bé lờ đờ, đi ngoài ra máu hoặc nôn liên tục >12h: **Đưa đến phòng khám thú y gần nhất ngay** hoặc gọi gấp Hotline **"
            f"{self.kb.shop_info['hotline']}**! Khi bé ổn định có thể bổ sung **Gel Dinh Dưỡng Nutri-Plus Gel Virbac (`185,000 đ`)**."
        )

    def _handle_complaint(self, user_name: Optional[str]) -> str:
        prefix = f"Chào bạn **{user_name}**, " if user_name else "Dạ "
        return (
            f"{prefix}**Meow & Woof** chân thành xin lỗi bạn vì trải nghiệm chưa trọn vẹn vừa qua ạ! 🙏\n"
            "Mọi phản hồi của bạn đều rất quan trọng và shop xin nhận trách nhiệm xử lý ưu tiên ngay:\n"
            "• **Kiểm tra đơn / giao chậm / nhầm hàng**: Gọi trực tiếp Hotline/Zalo **`0905.123.456`** (kèm SĐT đặt hàng) để được hoàn tiền/giao bù hỏa tốc ngay trong ngày.\n"
            "• **Góp ý chất lượng / bảo hành**: Gửi email về **`trungvt040106@gmail.com`** — Quản lý sẽ phản hồi và tặng mã đền bù tri ân cho bạn trong vòng 30 phút."
        )

    def _handle_bargain(self, active_pet: Optional[Dict[str, Any]], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        if active_pet:
            price = float(active_pet.get("price", 0) or 0)
            disc_20 = min(price * 0.20, 500000.0) if price >= 100000 else 0.0
            final_p = max(0.0, price - disc_20)
            value_line = (
                "• Bảo hành 15 ngày Parvo & Care, tiêm phòng 1-2 mũi & sổ theo dõi thú y.\n"
                if active_pet.get("category") in ("Chó cảnh", "Mèo cảnh")
                else "• Sản phẩm chính hãng chuẩn thú y, đóng gói cẩn thận & giao nhanh.\n"
            )
            return (
                f"{prefix}😊 Mình hiểu tâm lý cân nhắc chi phí của bạn! Với **{active_pet['name']}** giá niêm yết **{int(price):,} đ** đã bao gồm:\n"
                f"{value_line}"
                f"🎁 Tuy nhiên, bạn hoàn toàn có thể áp ngay mã **`GENZVIP20`** (giảm 20%, tối đa 500,000 đ) để giảm còn **{int(final_p):,} đ**, "
                "hoặc mua kèm combo phụ kiện và gọi Hotline **`0905.123.456`** để shop hỗ trợ ưu đãi tốt nhất nhé!"
            )
        return (
            f"{prefix}😊 Tất cả bé tại **Meow & Woof** đều thuần chủng, tiêm vắc xin đầy đủ và bảo hành sức khỏe 15 ngày nên shop niêm yết giá minh bạch.\n"
            "🎁 Để tiết kiệm nhất, bạn dùng ngay 3 mã đang mở tại giỏ hàng:\n"
            "• **`GENZVIP20`**: Giảm **20%** (tối đa **500,000 đ**) cho đơn từ 100K.\n"
            "• **`MEOW50K`**: Trừ thẳng **50,000 đ** cho đơn từ 200K.\n"
            "• **`FREESHIP30K`**: Trợ giá ship **30,000 đ**.\n"
            "💬 Nếu bạn mua combo từ 2 sản phẩm hoặc có thẻ VIP (giảm thêm tới 15%), cứ nhắn Hotline **`0905.123.456`** để được báo giá ưu đãi riêng nha!"
        )

    def _handle_how_to_buy(self, topic_pet: Optional[Dict[str, Any]], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        pet_intro = ""
        if topic_pet:
            price = float(topic_pet.get("price", 0) or 0)
            disc = min(price * 0.20, 500000.0) if price >= 100000 else 0.0
            pet_intro = (
                f"Với **{topic_pet['name']}** (`{topic_pet['sku']}` — **{int(price):,} đ**, áp **`GENZVIP20`** còn **{int(price - disc):,} đ**):\n"
            )
        return (
            f"{prefix}🛒 **Hướng dẫn đặt mua nhanh trên Meow & Woof**:\n"
            f"{pet_intro}"
            "1. Tìm bé trên trang **Sản phẩm** (hoặc Trang chủ) rồi bấm **Thêm vào giỏ hàng**.\n"
            "2. Vào **Giỏ hàng (`/cart`)**, nhập mã **`GENZVIP20`** để giảm ngay 20% (tối đa 500,000 đ).\n"
            "3. Chọn **Chuyển khoản VietQR 24/7** (quét mã QR tự động) hoặc **COD** (trả tiền khi nhận) → xác nhận là xong!\n"
            "📞 Cần đặt giữ bé gấp ngay bây giờ, gọi Hotline **`0905.123.456`** nhé!"
        )

    def _handle_comparison(
        self,
        norm_q: str,
        breeds_in_q: List[Dict[str, Any]],
        last_pet: Optional[Dict[str, Any]],
        user_name: Optional[str],
    ) -> str:
        prefix = self._greeting_prefix(user_name)
        pair: List[Dict[str, Any]] = list(breeds_in_q[:2])
        if len(pair) == 1 and last_pet and last_pet.get("sku") != pair[0].get("sku"):
            pair.append(last_pet)

        if len(pair) >= 2:
            p1, p2 = pair[0], pair[1]
            cheaper = p1 if p1["price"] < p2["price"] else p2
            return (
                f"{prefix}⚖️ **So sánh nhanh {p1.get('breed', p1['name'])} vs {p2.get('breed', p2['name'])}**:\n"
                f"1. **{p1['name']}** (`{p1['sku']}`): **{int(p1['price']):,} đ** (Còn {p1.get('stock', 1)})\n"
                f"   → {p1.get('description', '')}\n"
                f"2. **{p2['name']}** (`{p2['sku']}`): **{int(p2['price']):,} đ** (Còn {p2.get('stock', 1)})\n"
                f"   → {p2.get('description', '')}\n"
                f"💡 *Gợi ý*: Nếu ưu tiên tiết kiệm chi phí hơn, **{cheaper['breed']}** đang có mức giá mềm hơn (**{int(cheaper['price']):,} đ**). "
                "Bạn thích ngoại hình hay tính cách bé nào hơn ạ?"
            )

        if "cho" in preprocess_vi_tokens(norm_q) and "meo" in preprocess_vi_tokens(norm_q):
            return (
                f"{prefix}🐶🐱 **Nên chọn nuôi Chó hay Mèo?**\n"
                "• **Nuôi Chó** (từ **4,200,000 đ** - Chihuahua, Pug, Poodle Tiny): Quấn chủ, năng động, thích đi dạo — hợp với bạn thích tương tác nhiều.\n"
                "• **Nuôi Mèo** (từ **3,800,000 đ** - Mèo Xiêm, Mèo Anh Lông Ngắn): Sạch sẽ, điềm tĩnh, tự đi vệ sinh vào thau cát — rất hợp người bận rộn hoặc ở phòng nhỏ."
            )

        return (
            f"{prefix}⚖️ Để mình so sánh chính xác 2 giống bạn đang phân vân, bạn nhắn rõ tên 2 bé giúp mình nhé!\n"
            "• VD: *\"So sánh Poodle và Corgi\"* hoặc *\"Mèo Anh Lông Ngắn hay Ragdoll dễ nuôi hơn?\"*"
        )

    def _handle_cheapest_or_expensive(self, raw_q: str, norm_q: str, mode: str, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        ptype = self._detect_pet_type_intent(raw_q, norm_q)
        dogs = sorted(self.kb.search_pets(category="Chó", pets_only=True), key=lambda x: float(x["price"]), reverse=(mode == "expensive"))
        cats = sorted(self.kb.search_pets(category="Mèo", pets_only=True), key=lambda x: float(x["price"]), reverse=(mode == "expensive"))
        all_pets = sorted(dogs + cats, key=lambda x: float(x["price"]), reverse=(mode == "expensive"))

        label = "giá mềm nhất" if mode == "cheapest" else "cao cấp & giá cao nhất"
        if ptype == "Chó" and dogs:
            target_list = dogs[:3]
            heading = f"🐶 **Top Chó cảnh {label} tại Meow & Woof**:"
        elif ptype == "Mèo" and cats:
            target_list = cats[:3]
            heading = f"🐱 **Top Mèo cảnh {label} tại Meow & Woof**:"
        else:
            target_list = all_pets[:4]
            heading = f"🐾 **Top Thú cưng {label} tại Meow & Woof**:"

        lines = [f"{prefix}{heading}"]
        for p in target_list:
            lines.append(f"• **{p['name']}** (`{p['sku']}`): **{int(p['price']):,} đ**")
        if mode == "cheapest":
            lines.append("🎁 Ngoài ra dùng mã **`GENZVIP20`** được giảm thêm **20%** (tối đa 500,000 đ) khi thanh toán đó ạ!")
        return "\n".join(lines)

    def _handle_nutrition_care(self, active_pet: Optional[Dict[str, Any]], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        is_cat = bool(active_pet and active_pet.get("pet_type") == "Mèo")
        is_dog = bool(active_pet and active_pet.get("pet_type") == "Chó")
        subject = f"**{active_pet['name']}**" if active_pet else "bé cún/mèo con"

        if is_cat:
            return (
                f"{prefix}🥣 **Chế độ ăn chuẩn cho {subject}**:\n"
                "• **Hạt khô chính**: **Hạt Royal Canin Indoor 27 (2kg)** (`CAT-FD-001` — **465,000 đ**) giúp giảm mùi phân & tiêu búi lông.\n"
                "• **Kích thích ăn ngon**: Trộn thêm **Pate Mèo Ciao Churu** (`CAT-FD-002` — **35,000 đ**/gói 4 thanh).\n"
                "• **Lưu ý**: Tuyệt đối không cho uống sữa bò tươi có lactose hay ăn hành/sô-cô-la; luôn để sẵn nước sạch & cát **Tofu (`125,000 đ`)**."
            )
        if is_dog:
            return (
                f"{prefix}🥣 **Chế độ ăn chuẩn cho {subject}**:\n"
                "• **Hạt dinh dưỡng**: **Hạt SmartHeart Adult Vị Bò Nướng (3kg)** (`DOG-FD-001` — **215,000 đ**) bổ sung Omega 3 & 6 mượt lông.\n"
                "• **Với bé 2-3 tháng mới về nhà**: Chia 3-4 bữa/ngày, ngâm hạt mềm bằng nước ấm trong 5 phút đầu; hỗ trợ thêm **Nutri-Plus Gel Virbac (`185,000 đ`)** nếu bé kén ăn.\n"
                "• **Cấm kỵ**: Không cho ăn xương gà nhỏ dễ hóc, sô-cô-la, nho, hành tỏi hoặc đồ ăn mặn của người."
            )
        return (
            f"{prefix}🥣 **Gợi ý dinh dưỡng chuẩn cho chó mèo tại nhà**:\n"
            "• **Cho Chó**: **Hạt SmartHeart Vị Bò Nướng 3kg** (`DOG-FD-001` — **215,000 đ**), ngâm ấm nếu bé dưới 3 tháng tuổi.\n"
            "• **Cho Mèo**: **Hạt Royal Canin Indoor 27 2kg** (`CAT-FD-001` — **465,000 đ**) + **Pate Ciao Churu** (`CAT-FD-002` — **35,000 đ**).\n"
            "• **Bổ sung đề kháng**: **Gel Dinh Dưỡng Nutri-Plus Gel Virbac** (`PET-MED-001` — **185,000 đ**).\n"
            "Bạn đang nuôi bé thuộc giống nào để mình tư vấn khẩu phần chi tiết hơn ạ?"
        )

    def _handle_spa(
        self,
        norm_q: str,
        weight_kg: Optional[float],
        active_pet: Optional[Dict[str, Any]],
        intent: str,
        user_name: Optional[str],
    ) -> str:
        prefix = self._greeting_prefix(user_name)

        selected_svc = None
        if any(w in norm_q for w in ["cat tia", "tia long", "grooming", "tao kieu"]):
            selected_svc = "Cắt tỉa & Tạo kiểu lông (Grooming)"
        elif any(w in norm_q for w in ["cao long", "cao ve sinh"]):
            selected_svc = "Cạo lông máu / Cạo vệ sinh"
        elif any(w in norm_q for w in ["trong giu", "khach san", "qua dem", "gui cho", "gui meo"]):
            selected_svc = "Trông giữ thú cưng (1 ngày)"
        elif any(w in norm_q for w in ["kham suc khoe", "tu van dinh duong"]):
            selected_svc = "Khám sức khỏe & Tư vấn dinh dưỡng"
        elif any(w in norm_q for w in ["tam say", "tam cho", "tam meo", "tam "]):
            selected_svc = "Tắm sấy & Vệ sinh tai móng"

        if weight_kg is not None:
            svc = selected_svc or "Tắm sấy & Vệ sinh tai móng"
            calc_price, mult = self.kb.calculate_spa_price(svc, weight_kg, self.kb.spa_services)
            tier_text = "giá gốc (<5kg)" if mult == 1.0 else ("phụ phí +20% (5–10kg)" if mult == 1.2 else "phụ phí +40% (>10kg)")
            return (
                f"{prefix}🛁 **Báo giá dịch vụ {svc} cho bé nặng {weight_kg:g}kg**:\n"
                f"• Giá niêm yết cơ bản: **{int(self.kb.spa_services[svc]):,} đ**\n"
                f"• Mức áp dụng: **{tier_text}** → Thành tiền: **{int(calc_price):,} đ**\n"
                "👉 Bạn có thể đặt lịch ngay tại mục **Dịch vụ Spa** (`/spa`) trên thanh menu — shop sẽ gửi email xác nhận tự động!"
            )

        if selected_svc and intent != "spa_booking_howto":
            base_p = int(self.kb.spa_services[selected_svc])
            return (
                f"{prefix}✨ Dịch vụ **{selected_svc}** có giá cơ bản **{base_p:,} đ** (dưới 5kg).\n"
                f"• Từ 5–10kg: **{int(base_p * 1.2):,} đ** (+20%) | Trên 10kg: **{int(base_p * 1.4):,} đ** (+40%).\n"
                "👉 Đặt lịch nhanh tại trang **Đặt lịch Spa (`/spa`)** hoặc nhắn mình cân nặng của bé để mình tính chuẩn xác nhé!"
            )

        lines = [f"{prefix}🐾 **Bảng giá & Cách đặt lịch Spa tại Meow & Woof**:"]
        for k, v in self.kb.spa_services.items():
            lines.append(f"• **{k}**: **{int(v):,} đ**")
        lines.append("⚖️ *Phụ phí cân nặng*: Dưới 5kg giữ nguyên | 5–10kg (+20%) | Trên 10kg (+40%).")
        lines.append("📅 *Cách đặt lịch*: Chọn **Đặt lịch Spa (`/spa`)** trên menu, nhập tên bé + cân nặng + khung giờ phù hợp và xác nhận ngay.")
        return "\n".join(lines)

    def _format_vouchers_reply(self, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        lines = [f"{prefix}🎁 **Mã giảm giá đang áp dụng ngay tại Giỏ hàng (`/cart`)**:"]
        for v in self.kb.vouchers:
            lines.append(f"• **`{v['code']}`**: {v['desc']}")
        lines.append("👉 Bạn chỉ cần dán mã vào ô *Mã giảm giá Voucher* trước khi bấm Đặt hàng nhé!")
        return "\n".join(lines)

    def _handle_capabilities(self, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        return (
            f"{prefix}🤖 **Tôi được huấn luyện để hỗ trợ bạn mượt mà các chủ đề sau**:\n"
            "1. **Tư vấn mua & tra cứu 32 giống chó mèo**: VD *\"Tôi muốn mua chó\"*, *\"Chó màu trắng\"*, *\"Mèo bắt chuột giỏi\"*, *\"Giá Corgi\"*, *\"So sánh Poodle và Corgi\"*\n"
            "2. **Lọc theo ngân sách & không gian sống**: VD *\"Tìm chó dưới 5 triệu\"*, *\"Mới nuôi ở chung cư nên chọn bé nào?\"*\n"
            "3. **Bảng giá Spa & tính phụ phí theo kg**: VD *\"Chó 12kg tắm sấy hết bao nhiêu?\"*\n"
            "4. **Nuôi dưỡng & Huấn luyện thực tế**: Chi phí 1 tháng, dạy đi vệ sinh, lịch tiêm phòng, triệt sản, chống rụng lông & sơ cứu khi bé ốm.\n"
            "5. **Voucher, Hạng VIP, Bảo hành, Ship & Đơn hàng**: VD *\"Có mã giảm giá nào?\"*, *\"Kiểm tra đơn hàng ở đâu?\"*\n\n"
            "Bạn cứ đặt câu hỏi tự nhiên, mình luôn sẵn sàng hỗ trợ bạn ngay!"
        )

    def _handle_buy_category(self, pet_type: str, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        if pet_type == "Chó":
            return (
                f"{prefix}🐶 **Chào mừng bạn đến chọn bé Cún tại Meow & Woof!** (Hiện có đủ **20 giống Chó cảnh thuần chủng**, giá từ **4,200,000 đ – 12,500,000 đ**):\n"
                "• **Nhỏ gọn, dễ nuôi, hợp chung cư**: Chihuahua (**4,200,000 đ**), Lạp Xưởng (**4,300,000 đ**), Pug Mặt Xệ (**4,500,000 đ**), Poodle Tiny (**4,800,000 đ**)\n"
                "• **Hot trend, siêu đáng yêu**: Corgi Chân Lùn (**7,900,000 đ**), Phốc Sóc Trắng Tuyết (**7,200,000 đ**), Bichon Frise (**6,900,000 đ**), Shiba Inu (**9,500,000 đ**)\n"
                "• **Năng động / giống lớn**: Golden Retriever (**6,200,000 đ**), Husky (**7,500,000 đ**), Alaska (**8,500,000 đ**), Samoyed (**8,800,000 đ**)\n"
                "🛡️ *Cam kết*: Đã tiêm 1-2 mũi, tẩy giun & bảo hành 15 ngày Parvo/Care. Áp mã **`GENZVIP20`** giảm thêm tối đa **500,000 đ**!\n"
                "👉 Bạn dự định tìm bé **ngân sách khoảng bao nhiêu** hoặc **tên giống nào** (VD *\"Corgi\"*, *\"Chó dưới 5 triệu\"*) để mình gửi chi tiết nhé?"
            )
        if pet_type == "Mèo":
            return (
                f"{prefix}🐱 **Meow & Woof hiện có sẵn 12 giống Mèo cảnh thuần chủng** (từ **3,800,000 đ – 13,500,000 đ**, sạch sẽ & tự đi cát):\n"
                "• **Giá mềm, dễ nuôi**: Mèo Xiêm (**3,800,000 đ**), Mèo Anh Lông Ngắn ALN (**4,500,000 đ**), Mèo Mỹ Lông Ngắn (**4,900,000 đ**)\n"
                "• **Lông xù, quý tộc**: Mèo Anh Lông Dài ALD (**5,200,000 đ**), Tai Cụp Scottish (**5,600,000 đ**), Ba Tư (**5,800,000 đ**), Ragdoll Mắt Xanh (**7,500,000 đ**)\n"
                "• **Độc lạ, cá tính**: Chân Ngắn Munchkin (**8,200,000 đ**), Bengal Vân Báo (**8,900,000 đ**), Maine Coon (**11,500,000 đ**), Sphynx (**13,500,000 đ**)\n"
                "🛡️ *Cam kết*: Kèm sổ tiêm phòng, bảo hành 15 ngày & tặng ưu đãi mã **`GENZVIP20`** (giảm tối đa 500,000 đ)!\n"
                "👉 Bạn thích bé nào hoặc muốn lọc theo ngân sách (VD *\"Mèo dưới 6 triệu\"*) ạ?"
            )
        return (
            f"{prefix}🐾 **Meow & Woof hiện có 32 giống Chó Mèo cảnh thuần chủng** sẵn sàng về nhà mới:\n"
            "• **20 giống Chó cảnh** (**4,200,000 đ – 12,500,000 đ**): Nổi bật có Poodle, Pug, Corgi, Phốc Sóc, Shiba, Golden, Husky, Samoyed.\n"
            "• **12 giống Mèo cảnh** (**3,800,000 đ – 13,500,000 đ**): Nổi bật có Mèo Anh Lông Ngắn, Tai Cụp Scottish, Ragdoll, Ba Tư, Munchkin, Xiêm.\n"
            "🎁 Dùng mã **`GENZVIP20`** giảm **20%** (tối đa **500,000 đ**) + **`FREESHIP30K`** khi đặt hàng trên web!\n"
            "👉 Bạn đang muốn tìm **Chó** hay **Mèo**, và tầm ngân sách khoảng bao nhiêu để mình gợi ý chuẩn nhất ạ?"
        )

    def _handle_rag_matches(
        self,
        raw_q: str,
        matches: List[Dict[str, Any]],
        pet_type: Optional[str],
        user_name: Optional[str],
    ) -> str:
        prefix = self._greeting_prefix(user_name)
        label = pet_type if pet_type in ("Chó", "Mèo") else "thú cưng / sản phẩm"
        lines = [f"{prefix}🔎 **Dựa trên mô tả của bạn (*\"{raw_q.strip()[:50]}\"*), các {label} phù hợp nhất tại Meow & Woof là**:"]
        for p in matches:
            lines.append(
                f"• **{p['name']}** (`{p['sku']}`): **{int(p['price']):,} đ** (Còn {p.get('stock', 1)}) — {p.get('description', '')}"
            )
        lines.append("👉 Bạn muốn xem chi tiết, cách chăm sóc hay hướng dẫn đặt mua bé nào trong danh sách trên ạ?")
        return "\n".join(lines)

    def _handle_short_affirmative(self, mem: Dict[str, Any], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        last_pet = mem.get("last_pet")
        if last_pet:
            price = float(last_pet.get("price", 0) or 0)
            disc = min(price * 0.20, 500000.0) if price >= 100000 else 0.0
            final_p = max(0.0, price - disc)
            care_line = (
                "• **Dinh dưỡng khuyên dùng**: Hạt **Royal Canin Indoor 27** (`465,000 đ`) + **Cát Tofu** (`125,000 đ`).\n"
                if last_pet.get("pet_type") == "Mèo"
                else (
                    "• **Dinh dưỡng khuyên dùng**: Hạt **SmartHeart Vị Bò Nướng** (`215,000 đ`) + **Nutri-Plus Gel Virbac** (`185,000 đ`).\n"
                    if last_pet.get("pet_type") == "Chó"
                    else ""
                )
            )
            return (
                f"{prefix}👍 Dưới đây là **thông tin trọn gói cho {last_pet['name']}** (`{last_pet['sku']}`):\n"
                f"• **Giá ưu đãi với mã `GENZVIP20`**: Chỉ còn **{int(final_p):,} đ** (giảm {int(disc):,} đ).\n"
                f"{care_line}"
                f"• **Giao hàng**: {self.kb.policies['shipping']} (Nhập thêm **`FREESHIP30K`** trừ 30,000 đ).\n"
                f"👉 Để đặt giữ bé hoặc tư vấn thêm, bạn vào **Giỏ hàng (`/cart`)** hoặc gọi Hotline **`{self.kb.shop_info['hotline']}`** nhé!"
            )
        return (
            f"{prefix}👍 Tuyệt vời! Bạn muốn mình tư vấn cụ thể hơn về **Chó cảnh**, **Mèo cảnh**, **Bảng giá Spa** hay **Mã giảm giá** ạ?"
        )

    def _handle_pet_age_gender_origin(
        self,
        pet_type: Optional[str],
        topic_pet: Optional[Dict[str, Any]],
        user_name: Optional[str],
    ) -> str:
        prefix = self._greeting_prefix(user_name)
        subject = f"**{topic_pet['name']}**" if topic_pet else ("các bé **Chó/Mèo cảnh**" if pet_type in (None, "BOTH") else f"các bé **{pet_type} cảnh**")
        return (
            f"{prefix}📋 **Thông tin độ tuổi, giới tính & nguồn gốc của {subject} tại Meow & Woof**:\n"
            "• **Độ tuổi xuất chuồng**: Đủ **2 – 2.5 tháng tuổi**, đã cai sữa mẹ, ăn hạt khỏe và hoàn thành 1–2 mũi vắc xin + tẩy giun.\n"
            "• **Giới tính & Màu lông**: Shop luôn có đủ **bé Đực và bé Cái** nhiều màu để bạn lựa chọn theo sở thích.\n"
            "• **Nguồn gốc**: Thuần chủng tuyển chọn từ trại phối uy tín, có sổ theo dõi sức khỏe thú y & bảo hành 15 ngày Parvo/Care.\n"
            f"📹 Muốn xem **ảnh/video thực tế từng bé** ngay lúc này, bạn nhắn Zalo **`{self.kb.shop_info['hotline']}`** hoặc ghé **{self.kb.shop_info['address']}** nhé!"
        )

    def _handle_monthly_cost(
        self,
        pet_type: Optional[str],
        topic_pet: Optional[Dict[str, Any]],
        user_name: Optional[str],
    ) -> str:
        prefix = self._greeting_prefix(user_name)
        if topic_pet and topic_pet.get("pet_type") == "Mèo":
            pet_type = "Mèo"
        elif topic_pet and topic_pet.get("pet_type") == "Chó":
            pet_type = "Chó"

        if pet_type == "Mèo":
            return (
                f"{prefix}💰 **Chi phí nuôi Mèo cảnh trung bình mỗi tháng (~250,000 – 450,000 đ/tháng)**:\n"
                "• **Hạt dinh dưỡng**: Hạt Royal Canin Indoor 27 2kg (**465,000 đ**, ăn được 1.5 – 2 tháng → ~**250,000 đ/tháng**).\n"
                "• **Cát vệ sinh**: 1–2 túi **Cát Tofu 6L** (`125,000 đ`/túi) + vài thanh **Pate Ciao** (`35,000 đ`/gói).\n"
                "• **Tắm rửa**: Mèo rất sạch, 3–4 tuần mới cần tắm **Sữa tắm SOS (`145,000 đ`)** hoặc đi Spa (**150,000 đ**)."
            )
        if pet_type == "Chó":
            return (
                f"{prefix}💰 **Chi phí nuôi Chó cảnh trung bình mỗi tháng (~300,000 – 600,000 đ/tháng)**:\n"
                "• **Thức ăn hạt**: Hạt **SmartHeart 3kg** (`215,000 đ` — bé nhỏ dùng 1.5–2 tháng, bé lớn 1 tháng).\n"
                "• **Chăm sóc & Spa**: Tắm sấy Spa (**150,000 đ**) hoặc tự tắm bằng **Sữa tắm SOS (`145,000 đ`)** dùng cả 4–5 tháng.\n"
                "• **Phòng bệnh định kỳ**: Tẩy giun/nhỏ gáy ve rận chỉ ~100,000–200,000 đ mỗi vài tháng (rất vừa túi tiền sinh viên/gia đình!)."
            )
        return (
            f"{prefix}💰 **Chi phí nuôi thú cưng trung bình 1 tháng tại Việt Nam**:\n"
            "• **Nuôi Mèo**: Khoảng **250,000 – 450,000 đ/tháng** (hạt Royal Canin 465K dùng ~2 tháng + cát Tofu 125K + ít pate Ciao 35K).\n"
            "• **Nuôi Chó nhỏ/vừa**: Khoảng **300,000 – 600,000 đ/tháng** (hạt SmartHeart 215K/3kg + tắm Spa 150K).\n"
            "💡 Dùng mã **`GENZVIP20`** khi mua combo hạt & phụ kiện tại shop sẽ tiết kiệm thêm **20%** nữa đó ạ!"
        )

    def _handle_training_behavior(self, norm_q: str, pet_type: Optional[str], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        if any(w in norm_q for w in ["cao ghe", "sofa", "thau cat"]) or pet_type == "Mèo":
            return (
                f"{prefix}🐱 **Mẹo dạy Mèo đi vệ sinh vào thau cát & không cào sofa**:\n"
                "1. **Đi vệ sinh đúng chỗ**: Đặt thau **Cát Tofu (`125,000 đ`)** ở góc yên tĩnh. Sau khi mèo ăn 15 phút, đặt bé vào thau và bới nhẹ chân trước để tạo phản xạ tự nhiên.\n"
                "2. **Bảo vệ ghế sofa**: Đặt **Trụ Cào Móng Bọc Thừng Sisal** (`CAT-TOY-001` — **190,000 đ**) ngay cạnh sofa, rắc chút cỏ bạc hà (catnip) lên trụ để bé chuyển hướng cào ngay!"
            )
        if any(w in norm_q for w in ["sua", "can dep", "can do"]):
            return (
                f"{prefix}🐶 **Cách khắc phục Cún sủa đêm & cắn đồ dùng**:\n"
                "1. **Giảm cắn phá**: Bé 2–5 tháng đang ngứa nướu thay răng — hãy chuẩn bị **Xương Cao Su Sạch Răng** (`DOG-TOY-001` — **68,000 đ**) để bé gặm thay vì cắn dép.\n"
                "2. **Hạn chế sủa đêm**: Cho bé vận động nhẹ trước khi ngủ, giữ chỗ ngủ ấm áp gần ánh sáng dịu và không dỗ dành khi bé đang sủa đòi ra chuồng (đợi bé im mới thưởng)."
            )
        return (
            f"{prefix}🐾 **Quy tắc vàng dạy Cún đi vệ sinh đúng chỗ & nghe lệnh trong 7 ngày**:\n"
            "1. **Khung giờ vàng**: Đưa bé ra đúng khay vệ sinh ngay sau khi **ngủ dậy**, sau **bữa ăn 15–20 phút** và trước khi ngủ.\n"
            "2. **Thưởng ngay lập tức**: Khi bé đi đúng chỗ, khen nhỏ nhẹ + thưởng 1 miếng bánh nhỏ; nếu lỡ đi sai tuyệt đối không quát mắng to, chỉ lau sạch bằng dung dịch khử mùi.\n"
            "3. **Gặm nhai chống phá đồ**: Trang bị **Xương Cao Su (`68,000 đ`)** cho cún hoặc **Trụ Cào Móng (`190,000 đ`)** cho mèo nhé!"
        )

    def _handle_shedding_grooming(self, norm_q: str, pet_type: Optional[str], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        return (
            f"{prefix}✨ **Bí quyết chăm lông, giảm rụng lông & khử mùi cho thú cưng**:\n"
            "• **Tần suất tắm chuẩn**: Chó tắm **7–10 ngày/lần**; Mèo tự liếm sạch nên **3–4 tuần/lần** là lý tưởng (tắm quá dày dễ khô da rụng lông thêm).\n"
            "• **Dưỡng lông từ trong & ngoài**: Bổ sung hạt giàu Omega 3 & 6 (**SmartHeart `215,000 đ`** / **Royal Canin `465,000 đ`**), dùng **Sữa tắm SOS (`145,000 đ`)** và sấy khô kỹ kẽ chân/tai sau tắm.\n"
            "• **Vệ sinh tai, cắt móng & chải lông chết**: 2 tuần/lần hoặc đặt gói **Tắm sấy & Vệ sinh tai móng (`150,000 đ`)** tại `/spa` để KTV làm sạch tuyến hôi và lông rối cực êm nhé!"
        )

    def _handle_vaccination_schedule(
        self,
        pet_type: Optional[str],
        topic_pet: Optional[Dict[str, Any]],
        user_name: Optional[str],
    ) -> str:
        prefix = self._greeting_prefix(user_name)
        return (
            f"{prefix}💉 **Lịch tiêm phòng & tẩy giun chuẩn thú y cho Chó Mèo**:\n"
            "• **Mũi 1 (6–8 tuần tuổi)**: Chó tiêm 5 bệnh / Mèo tiêm 3–4 bệnh cơ bản.\n"
            "• **Mũi 2 & Mũi 3 (cách nhau 3–4 tuần)**: Tiêm nhắc lại 7 bệnh (chó) hoặc 4 bệnh (mèo) để tạo miễn dịch trọn vẹn.\n"
            "• **Tiêm phòng Dại**: Từ **12–16 tuần tuổi** (nhắc lại mỗi năm 1 lần).\n"
            "• **Tẩy giun**: Dưới 6 tháng mỗi **1 tháng/lần**; trên 6 tháng mỗi **3–6 tháng/lần**.\n"
            "🛡️ *An tâm*: 100% bé đón tại **Meow & Woof** đã được **tiêm sẵn 1–2 mũi + tẩy giun** và có **sổ theo dõi thú y** kèm theo!"
        )

    def _handle_spay_neuter(self, pet_type: Optional[str], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        return (
            f"{prefix}🩺 **Tư vấn Triệt sản & Sinh sản cho Chó Mèo**:\n"
            "• **Độ tuổi triệt sản lý tưởng**: Mèo từ **5–7 tháng tuổi**; Chó từ **6–12 tháng tuổi** (sau khi tiêm đủ các mũi vắc xin).\n"
            "• **Lợi ích**: Hết tình trạng mèo gào đực kêu đêm / đi tiểu đánh dấu, giảm stress và phòng ngừa viêm tử cung hoặc u tuyến vú.\n"
            "• **Phối giống & Mang thai**: Nếu muốn cho bé sinh sản, nên đợi từ lần động dục thứ 2 (khoảng 10–12 tháng tuổi); thời gian mang thai trung bình của chó mèo khoảng **58–65 ngày**."
        )

    def _handle_pet_naming(self, pet_type: Optional[str], user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        return (
            f"{prefix}🏷️ **Gợi ý những cái tên cực cute, dễ gọi giúp bé nhớ tên nhanh**:\n"
            "• **Kiểu đồ ăn ngọt ngào**: *Mochi, Bánh Bao, Bơ, Sữa, Latte, Kem, Khoai Tây, Xúc Xích, Kẹo*\n"
            "• **Kiểu tiếng Việt thuần thân thương**: *Bông, Mực, Cún, Lu, Bi, Tít, Mướp, Đậu, Xù*\n"
            "• **Kiểu tiếng Anh sang xịn**: *Milo, Coco, Bella, Loki, Daisy, Leo, Ruby, Simba, Teddy*\n"
            "💡 Mẹo: Chọn tên **1–2 âm tiết** có vần mở (*Bơ, Mochi, Milo*) để bé phản xạ quay lại ngay khi bạn gọi nhé!"
        )

    def _handle_cohabitation(self, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        return (
            f"{prefix}🤝 **Cách nuôi chung nhiều bé (Chó + Mèo hoặc Mèo mới + Mèo cũ) hòa thuận không đánh nhau**:\n"
            "1. **Cách ly làm quen mùi (3–5 ngày đầu)**: Cho bé mới ở phòng/chuồng riêng, tráo khăn nằm hoặc đồ chơi qua lại để 2 bé quen mùi nhau trước.\n"
            "2. **Cho nhìn mặt qua khe/lưới + thưởng pate**: Dùng thanh **Pate Ciao (`35,000 đ`)** đút song song cho cả 2 bé để tạo ấn tượng tích cực.\n"
            "3. **Bố trí tách biệt đồ dùng**: Dùng 2 bát ăn và 2 thau cát riêng trong 2 tuần đầu để tránh tranh giành lãnh thổ nhé!"
        )

    def _handle_pet_list_menu(self, raw_q: str, norm_q: str, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        ptype = self._detect_pet_type_intent(raw_q, norm_q)
        dogs = self.kb.search_pets(category="Chó", pets_only=True)
        cats = self.kb.search_pets(category="Mèo", pets_only=True)

        if ptype == "Mèo":
            cat_names = ", ".join(p.get("breed", "").replace("Mèo ", "") for p in cats)
            return (
                f"{prefix}🐱 **Shop hiện có đầy đủ {len(cats)} giống Mèo cảnh thuần chủng** (từ **3,800,000 đ** đến **13,500,000 đ**):\n"
                f"• {cat_names}.\n"
                "👉 Bạn thích bé nào (VD *Anh Lông Ngắn, Ragdoll, Tai Cụp, Xiêm...*) để mình báo giá & tình trạng kho nhé!"
            )

        if ptype == "Chó":
            dog_names = ", ".join(p.get("breed", "").replace("Chó ", "") for p in dogs)
            return (
                f"{prefix}🐶 **Shop hiện có đầy đủ {len(dogs)} giống Chó cảnh thuần chủng** (từ **4,200,000 đ** đến **12,500,000 đ**):\n"
                f"• {dog_names}.\n"
                "👉 Bạn đang nhắm bé nào (VD *Poodle, Corgi, Phốc Sóc, Shiba, Pug...*) để mình gửi thông tin chi tiết?"
            )

        return (
            f"{prefix}🐾 **Danh mục Meow & Woof hiện có 42 sản phẩm**:\n"
            f"• **20 giống Chó cảnh** (**4.2M – 12.5M đ**): Poodle, Corgi, Phốc Sóc, Shiba, Golden, Pug, Alaska, Husky, Samoyed...\n"
            f"• **12 giống Mèo cảnh** (**3.8M – 13.5M đ**): Anh Lông Ngắn (ALN), Tai Cụp Scottish, Ragdoll, Ba Tư, Munchkin, Bengal, Xiêm...\n"
            "• **10+ Thức ăn, Phụ kiện, Đồ chơi & Y tế**: Hạt Royal Canin, SmartHeart, Ciao Churu, Cát Tofu, Balo, Virbac, Frontline Plus.\n"
            "👉 Bạn muốn xem chi tiết nhóm nào ạ?"
        )

    def _handle_supplies_list(self, user_name: Optional[str]) -> str:
        prefix = self._greeting_prefix(user_name)
        supplies = [p for p in self.kb.pets if p.get("category") not in ("Chó cảnh", "Mèo cảnh")]
        lines = [f"{prefix}🛍️ **Thức ăn, Phụ kiện, Vệ sinh & Y tế hiện có tại shop**:"]
        for s in supplies:
            lines.append(f"• **{s['name']}** (`{s['sku']}`): **{int(s['price']):,} đ**")
        lines.append("🎁 Dùng mã **`GENZVIP20`** giảm **20%** cho đơn từ 100K hoặc **`MEOW50K`** giảm **50K** cho đơn từ 200K nhé!")
        return "\n".join(lines)

    def _handle_smalltalk(self, raw_q: str, user_name: Optional[str]) -> str:
        norm = normalize_vi(raw_q)
        call_name = f"**{user_name}**" if user_name else "bạn"
        if any(w in norm for w in ["an com", "ngu chua"]):
            return (
                f"Haha cảm ơn {call_name} đã hỏi thăm nha! ☕ Mình chạy bằng điện và tri thức thú cưng nên trực 24/7 không biết đói luôn.\n"
                "Không biết hôm nay bạn muốn tìm bé cún/mèo nào hay đặt lịch Spa cho boss ở nhà không ạ? 🐾"
            )
        if any(w in norm for w in ["nguoi yeu", "chuyen cuoi", "hat ", "lam tho", "chan qua"]):
            return (
                f"Mình chỉ có 'người thương' là mấy bé cún mèo mũm mĩm thôi {call_name} ơi! 🐶🐱\n"
                "Nếu đang buồn chán, ngắm thử mấy bé **Corgi mông trái tim** hay **Mèo Ragdoll mắt xanh** bên shop đảm bảo vui lên liền — bạn muốn xem thử không?"
            )
        return (
            f"Câu hỏi thú vị quá {call_name} ơi! 😄 Tuy nhiên chuyên môn chính của mình là tư vấn Chó Mèo, Spa và phụ kiện tại **Meow & Woof**.\n"
            "Khi nào bạn cần chọn giống thú cưng, tính giá tắm sấy Spa hay săn mã giảm giá, cứ hỏi mình ngay nha! 🐾"
        )

    def _handle_out_of_scope(self, raw_q: str, user_name: Optional[str], last_assistant_reply: str) -> str:
        short_q = raw_q.strip()[:55]
        call_name = f"**{user_name}**" if user_name else "bạn"
        already_oos = "chưa rõ ý của câu" in last_assistant_reply or "nằm ngoài dữ liệu" in last_assistant_reply
        if already_oos:
            return (
                f"Mình vẫn chưa nắm rõ yêu cầu *\"{short_q}\"* của {call_name} ạ 😅.\n"
                "Bạn thử gõ ngắn gọn từ khóa như: *\"Giá Corgi\"*, *\"Chó dưới 5 triệu\"*, *\"Bảng giá Spa\"*, "
                "*\"Chó bị tiêu chảy\"*, hoặc gọi trực tiếp Hotline **`0905.123.456`** để nhân viên tư vấn 1-1 nhé!"
            )
        return (
            f"Xin lỗi {call_name}, mình chưa rõ ý của câu *\"{short_q}\"* hoặc nội dung này nằm ngoài dữ liệu của **Meow & Woof** 😅.\n\n"
            "Mình có thể hỗ trợ bạn nhanh các vấn đề sau:\n"
            "• *\"Shop có chó Corgi / Poodle / Mèo Anh lông ngắn không?\"*\n"
            "• *\"Bảng giá Spa (hoặc Chó 10kg tắm bao nhiêu)?\"*\n"
            "• *\"Có mã giảm giá hay chính sách bảo hành gì không?\"*"
        )


# =============================================================================
# 5. LỚP AI ĐIỀU HÀNH CHÍNH (PETSHOP AI ADVISOR)
# =============================================================================

class PetShopAIAdvisor:
    """Class trung tâm tích hợp Gemini 3.8 Flash + Trained NLP Classifier + Memory RAG."""

    def __init__(self, api_key: Optional[str] = None):
        self.kb = PetShopKnowledgeBase()
        self.classifier = TrainedIntentClassifier()
        self.gemini = GeminiFlashAdvisor(api_key=api_key)
        self.fallback = SmartSemanticFallbackAdvisor(self.kb, classifier=self.classifier)
        self.conversation_history: List[Dict[str, str]] = []

    def ask(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Tư vấn câu hỏi của khách hàng qua Gemini 3.8 Flash hoặc Trained Scenario Engine."""
        active_history = history if history is not None else self.conversation_history
        system_context = self.kb.build_full_system_context()
        situation_hint = self.fallback.build_situation_hint(query, active_history)

        reply_text, model_info = self.gemini.generate(
            query,
            system_context,
            active_history,
            situation_hint=situation_hint,
        )

        if reply_text:
            final_reply = reply_text
            engine_used = f"Google Gemini ({model_info})"
        else:
            final_reply = self.fallback.consult(query, history=active_history)
            engine_used = f"Trained NLP Engine ({model_info})"

        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": final_reply})

        return {
            "reply": final_reply,
            "engine": engine_used,
            "model": "gemini-3.8-flash",
            "situation_hint": situation_hint,
        }


# =============================================================================
# 6. CHẠY THỬ NGHIỆM CLI
# =============================================================================

if __name__ == "__main__":
    advisor = PetShopAIAdvisor()
    print(
        f"=== TRỢ LÝ AI MEOW & WOOF (Trained Intents: {len(advisor.classifier.intents)}, "
        f"Patterns: {len(advisor.classifier.doc_vectors)}) ==="
    )
    while True:
        try:
            q = input("\nBạn: ").strip()
            if not q or q.lower() in ["exit", "quit"]:
                break
            res = advisor.ask(q)
            print(f"\nAI [{res['engine']}]:\n{res['reply']}")
        except (KeyboardInterrupt, EOFError):
            break
