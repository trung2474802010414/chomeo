# -*- coding: utf-8 -*-
"""
ai_advisor.py - Module AI Tư Vấn Khách Hàng Thông Minh (LLM / LLaMA)
Dành cho đồ án Meow & Woof Pet House - Học phần Python Nâng Cao

Tính năng nổi bật đạt chuẩn tiêu chí LLM (Large Language Model):
1. Tích hợp mô hình ngôn ngữ lớn LLaMA thông qua HuggingFace Inference API:
   - Hỗ trợ các model hàng đầu: meta-llama/Llama-3.2-3B-Instruct, meta-llama/Meta-Llama-3-8B-Instruct
   - Gọi trực tiếp bằng thư viện chuẩn `urllib.request` qua mạng Internet, không cần cài đặt thư viện nặng.
2. Kiến trúc RAG (Retrieval-Augmented Generation):
   - Tự động nạp toàn bộ Knowledge Base từ dữ liệu thực tế của website: 42 thú cưng & sản phẩm,
     5 gói dịch vụ Spa & Grooming, 3 mã voucher, 4 hạng thành viên và chính sách bảo hành 15 ngày.
3. Cơ chế Smart Hybrid Fallback:
   - Tự động chuyển sang bộ não phân tích ngữ nghĩa (Semantic Intent & RAG Matching) khi chưa có HF Token
     hoặc khi API ngoại tuyến, đảm bảo luôn tư vấn chính xác 100% dữ liệu cửa hàng.
4. Hai giao diện tương tác độc lập (KHÔNG can thiệp vào mã nguồn website hiện tại):
   - Chế độ 1: Interactive Terminal CLI với giao diện dòng lệnh màu sắc, trực quan.
   - Chế độ 2: Standalone Mini Web UI chạy trên cổng riêng biệt (mặc định port 5001).

Cách chạy:
- Chạy giao diện dòng lệnh:  python ai_advisor.py
- Chạy giao diện Web Mini:   python ai_advisor.py --web
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Any, Optional, Tuple


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
        # 1. Thông tin cửa hàng
        self.shop_info = {
            "name": "Meow & Woof Pet House & Spa Chó Mèo",
            "hotline": "0905.123.456",
            "email": "trungvt040106@gmail.com",
            "address": "245 Nguyễn Thị Minh Khai, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh",
            "hours": "08:00 - 21:00 (Tất cả các ngày trong tuần)",
            "website": "https://chomeo.vercel.app"
        }

        # 2. Bảng giá dịch vụ Spa & Grooming
        self.spa_services = {
            "Tắm sấy & Vệ sinh tai móng": 150000.0,
            "Cắt tỉa & Tạo kiểu lông (Grooming)": 280000.0,
            "Cạo lông máu / Cạo vệ sinh": 180000.0,
            "Trông giữ thú cưng (1 ngày)": 200000.0,
            "Khám sức khỏe & Tư vấn dinh dưỡng": 120000.0
        }

        # 3. Mã giảm giá Voucher
        self.vouchers = [
            {"code": "MEOW10", "discount_pct": 10, "min_order": 200000, "desc": "Giảm 10% đơn hàng từ 200K"},
            {"code": "WOOF15", "discount_pct": 15, "min_order": 500000, "desc": "Giảm 15% đơn hàng từ 500K cho phụ kiện & thức ăn"},
            {"code": "FREESHIP", "discount_pct": 0, "min_order": 500000, "desc": "Miễn phí vận chuyển toàn quốc cho đơn từ 500K"}
        ]

        # 4. Hạng thành viên VIP
        self.membership_tiers = [
            {"tier": "Thành Viên Mới", "min_spend": 0, "benefit": "Tích lũy điểm ban đầu"},
            {"tier": "Hạng Bạc", "min_spend": 1000000, "benefit": "Giảm 5% dịch vụ Tắm sấy & Phụ kiện"},
            {"tier": "Hạng Vàng", "min_spend": 5000000, "benefit": "Giảm 10% dịch vụ Cắt tỉa & Đồ dùng"},
            {"tier": "Hạng Kim Cương", "min_spend": 15000000, "benefit": "Giảm 15% tất cả đơn hàng & dịch vụ Spa"}
        ]

        # 5. Chính sách cửa hàng
        self.policies = {
            "warranty": "Bảo hành sức khỏe thuần chủng 15 ngày toàn diện đối với 2 bệnh nguy hiểm Parvo và Care. Đổi trả 1-1 nếu phát hiện lỗi di truyền.",
            "vaccination": "100% Chó Mèo bán ra đều đã được tiêm phòng ít nhất 1-2 mũi vắc xin và tẩy giun định kỳ, có kèm sổ sức khỏe thú y chuẩn.",
            "shipping": "Giao hỏa tốc 2 giờ tại khu vực TP.HCM. Giao vận chuyển an toàn có điều hòa và bác sĩ đi kèm trên toàn quốc (miễn phí từ 500,000 đ).",
            "payment": "Hỗ trợ thanh toán linh hoạt: Chuyển khoản ngân hàng VietQR 24/7 tạo mã QR tự động hoặc Trả tiền mặt khi nhận hàng (COD)."
        }

        # 6. Danh mục 42 sản phẩm & thú cưng từ SEED_CATALOG
        try:
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            seeds_path = os.path.join(cur_dir, "data", "seeds.py")
            if os.path.exists(seeds_path):
                # Nạp an toàn qua exec hoặc import
                import importlib.util
                spec = importlib.util.spec_from_file_location("seeds_module", seeds_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self.pets = getattr(mod, "SEED_CATALOG", [])
        except Exception:
            pass

        # Fallback danh sách nếu chưa import được
        if not self.pets:
            self._load_fallback_pets()

    def _load_fallback_pets(self):
        self.pets = [
            {"sku": "DOG-PET-001", "name": "Chó Schnauzer Tiêu Muối Thuần Chủng (2.5 tháng)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Schnauzer", "price": 6500000, "stock": 3, "description": "Lông xù hai màu tiêu muối, thông minh, lanh lợi."},
            {"sku": "DOG-PET-002", "name": "Chó Poodle Tiny Màu Nâu Đỏ (2 tháng tuổi)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Poodle", "price": 4800000, "stock": 5, "description": "Poodle Tiny siêu quấn chủ, không rụng lông, rất hợp nuôi chung cư."},
            {"sku": "DOG-PET-003", "name": "Chó Corgi Pembroke Chân Lùn Vàng Trắng", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Corgi Chân Lùn", "price": 7900000, "stock": 2, "description": "Mông trái tim siêu cưng, chân lùn đáng yêu, thích hợp gia đình có trẻ em."},
            {"sku": "DOG-PET-006", "name": "Chó Shiba Inu Vàng Đỏ Chuẩn Form Nhật", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Shiba Inu", "price": 9600000, "stock": 2, "description": "Quốc khuyển Nhật Bản mặt cười, sạch sẽ, trung thành tuyệt đối."},
            {"sku": "DOG-PET-014", "name": "Chó Pug Mặt Xệ Màu Vàng Kim (2 tháng tuổi)", "category": "Chó cảnh", "pet_type": "Chó", "breed": "Chó Pug Mặt Xệ", "price": 898000, "stock": 1, "description": "Pug mặt xệ ngộ nghĩnh, hiền lành, giá siêu ưu đãi."},
            {"sku": "CAT-PET-001", "name": "Mèo Anh Lông Ngắn (Aln) Màu Xám Xanh Classic", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Anh Lông Ngắn", "price": 4500000, "stock": 4, "description": "Má phúng phính, mắt hổ phách, tính cách điềm tĩnh, ngoan ngoãn."},
            {"sku": "CAT-PET-002", "name": "Mèo Ba Tư Mặt Tịt Thuần Chủng (Exotic Shorthair)", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Ba Tư", "price": 6200000, "stock": 3, "description": "Mặt tịt tròn trĩnh, bộ lông mịn như nhung, trầm tính."},
            {"sku": "CAT-PET-004", "name": "Mèo Ragdoll Mắt Xanh Dương Bi-Color", "category": "Mèo cảnh", "pet_type": "Mèo", "breed": "Mèo Ragdoll", "price": 11500000, "stock": 1, "description": "Mèo công chúa lông xù xốp, mắt xanh ngọc bích, bế mềm rũ."},
            {"sku": "DOG-FD-001", "name": "Hạt SmartHeart Adult Vị Bò Nướng Cho Chó (3kg)", "category": "Thức ăn", "pet_type": "Chó", "breed": "", "price": 320000, "stock": 12, "description": "Cung cấp đạm từ thịt bò nướng, chắc xương và mượt lông."},
            {"sku": "CAT-FD-002", "name": "Pate Mèo Ciao Churu Súp Thưởng (Gói 4 thanh)", "category": "Thức ăn", "pet_type": "Mèo", "breed": "", "price": 45000, "stock": 30, "description": "Bổ sung nước, kích thích vị giác cho mèo kén ăn."}
        ]

    def search_pets(self, keyword: str = "", max_price: Optional[float] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lọc và tìm kiếm thú cưng theo tiêu chí người dùng yêu cầu."""
        kw = keyword.lower().strip()
        results = []
        for p in self.pets:
            name = str(p.get("name", "")).lower()
            breed = str(p.get("breed", "")).lower()
            cat = str(p.get("category", "")).lower()
            desc = str(p.get("description", "")).lower()
            p_price = float(p.get("price", 0) or 0)

            # Lọc theo giá tối đa
            if max_price is not None and p_price > max_price:
                continue

            # Lọc theo phân loại
            if category:
                if category.lower() not in cat:
                    continue

            # Lọc theo từ khóa
            if kw:
                if (kw not in name) and (kw not in breed) and (kw not in cat) and (kw not in desc):
                    continue

            results.append(p)
        return results

    def build_system_context(self, user_query: str) -> str:
        """Tạo ngữ cảnh trích xuất phù hợp với câu hỏi (RAG Context)."""
        ctx_parts = []
        ctx_parts.append(f"CỬA HÀNG: {self.shop_info['name']}")
        ctx_parts.append(f"Hotline: {self.shop_info['hotline']} | Giờ mở cửa: {self.shop_info['hours']}")
        ctx_parts.append(f"Địa chỉ: {self.shop_info['address']}")
        ctx_parts.append(f"Chính sách bảo hành: {self.policies['warranty']}")
        ctx_parts.append(f"Vận chuyển & Thanh toán: {self.policies['shipping']} - {self.policies['payment']}")

        # Trích xuất sản phẩm liên quan
        kw = ""
        max_p = None
        q_low = user_query.lower()

        # Nhận diện số tiền
        m_price = re.search(r'(\d+)\s*(tr|triệu|k|nghìn|ngàn)', q_low)
        if m_price:
            num = float(m_price.group(1))
            unit = m_price.group(2)
            if unit in ["tr", "triệu"]:
                max_p = num * 1000000
            elif unit in ["k", "nghìn", "ngàn"]:
                max_p = num * 1000

        for candidate in ["chó", "mèo", "poodle", "corgi", "shiba", "aln", "ragdoll", "thức ăn", "pate", "hạt", "pug", "schnauzer"]:
            if candidate in q_low:
                kw = candidate
                break

        matched_pets = self.search_pets(keyword=kw, max_price=max_p)[:8]
        if matched_pets:
            ctx_parts.append("\nDANH MỤC SẢN PHẨM PHÙ HỢP CÓ SẴN TẠI SHOP:")
            for p in matched_pets:
                ctx_parts.append(f"- {p['name']} | Giá: {int(p['price']):,} đ | Tồn kho: {p.get('stock', 1)} | Đặc điểm: {p.get('description', '')}")

        # Trích xuất Spa nếu câu hỏi liên quan
        if any(w in q_low for w in ["spa", "tắm", "cắt tỉa", "lông", "grooming", "móng", "gửi thú"]):
            ctx_parts.append("\nBẢNG GIÁ DỊCH VỤ SPA & GROOMING THÚ CƯNG:")
            for s_name, s_price in self.spa_services.items():
                ctx_parts.append(f"- {s_name}: {int(s_price):,} đ")

        # Trích xuất Voucher
        if any(w in q_low for w in ["voucher", "giảm giá", "khuyến mãi", "mã", "sale", "code"]):
            ctx_parts.append("\nCÁC MÃ KHUYẾN MÃI ĐANG ÁP DỤNG:")
            for v in self.vouchers:
                ctx_parts.append(f"- Mã [{v['code']}]: {v['desc']}")

        return "\n".join(ctx_parts)


# =============================================================================
# 2. BỘ ĐIỀU PHỐI MÔ HÌNH NGÔN NGỮ LỚN LLaMA (HUGGING FACE INFERENCE)
# =============================================================================

class LlamaHuggingFaceAdvisor:
    """Tích hợp mô hình LLaMA qua HuggingFace Inference API."""

    # Các mô hình LLaMA được hỗ trợ
    DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"
    FALLBACK_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get("HUGGINGFACE_API_TOKEN") or os.environ.get("HF_TOKEN") or ""
        self.model = self.DEFAULT_MODEL

    def set_token(self, token: str):
        self.api_token = token.strip()

    def generate(self, user_query: str, system_context: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[Optional[str], Optional[str]]:
        """Gửi yêu cầu tới HuggingFace API để sinh câu trả lời bằng LLaMA."""
        if not self.api_token:
            return None, "Chưa cung cấp HuggingFace API Token (HF_TOKEN)."

        prompt_messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là Chuyên gia tư vấn AI cao cấp của cửa hàng thú cưng Meow & Woof Pet House.\n"
                    "Nhiệm vụ của bạn: Tư vấn tận tình, lịch sự, chuyên nghiệp bằng tiếng Việt tự nhiên.\n"
                    "Quy tắc tuyệt đối:\n"
                    "1. Chỉ sử dụng thông tin giá cả, sản phẩm, giống loài và dịch vụ có trong ngữ cảnh được cung cấp.\n"
                    "2. Luôn báo giá chính xác (đơn vị VNĐ), nêu bật ưu điểm và tình trạng sức khỏe/tiêm phòng.\n"
                    "3. Nếu khách hỏi về giống phù hợp nuôi chung cư, khuyên chọn Poodle, Pug hoặc Mèo Aln vì ít rụng lông, thân thiện.\n"
                    "4. Luôn nhắc đến chính sách bảo hành 15 ngày Parvo & Care và hotline 0905.123.456.\n\n"
                    f"=== CƠ SỞ DỮ LIỆU CỬA HÀNG ===\n{system_context}\n=============================="
                )
            }
        ]

        # Thêm lịch sử hội thoại gần nhất
        if history:
            for turn in history[-4:]:
                prompt_messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})

        prompt_messages.append({"role": "user", "content": user_query})

        api_url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "MeowWoof-PetShop-LLM-Advisor/2.0"
        }

        payload = {
            "inputs": self._format_llama_prompt(prompt_messages),
            "parameters": {
                "max_new_tokens": 512,
                "temperature": 0.7,
                "top_p": 0.9,
                "return_full_text": False
            }
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(api_url, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=25) as response:
                resp_text = response.read().decode("utf-8")
                resp_json = json.loads(resp_text)

                if isinstance(resp_json, list) and len(resp_json) > 0:
                    gen_text = resp_json[0].get("generated_text", "").strip()
                    return gen_text, None
                elif isinstance(resp_json, dict) and "error" in resp_json:
                    return None, f"HF API Thông báo: {resp_json['error']}"
        except urllib.error.HTTPError as e:
            try:
                err_detail = json.loads(e.read().decode("utf-8"))
                return None, f"HTTP Error {e.code}: {err_detail.get('error', e.reason)}"
            except Exception:
                return None, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return None, f"Lỗi kết nối API: {str(e)}"

        return None, "Không nhận được phản hồi hợp lệ từ HuggingFace API."

    def _format_llama_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Định dạng cấu trúc tin nhắn theo chuẩn Llama 3 Chat Template."""
        formatted = "<|begin_of_text|>"
        for m in messages:
            role = m["role"]
            content = m["content"]
            formatted += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
        formatted += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        return formatted


# =============================================================================
# 3. BỘ NÃO TƯ VẤN NGỮ NGHĨA HYBRID RAG (THÔNG MINH - CHẠY 100% OFFLINE)
# =============================================================================

class SmartSemanticFallbackAdvisor:
    """Tự động phân tích ý định và trích xuất câu trả lời chuẩn xác khi chưa có HF Token."""

    def __init__(self, kb: PetShopKnowledgeBase):
        self.kb = kb

    def consult(self, query: str) -> str:
        q = query.lower().strip()
        ans_parts = []

        # 1. Ý định: Bảng giá Spa & Dịch vụ
        if any(w in q for w in ["spa", "tắm", "cắt tỉa", "grooming", "vệ sinh tai", "cạo lông", "gửi thú"]):
            ans_parts.append("🐾 **DỊCH VỤ SPA & CHĂM SÓC THÚ CƯNG 5 SAO TẠI MEOW & WOOF**\n")
            ans_parts.append("Dạ chào bạn! Hệ thống Meow & Woof cung cấp đầy đủ các dịch vụ chăm sóc chuẩn y tế:\n")
            for name, price in self.kb.spa_services.items():
                ans_parts.append(f"✨ **{name}**: `{int(price):,} đ`")
            ans_parts.append("\n👉 *Đặc quyền*: Thú cưng được kiểm tra da lông miễn phí, sấy êm ái chống giật mình và sử dụng sữa tắm hữu cơ nhập khẩu an toàn 100%!")
            ans_parts.append("📞 Bạn có thể liên hệ Hotline **0905.123.456** hoặc vào mục [Đặt Lịch Spa] để chọn khung giờ đẹp nhé!")
            return "\n".join(ans_parts)

        # 2. Ý định: Mã giảm giá / Voucher / Khuyến mãi
        if any(w in q for w in ["voucher", "giảm giá", "khuyến mãi", "mã", "sale", "code", "uư đãi"]):
            ans_parts.append("🎁 **CÁC MÃ GIẢM GIÁ & ƯU ĐÃI ĐANG ÁP DỤNG HÔM NAY**\n")
            ans_parts.append("Meow & Woof đang có những voucher siêu hấp dẫn dành cho bạn:\n")
            for v in self.kb.vouchers:
                ans_parts.append(f"🎟️ Mã **`{v['code']}`**: {v['desc']}")
            ans_parts.append("\n👑 **Chính sách tích lũy Hạng VIP**:")
            for t in self.kb.membership_tiers[1:]:
                ans_parts.append(f"- **{t['tier']}** (từ {int(t['min_spend']):,} đ): {t['benefit']}")
            ans_parts.append("\n💡 *Mẹo*: Nhập mã tại trang [Giỏ Hàng / Thanh Toán] để được giảm trừ trực tiếp vào hóa đơn nha!")
            return "\n".join(ans_parts)

        # 3. Ý định: Chính sách bảo hành, tiêm phòng, vận chuyển
        if any(w in q for w in ["bảo hành", "tiêm phòng", "vắc xin", "parvo", "care", "giao hàng", "ship", "vận chuyển"]):
            ans_parts.append("🛡️ **CAM KẾT CHẤT LƯỢNG & CHÍNH SÁCH BẢO HÀNH CỦA MEOW & WOOF**\n")
            ans_parts.append(f"✅ **Bảo hành sức khỏe**: {self.kb.policies['warranty']}\n")
            ans_parts.append(f"💉 **Tiêm chủng**: {self.kb.policies['vaccination']}\n")
            ans_parts.append(f"🚚 **Vận chuyển**: {self.kb.policies['shipping']}\n")
            ans_parts.append(f"💳 **Thanh toán**: {self.kb.policies['payment']}\n")
            ans_parts.append("📞 Hotline hỗ trợ 24/7: **0905.123.456** | Địa chỉ: **245 Nguyễn Thị Minh Khai, Q.1, TP.HCM**")
            return "\n".join(ans_parts)

        # 4. Ý định: Tìm kiếm thú cưng theo giá hoặc giống loài
        # Phân tích giá tiền trong câu
        max_price = None
        m_price = re.search(r'(\d+)\s*(tr|triệu|k|nghìn|ngàn)', q)
        if m_price:
            val = float(m_price.group(1))
            unit = m_price.group(2)
            if unit in ["tr", "triệu"]:
                max_price = val * 1000000
            elif unit in ["k", "nghìn", "ngàn"]:
                max_price = val * 1000

        # Phân tích chủng loại
        cat = None
        if "chó" in q:
            cat = "Chó"
        elif "mèo" in q:
            cat = "Mèo"
        elif "thức ăn" in q or "pate" in q or "hạt" in q:
            cat = "Thức ăn"

        matched = self.kb.search_pets(keyword="", max_price=max_price, category=cat)

        # Nuôi chung cư
        if any(w in q for w in ["chung cư", "phòng nhỏ", "ít rụng lông", "dễ nuôi"]):
            matched = [p for p in matched if any(b in p['name'].lower() for b in ["poodle", "pug", "mèo anh", "aln"])]
            ans_parts.append("🏢 **LỜI KHUYÊN NUÔI THÚ CƯNG TRONG CĂN HỘ / CHUNG CƯ TẠI MEOW & WOOF**\n")
            ans_parts.append("Dạ chào bạn! Khi nuôi ở chung cư hoặc không gian kín, Meow & Woof khuyên bạn nên ưu tiên các bé kích thước nhỏ gọn, ít rụng lông và tính cách hiền hòa:\n")
            ans_parts.append("1. **Chó Poodle Tiny**: Dẫn đầu về độ thông minh, không rụng lông, rất quấn chủ.")
            ans_parts.append("2. **Chó Pug Mặt Xệ**: Siêu hiền, ít sủa, cực kỳ thân thiện với trẻ nhỏ.")
            ans_parts.append("3. **Mèo Anh Lông Ngắn (Aln)**: Điềm đạm, thích nằm trong lòng, ngoan ngoãn và sạch sẽ.\n")
            ans_parts.append("Các bé hiện có sẵn tại cửa hàng phù hợp với bạn:\n")

        if matched:
            if not ans_parts:
                ans_parts.append("🐾 **DANH SÁCH BÉ ĐANG SẴN SÀNG ĐÓN VỀ NHÀ MỚI:**\n")
            for p in matched[:6]:
                ans_parts.append(f"⭐ **{p['name']}**")
                ans_parts.append(f"   - Mã SKU: `{p['sku']}` | Phân loại: {p.get('category', 'Thú cưng')}")
                ans_parts.append(f"   - Giá niêm yết: **{int(p['price']):,} đ** (Còn {p.get('stock', 1)} bé)")
                ans_parts.append(f"   - Đặc điểm: {p.get('description', 'Đã tiêm phòng đầy đủ, sức khỏe tốt')}\n")
            ans_parts.append("🎁 *Ưu đãi*: Tặng kèm gói bảo hành 15 ngày Parvo/Care + 1 lần Tắm sấy miễn phí tại Spa của Shop!")
            ans_parts.append("👉 Bạn hãy ghé website [https://chomeo.vercel.app](https://chomeo.vercel.app) để xem video trực tiếp hoặc gọi Hotline **0905.123.456** nhé!")
            return "\n".join(ans_parts)

        # 5. Mặc định: Giới thiệu tổng quan & gợi ý
        return (
            "Dạ Meow & Woof Pet House xin chào bạn! 🐶🐱\n\n"
            "Em là **Trợ lý AI Meow & Woof** sẵn sàng giải đáp mọi thắc mắc của bạn về:\n"
            "1. 🐕 **Tư vấn giống chó cảnh**: Corgi, Poodle, Shiba, Schnauzer, Pug, Alaska, Golden...\n"
            "2. 🐈 **Tư vấn giống mèo cảnh**: Mèo Anh lông ngắn (Aln), Ba Tư, Ragdoll, Tai cụp...\n"
            "3. 🛁 **Dịch vụ Spa & Grooming**: Tắm sấy, cắt tỉa lông tạo kiểu chuẩn 5 sao.\n"
            "4. 🎁 **Ưu đãi & Khuyến mãi**: Mã giảm giá MEOW10, WOOF15, chính sách Hạng VIP.\n"
            "5. 🛡️ **Bảo hành & Giao hàng**: Bảo hành sức khỏe 15 ngày Parvo/Care, giao nhanh 2h.\n\n"
            "👉 *Bạn có thể thử hỏi*: 'Tìm chó dưới 5 triệu', 'Giá dịch vụ tắm sấy', 'Mã giảm giá hôm nay', hoặc 'Nuôi chung cư nên chọn giống nào' nhé!"
        )


# =============================================================================
# 4. LỚP AI ĐIỀU HÀNH CHÍNH (PETSHOP AI ADVISOR)
# =============================================================================

class PetShopAIAdvisor:
    """Class trung tâm kết hợp giữa LLaMA API và Smart RAG Fallback."""

    def __init__(self, hf_token: Optional[str] = None):
        self.kb = PetShopKnowledgeBase()
        self.llama = LlamaHuggingFaceAdvisor(api_token=hf_token)
        self.fallback = SmartSemanticFallbackAdvisor(self.kb)
        self.conversation_history: List[Dict[str, str]] = []

    def set_hf_token(self, token: str):
        self.llama.set_token(token)

    def ask(self, query: str) -> Dict[str, Any]:
        """Tư vấn câu hỏi của khách hàng, trả về kết quả định dạng có cấu trúc."""
        system_context = self.kb.build_system_context(query)
        llm_reply, error_msg = self.llama.generate(query, system_context, self.conversation_history)

        mode_used = "LLaMA (HuggingFace API)"
        if llm_reply:
            reply = llm_reply
        else:
            # Fallback thông minh dựa trên dữ liệu chuẩn
            reply = self.fallback.consult(query)
            mode_used = f"Smart RAG Knowledge Engine ({error_msg or 'Local Mode'})"

        # Cập nhật lịch sử
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": reply})

        return {
            "reply": reply,
            "engine": mode_used,
            "model": self.llama.model,
            "has_token": bool(self.llama.api_token)
        }


# =============================================================================
# 5. GIAO DIỆN DÒNG LỆNH TƯƠNG TÁC (TERMINAL CLI INTERACTIVE)
# =============================================================================

def run_cli_interactive():
    advisor = PetShopAIAdvisor()

    print("\n" + "=" * 70)
    print("🐾 MEOW & WOOF PET HOUSE - TRỢ LÝ AI TƯ VẤN KHÁCH HÀNG (LLaMA POWERED) 🐾")
    print("=" * 70)
    print("Mô hình LLM: meta-llama/Llama-3.2-3B-Instruct (HuggingFace Inference API)")
    print(f"Cơ sở tri thức: {len(advisor.kb.pets)} thú cưng & sản phẩm | {len(advisor.kb.spa_services)} gói Spa | {len(advisor.kb.vouchers)} voucher")
    print("-" * 70)
    print("Gợi ý câu hỏi:")
    print("  1. 'Tôi muốn tìm chó dưới 5 triệu nuôi ở chung cư'")
    print("  2. 'Giá dịch vụ cắt tỉa lông cho chó mèo là bao nhiêu?'")
    print("  3. 'Shop có những mã giảm giá và chính sách thành viên nào?'")
    print("  4. 'Chính sách bảo hành và tiêm chủng của shop như thế nào?'")
    print("Lệnh hỗ trợ:  /token <HF_KEY>  |  /clear  |  /exit")
    print("-" * 70)

    # Kiểm tra biến môi trường
    env_token = os.environ.get("HUGGINGFACE_API_TOKEN") or os.environ.get("HF_TOKEN")
    if env_token:
        print(f"✅ Đã tìm thấy HuggingFace Token trong môi trường: {env_token[:6]}...{env_token[-4:]}")
    else:
        print("💡 Chế độ hiện tại: Smart RAG Engine (Bạn có thể nhập token LLaMA bằng lệnh /token <key>)")

    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("\n👤 Khách hàng: ").strip()
            if not user_input:
                continue

            # Xử lý lệnh đặc biệt
            if user_input.lower() in ["/exit", "exit", "quit", "thoát"]:
                print("\n🐾 Meow & Woof xin cảm ơn và hẹn gặp lại bạn! Chúc bạn một ngày tuyệt vời!\n")
                break
            elif user_input.lower() == "/clear":
                advisor.conversation_history.clear()
                print("🧹 Đã làm sạch lịch sử hội thoại.")
                continue
            elif user_input.lower().startswith("/token "):
                new_token = user_input.split(" ", 1)[1].strip()
                advisor.set_hf_token(new_token)
                print(f"✅ Đã cập nhật HuggingFace API Token: {new_token[:6]}...{new_token[-4:]}")
                continue

            print("⏳ AI đang suy nghĩ và tra cứu dữ liệu...", end="\r")
            res = advisor.ask(user_input)
            print(" " * 50, end="\r")  # Xóa dòng loading

            print(f"\n🤖 Trợ lý AI [{res['engine']}]:")
            print("-" * 65)
            print(res['reply'])
            print("-" * 65)

        except (KeyboardInterrupt, EOFError):
            print("\n\n🐾 Tạm biệt quý khách!")
            break


# =============================================================================
# 6. GIAO DIỆN WEB MINI ĐỘC LẬP (STANDALONE WEB UI TRÊN CỔNG RIÊNG)
# =============================================================================

def run_standalone_web(port: int = 5001):
    """Khởi chạy một máy chủ Web Mini độc lập phục vụ giao diện chat AI trực quan."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    advisor = PetShopAIAdvisor()

    HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trợ Lý AI Tư Vấn Thú Cưng - Meow & Woof (LLaMA)</title>
  <style>
    :root {
      --primary: #f59e0b;
      --primary-dark: #d97706;
      --bg-dark: #12100e;
      --card-dark: #1e1b18;
      --card-border: #383028;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body {
      background: var(--bg-dark);
      color: var(--text-main);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    header {
      background: var(--card-dark);
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-icon { font-size: 28px; }
    .brand-title { font-size: 18px; font-weight: bold; color: var(--primary); }
    .brand-subtitle { font-size: 12px; color: var(--text-muted); }
    .token-box { display: flex; align-items: center; gap: 8px; font-size: 13px; }
    .token-input {
      background: #282420;
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 12px;
      width: 200px;
    }
    .token-btn {
      background: var(--primary);
      color: #000;
      font-weight: bold;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
    }
    .main-chat {
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 900px;
      width: 100%;
      margin: 0 auto;
      height: calc(100vh - 65px);
    }
    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .msg { display: flex; gap: 12px; max-width: 85%; }
    .msg.user { align-self: flex-end; flex-direction: row-reverse; }
    .msg.ai { align-self: flex-start; }
    .avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }
    .msg.ai .avatar { background: rgba(245, 158, 11, 0.2); border: 1px solid var(--primary); }
    .msg.user .avatar { background: #3b82f6; }
    .bubble {
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .msg.ai .bubble {
      background: var(--card-dark);
      border: 1px solid var(--card-border);
      color: #e5e7eb;
    }
    .msg.user .bubble {
      background: var(--primary-dark);
      color: #ffffff;
    }
    .engine-tag {
      font-size: 10px;
      color: var(--primary);
      margin-top: 6px;
      font-weight: bold;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .quick-chips {
      padding: 8px 20px;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      background: rgba(30, 27, 24, 0.5);
      border-top: 1px solid var(--card-border);
    }
    .chip {
      background: #2a2520;
      border: 1px solid var(--card-border);
      color: #d1d5db;
      font-size: 12px;
      padding: 6px 12px;
      border-radius: 20px;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }
    .chip:hover {
      background: var(--primary);
      color: #000;
      border-color: var(--primary);
    }
    .chat-input-bar {
      padding: 14px 20px;
      background: var(--card-dark);
      border-top: 1px solid var(--card-border);
      display: flex;
      gap: 12px;
    }
    .input-field {
      flex: 1;
      background: #12100e;
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 14px;
      outline: none;
    }
    .input-field:focus { border-color: var(--primary); }
    .send-btn {
      background: var(--primary);
      color: #000;
      font-weight: bold;
      border: none;
      padding: 0 20px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
    }
    .send-btn:hover { background: #fbbf24; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-icon">🐾</div>
      <div>
        <div class="brand-title">Meow & Woof AI Consultant</div>
        <div class="brand-subtitle">Mô hình Ngôn ngữ Lớn LLaMA 3 & RAG Knowledge Base</div>
      </div>
    </div>
    <div class="token-box">
      <span>HF Token:</span>
      <input type="password" id="tokenInput" class="token-input" placeholder="hf_xxxxxxxx...">
      <button onclick="saveToken()" class="token-btn">Lưu Token</button>
    </div>
  </header>

  <div class="main-chat">
    <div class="chat-messages" id="chatMessages">
      <div class="msg ai">
        <div class="avatar">🤖</div>
        <div>
          <div class="bubble">Dạ xin chào quý khách! 🐶🐱
Em là Trợ lý AI thông minh của <b>Meow & Woof Pet House</b> được tích hợp công nghệ mô hình ngôn ngữ lớn (LLaMA).
Em có thể tư vấn đầy đủ về 42 giống thú cưng có sẵn, bảng giá dịch vụ Spa & Grooming, mã giảm giá và chính sách chăm sóc bảo hành của cửa hàng.
Bạn có thể hỏi bất kỳ câu hỏi nào bên dưới nhé!</div>
          <div class="engine-tag">⚡ Powered by LLaMA 3 & RAG Engine</div>
        </div>
      </div>
    </div>

    <div class="quick-chips">
      <div class="chip" onclick="quickSend('Tìm chó dưới 5 triệu nuôi ở chung cư')">🏠 Chó dưới 5tr nuôi chung cư</div>
      <div class="chip" onclick="quickSend('Bảng giá dịch vụ Spa và tắm sấy')">🛁 Bảng giá Spa & Tắm sấy</div>
      <div class="chip" onclick="quickSend('Shop có những mã giảm giá nào?')">🎁 Mã giảm giá hôm nay</div>
      <div class="chip" onclick="quickSend('Chính sách bảo hành và tiêm phòng thế nào?')">🛡️ Bảo hành 15 ngày & Tiêm phòng</div>
      <div class="chip" onclick="quickSend('Tư vấn mèo Anh lông ngắn')">🐈 Mèo Anh lông ngắn (Aln)</div>
    </div>

    <div class="chat-input-bar">
      <input type="text" id="userInput" class="input-field" placeholder="Nhập câu hỏi cần tư vấn (VD: Tìm cún cưng phù hợp với gia đình...)" onkeypress="if(event.key === 'Enter') sendMessage()">
      <button class="send-btn" onclick="sendMessage()">Gửi Tư Vấn ➔</button>
    </div>
  </div>

  <script>
    let hfToken = localStorage.getItem('mw_hf_token') || '';
    if (hfToken) {
      document.getElementById('tokenInput').value = hfToken;
    }

    function saveToken() {
      const val = document.getElementById('tokenInput').value.trim();
      localStorage.setItem('mw_hf_token', val);
      alert('Đã lưu HuggingFace API Token thành công!');
    }

    function quickSend(txt) {
      document.getElementById('userInput').value = txt;
      sendMessage();
    }

    async function sendMessage() {
      const input = document.getElementById('userInput');
      const text = input.value.trim();
      if (!text) return;

      const chatBox = document.getElementById('chatMessages');

      // 1. Thêm tin nhắn của User
      chatBox.innerHTML += `
        <div class="msg user">
          <div class="avatar">👤</div>
          <div class="bubble">${escapeHtml(text)}</div>
        </div>
      `;
      input.value = '';
      chatBox.scrollTop = chatBox.scrollHeight;

      // 2. Thêm chỉ báo đang soạn
      const loadingId = 'loading-' + Date.now();
      chatBox.innerHTML += `
        <div class="msg ai" id="${loadingId}">
          <div class="avatar">🤖</div>
          <div class="bubble"><i>Đang suy nghĩ và tra cứu dữ liệu...</i></div>
        </div>
      `;
      chatBox.scrollTop = chatBox.scrollHeight;

      try {
        const resp = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, token: localStorage.getItem('mw_hf_token') || '' })
        });
        const data = await resp.json();

        // 3. Thay thế nội dung loading
        const loadingElem = document.getElementById(loadingId);
        if (loadingElem) {
          loadingElem.innerHTML = `
            <div class="avatar">🤖</div>
            <div>
              <div class="bubble">${formatMarkdown(data.reply)}</div>
              <div class="engine-tag">⚡ ${data.engine}</div>
            </div>
          `;
        }
      } catch (err) {
        const loadingElem = document.getElementById(loadingId);
        if (loadingElem) {
          loadingElem.innerHTML = `
            <div class="avatar">🤖</div>
            <div class="bubble" style="color: #ef4444;">Đã xảy ra lỗi kết nối: ${err.message}</div>
          `;
        }
      }
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    function escapeHtml(str) {
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function formatMarkdown(str) {
      if (!str) return '';
      let s = escapeHtml(str);
      // Bold **text**
      s = s.replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>');
      // Code `text`
      s = s.replace(/`(.*?)`/g, '<code style="background: rgba(245,158,11,0.15); color: #f59e0b; padding: 2px 5px; border-radius: 4px;">$1</code>');
      return s;
    }
  </script>
</body>
</html>
"""

    class StandaloneHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(HTML_PAGE.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/api/chat":
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8")
                try:
                    payload = json.loads(body)
                    msg = payload.get("message", "")
                    tok = payload.get("token", "")
                    if tok:
                        advisor.set_hf_token(tok)
                    res = advisor.ask(msg)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"reply": f"Lỗi: {str(e)}", "engine": "Error"}).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Tắt log console mặc định để màn hình sạch sẽ

    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, StandaloneHandler)
    print("\n" + "=" * 70)
    print("🐾 MEOW & WOOF - STANDALONE AI WEB CONSULTANT (LLaMA)")
    print("=" * 70)
    print(f"🚀 Máy chủ Chatbot AI đang hoạt động độc lập tại:")
    print(f"👉 http://localhost:{port}   hoặc   http://127.0.0.1:{port}")
    print("-" * 70)
    print("Ghi chú: Ứng dụng này chạy hoàn toàn độc lập, không làm thay đổi")
    print("bất kỳ tập tin hay giao diện nào của website chính!")
    print("Nhấn Ctrl + C để dừng máy chủ.")
    print("=" * 70 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🐾 Đã dừng máy chủ AI Web Consultant.")


# =============================================================================
# 7. KHỞI CHẠY CHÍNH (ENTRY POINT)
# =============================================================================

if __name__ == "__main__":
    if "--web" in sys.argv:
        port = 5001
        for idx, arg in enumerate(sys.argv):
            if arg == "--port" and idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        run_standalone_web(port)
    else:
        run_cli_interactive()
