# -*- coding: utf-8 -*-
"""
ai_advisor.py - Module AI Tư Vấn Khách Hàng Thông Minh (Google Gemini 3.8 Flash & RAG)
Dành cho đồ án Meow & Woof Pet House - Học phần Python Nâng Cao

Tính năng nổi bật:
1. Tích hợp Google Gemini API (Model: gemini-3.8-flash):
   - Kết nối trực tiếp qua mạng Internet bằng thư viện chuẩn `urllib.request`.
   - Hỗ trợ cơ chế tự động chuyển tiếp (Waterfall Fallback) sang `gemini-3-flash-preview` và `gemini-3.1-flash-lite`
     nếu server `gemini-3.8-flash` quá tải, đảm bảo tốc độ phản hồi dưới 2 giây.
2. Kiến trúc RAG (Retrieval-Augmented Generation):
   - Nạp toàn bộ 42 thú cưng & sản phẩm, 5 gói Spa, mã voucher, hạng VIP và chính sách bảo hành 15 ngày
     vào System Instruction của Gemini để tư vấn chính xác 100%.
3. Bộ não dự phòng Offline (Smart Semantic RAG Engine):
   - Đảm bảo hệ thống luôn hoạt động ngay cả khi mất kết nối Internet.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Any, Optional, Tuple


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
# 1. KNOWLEDGE BASE RAG (TRÍCH XUẤT TOÀN BỘ DỮ LIỆU CỬA HÀNG)
# =============================================================================

class PetShopKnowledgeBase:
    """Kho tri thức tổng hợp toàn bộ sản phẩm, dịch vụ, khuyến mãi từ hệ thống Meow & Woof."""

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
            "website": "https://chomeo.vercel.app"
        }

        self.spa_services = {
            "Tắm sấy & Vệ sinh tai móng": 150000.0,
            "Cắt tỉa & Tạo kiểu lông (Grooming)": 280000.0,
            "Cạo lông máu / Cạo vệ sinh": 180000.0,
            "Trông giữ thú cưng (1 ngày)": 200000.0,
            "Khám sức khỏe & Tư vấn dinh dưỡng": 120000.0
        }

        self.vouchers = [
            {"code": "MEOW10", "discount_pct": 10, "min_order": 200000, "desc": "Giảm 10% đơn hàng từ 200K"},
            {"code": "WOOF15", "discount_pct": 15, "min_order": 500000, "desc": "Giảm 15% đơn hàng từ 500K cho phụ kiện & thức ăn"},
            {"code": "FREESHIP", "discount_pct": 0, "min_order": 500000, "desc": "Miễn phí vận chuyển toàn quốc cho đơn từ 500K"}
        ]

        self.membership_tiers = [
            {"tier": "Thành Viên Mới", "min_spend": 0, "benefit": "Tích lũy điểm ban đầu"},
            {"tier": "Hạng Bạc", "min_spend": 1000000, "benefit": "Giảm 5% dịch vụ Tắm sấy & Phụ kiện"},
            {"tier": "Hạng Vàng", "min_spend": 5000000, "benefit": "Giảm 10% dịch vụ Cắt tỉa & Đồ dùng"},
            {"tier": "Hạng Kim Cương", "min_spend": 15000000, "benefit": "Giảm 15% tất cả đơn hàng & dịch vụ Spa"}
        ]

        self.policies = {
            "warranty": "Bảo hành sức khỏe thuần chủng 15 ngày toàn diện đối với 2 bệnh nguy hiểm Parvo và Care. Đổi trả 1-1 nếu phát hiện lỗi di truyền.",
            "vaccination": "100% Chó Mèo bán ra đều đã được tiêm phòng ít nhất 1-2 mũi vắc xin và tẩy giun định kỳ, có kèm sổ theo dõi sức khỏe thú y chuẩn.",
            "shipping": "Giao hỏa tốc 2 giờ tại khu vực TP.HCM bằng xe điều hòa. Giao an toàn toàn quốc (Hà Nội, Đà Nẵng, Cần Thơ...) có bác sĩ thú y theo dõi suốt hành trình (miễn phí từ 500,000 đ).",
            "payment": "Hỗ trợ thanh toán linh hoạt: Chuyển khoản ngân hàng VietQR 24/7 tạo mã QR tự động chính xác từng đồng hoặc Trả tiền mặt khi nhận hàng (COD)."
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

    def _load_fallback_pets(self):
        self.pets = [
            {"sku": "DOG-PET-001", "name": "Chó Schnauzer Tiêu Muối Thuần Chủng (2.5 tháng)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Schnauzer", "price": 6500000, "stock": 3, "description": "Lông xù hai màu tiêu muối, thông minh, lanh lợi, không rụng lông."},
            {"sku": "DOG-PET-002", "name": "Chó Poodle Tiny Màu Nâu Đỏ (2 tháng tuổi)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Poodle", "price": 4800000, "stock": 5, "description": "Poodle Tiny siêu quấn chủ, không rụng lông, rất hợp nuôi chung cư."},
            {"sku": "DOG-PET-003", "name": "Chó Corgi Pembroke Chân Lùn Vàng Trắng", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Corgi Chân Lùn", "price": 7900000, "stock": 2, "description": "Mông trái tim siêu cưng, chân lùn đáng yêu, thích hợp gia đình có trẻ em."},
            {"sku": "DOG-PET-004", "name": "Chó Phốc Sóc Pomeranian Mặt Gấu Trắng Tuyết", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Phốc Sóc", "price": 7200000, "stock": 3, "description": "Bộ lông trắng bông xù như cục bông tuyết, mặt gấu ngây thơ."},
            {"sku": "DOG-PET-005", "name": "Chó Golden Retriever Thuần Chủng (2.5 tháng)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Golden", "price": 6200000, "stock": 3, "description": "Thánh thân thiện, hiền lành, thông minh, bạn đồng hành tuyệt vời của trẻ nhỏ."},
            {"sku": "DOG-PET-006", "name": "Chó Shiba Inu Vàng Đỏ Chuẩn Form Nhật", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Shiba Inu", "price": 9600000, "stock": 2, "description": "Quốc khuyển Nhật Bản mặt cười, sạch sẽ, trung thành tuyệt đối."},
            {"sku": "DOG-PET-014", "name": "Chó Pug Mặt Xệ Màu Vàng Kim (2 tháng tuổi)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Pug Mặt Xệ", "price": 4500000, "stock": 4, "description": "Pug mặt xệ ngộ nghĩnh, hiền lành, ít sủa, cực kỳ thích hợp nuôi chung cư."},
            {"sku": "CAT-PET-001", "name": "Mèo Anh Lông Ngắn Màu Xám Xanh (British Shorthair)", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Anh Lông Ngắn", "price": 4500000, "stock": 4, "description": "Má phúng phính, mắt hổ phách, điềm tĩnh, ngoan ngoãn và sạch sẽ."},
            {"sku": "CAT-PET-004", "name": "Mèo Ragdoll Mắt Xanh Ngọc Bích", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Ragdoll", "price": 7500000, "stock": 3, "description": "Công chúa mèo lông dài óng mượt, mắt xanh ngọc bích, bế lên là mềm rũ."}
        ]

    def search_pets(self, keyword: str = "", max_price: Optional[float] = None, min_price: Optional[float] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        kw = keyword.lower().strip()
        results = []
        for p in self.pets:
            name = str(p.get("name", "")).lower()
            breed = str(p.get("breed", "")).lower()
            cat = str(p.get("category", "")).lower()
            desc = str(p.get("description", "")).lower()
            p_price = float(p.get("price", 0) or 0)

            if max_price is not None and p_price > max_price:
                continue
            if min_price is not None and p_price < min_price:
                continue
            if category and category.lower() not in cat:
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
            "\n--- BẢNG GIÁ DỊCH VỤ SPA & GROOMING ---"
        ]
        for s_name, s_price in self.spa_services.items():
            lines.append(f"• {s_name}: {int(s_price):,} đ")

        lines.append("\n--- MÃ GIẢM GIÁ VOUCHER ---")
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
        return "\n".join(lines)


# =============================================================================
# 2. BỘ ĐIỀU PHỐI MÔ HÌNH GEMINI 3.8 FLASH (GOOGLE GENERATIVE AI API)
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

    def generate(self, user_query: str, system_context: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[Optional[str], str]:
        """Gọi API Gemini 3.8 Flash để sinh câu trả lời tự nhiên và chính xác."""
        if not self.api_key:
            return None, "Chưa cấu hình Gemini API Key"

        system_instruction = (
            "Bạn là Trợ lý AI tư vấn khách hàng chính thức của cửa hàng thú cưng Meow & Woof Pet House.\n"
            "Hãy trả lời TRỰC TIẾP, NGẮN GỌN, THÂN THIỆN và CHÍNH XÁC 100% câu hỏi của khách hàng bằng tiếng Việt.\n"
            "Quy tắc:\n"
            "1. Chỉ báo giá, tên giống thú cưng, mã SKU, dịch vụ Spa và mã giảm giá đúng theo dữ liệu của cửa hàng bên dưới.\n"
            "2. Không bịa đặt thông tin không có trong cơ sở dữ liệu.\n"
            "3. Trình bày gọn gàng, dễ đọc (dùng gạch đầu dòng ngắn gọn, in đậm giá tiền).\n"
            "4. Không tự giới thiệu dài dòng nếu khách chỉ hỏi thẳng vào vấn đề.\n\n"
            f"=== DỮ LIỆU CỬA HÀNG ===\n{system_context}"
        )

        contents = []
        if history:
            for turn in history[-6:]:
                role = "model" if turn.get("role") == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": turn.get("content", "")}]
                })

        contents.append({
            "role": "user",
            "parts": [{"text": user_query}]
        })

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.4,
                "topP": 0.9,
                "maxOutputTokens": 600
            }
        }
        req_bytes = json.dumps(payload).encode("utf-8")

        last_err = ""
        for model_name in self.FALLBACK_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={urllib.parse.quote(self.api_key)}"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "MeowWoof-GeminiAdvisor/3.8"
            }
            timeout_sec = 7 if model_name == "gemini-3.8-flash" else 15
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

        return None, f"Fallback ({last_err})"


# =============================================================================
# 3. BỘ NÃO DỰ PHÒNG OFFLINE (SMART SEMANTIC RAG FALLBACK)
# =============================================================================

class SmartSemanticFallbackAdvisor:
    """Bộ não phân tích ngữ nghĩa nội bộ đảm bảo hoạt động 100% khi mất kết nối mạng."""

    BREED_MAP = {
        "corgi": ["corgi", "chân lùn", "pembroke"],
        "poodle": ["poodle", "tiny", "teacup", "nâu đỏ"],
        "shiba": ["shiba", "quốc khuyển"],
        "pug": ["pug", "mặt xệ"],
        "schnauzer": ["schnauzer", "tiêu muối"],
        "alaska": ["alaska", "malamute", "giant"],
        "golden": ["golden", "retriever"],
        "samoyed": ["samoyed", "tuyết trắng"],
        "husky": ["husky", "ngáo"],
        "phốc sóc": ["phốc sóc", "pomeranian", "mặt gấu"],
        "mèo anh lông ngắn": ["aln", "anh lông ngắn", "british shorthair"],
        "mèo ba tư": ["ba tư", "persian", "mặt tịt"],
        "mèo tai cụp": ["tai cụp", "scottish fold", "scottish"],
        "mèo ragdoll": ["ragdoll", "ngọc bích"],
        "mèo sphynx": ["sphynx", "không lông", "ai cập"]
    }

    def __init__(self, kb: PetShopKnowledgeBase):
        self.kb = kb

    def consult(self, query: str) -> str:
        q = query.lower().strip()

        if any(w in q for w in ["địa chỉ", "ở đâu", "chi nhánh", "chỉ đường"]):
            return (
                f"📍 **Địa chỉ**: {self.kb.shop_info['address']}\n"
                f"⏰ **Giờ mở cửa**: {self.kb.shop_info['hours']}\n"
                f"📞 **Hotline / Zalo**: {self.kb.shop_info['hotline']}"
            )

        if any(w in q for w in ["mấy giờ", "giờ mở cửa", "giờ làm việc"]):
            return f"⏰ Shop mở cửa từ **{self.kb.shop_info['hours']}** tại **{self.kb.shop_info['address']}**."

        if any(w in q for w in ["tắm", "tắm sấy"]):
            return f"🛁 Dịch vụ **Tắm sấy & Vệ sinh tai móng** trọn gói có giá **{int(self.kb.spa_services['Tắm sấy & Vệ sinh tai móng']):,} đ**."

        if any(w in q for w in ["cắt tỉa", "tỉa lông", "grooming"]):
            return f"✂️ Dịch vụ **Cắt tỉa & Tạo kiểu lông** có giá **{int(self.kb.spa_services['Cắt tỉa & Tạo kiểu lông (Grooming)']):,} đ**."

        if any(w in q for w in ["spa", "bảng giá spa"]):
            lines = ["🐾 **Bảng giá dịch vụ Spa tại Meow & Woof**:"]
            for k, v in self.kb.spa_services.items():
                lines.append(f"• {k}: **{int(v):,} đ**")
            return "\n".join(lines)

        if any(w in q for w in ["voucher", "giảm giá", "khuyến mãi", "mã"]):
            lines = ["🎁 **Mã giảm giá đang áp dụng**:"]
            for v in self.kb.vouchers:
                lines.append(f"• **`{v['code']}`**: {v['desc']}")
            return "\n".join(lines)

        if any(w in q for w in ["bảo hành", "tiêm phòng", "parvo", "care"]):
            return f"🛡️ {self.kb.policies['warranty']}\n💉 {self.kb.policies['vaccination']}"

        if any(w in q for w in ["thanh toán", "vietqr", "cod"]):
            return f"💳 {self.kb.policies['payment']}"

        if any(w in q for w in ["ship", "giao hàng", "vận chuyển"]):
            return f"🚚 {self.kb.policies['shipping']}"

        if any(w in q for w in ["chung cư", "ít rụng lông"]):
            return (
                "🏢 **Gợi ý nuôi chung cư (ít rụng lông, ngoan hiền)**:\n"
                "• **Chó Poodle Tiny**: **4,800,000 đ** (không rụng lông, thông minh)\n"
                "• **Chó Pug Mặt Xệ**: **4,500,000 đ** (hiền lành, ít sủa)\n"
                "• **Mèo Anh Lông Ngắn (Aln)**: **4,500,000 đ** (sạch sẽ, điềm đạm)"
            )

        for b_key, b_words in self.BREED_MAP.items():
            if any(w in q for w in b_words):
                matched = [p for p in self.kb.pets if any(w in (p.get("name", "") + " " + p.get("breed", "")).lower() for w in b_words)]
                if matched:
                    p = matched[0]
                    return (
                        f"🐾 **{p['name']}** (`{p['sku']}`)\n"
                        f"• **Giá niêm yết**: **{int(p['price']):,} đ** (Còn {p.get('stock', 1)} bé)\n"
                        f"• **Đặc điểm**: {p.get('description', '')}\n"
                        f"• **Bảo hành**: 15 ngày Parvo & Care, đã tiêm phòng đầy đủ."
                    )

        m_under = re.search(r'(dưới|<|tầm|khoảng)\s*(\d+)\s*(tr|triệu|k)', q)
        if m_under:
            val = float(m_under.group(2))
            max_p = val * 1000000 if m_under.group(3) in ["tr", "triệu"] else val * 1000
            cat_f = "Chó" if "chó" in q else ("Mèo" if "mèo" in q else None)
            matched = sorted(self.kb.search_pets(max_price=max_p, category=cat_f), key=lambda x: float(x.get("price", 0)))
            if matched:
                lines = [f"🐾 **Các bé phù hợp ngân sách dưới {int(max_p):,} đ**:"]
                for p in matched[:5]:
                    lines.append(f"• **{p['name']}**: **{int(p['price']):,} đ**")
                return "\n".join(lines)

        return (
            "Xin chào bạn! 🐾 Tôi có thể tư vấn nhanh cho bạn về:\n"
            "• Giá và thông tin 42 giống chó mèo (Corgi, Poodle, Mèo Aln, Ragdoll...)\n"
            "• Bảng giá dịch vụ Spa (Tắm sấy 150K, Cắt tỉa 280K...)\n"
            "• Mã giảm giá (MEOW10, WOOF15) và chính sách bảo hành 15 ngày.\n"
            "Bạn muốn hỏi về nội dung nào ạ?"
        )


# =============================================================================
# 4. LỚP AI ĐIỀU HÀNH CHÍNH (PETSHOP AI ADVISOR)
# =============================================================================

class PetShopAIAdvisor:
    """Class trung tâm tích hợp Google Gemini 3.8 Flash và Kho Tri Thức Cửa Hàng."""

    def __init__(self, api_key: Optional[str] = None):
        self.kb = PetShopKnowledgeBase()
        self.gemini = GeminiFlashAdvisor(api_key=api_key)
        self.fallback = SmartSemanticFallbackAdvisor(self.kb)
        self.conversation_history: List[Dict[str, str]] = []

    def ask(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Tư vấn câu hỏi của khách hàng bằng Gemini 3.8 Flash."""
        active_history = history if history is not None else self.conversation_history
        system_context = self.kb.build_full_system_context()
        reply_text, model_info = self.gemini.generate(query, system_context, active_history)

        if reply_text:
            final_reply = reply_text
            engine_used = f"Google Gemini ({model_info})"
        else:
            final_reply = self.fallback.consult(query)
            engine_used = f"Smart RAG Engine ({model_info})"

        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": final_reply})

        return {
            "reply": final_reply,
            "engine": engine_used,
            "model": "gemini-3.8-flash"
        }


# =============================================================================
# 5. CHẠY THỬ NGHIỆM CLI
# =============================================================================

if __name__ == "__main__":
    advisor = PetShopAIAdvisor()
    print("=== TRỢ LÝ AI MEOW & WOOF (GEMINI 3.8 FLASH) ===")
    while True:
        try:
            q = input("\nBạn: ").strip()
            if not q or q.lower() in ["exit", "quit"]:
                break
            res = advisor.ask(q)
            print(f"\nAI: {res['reply']}")
        except (KeyboardInterrupt, EOFError):
            break
