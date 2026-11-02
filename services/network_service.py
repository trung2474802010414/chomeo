"""
services/network_service.py
Đáp ứng CLO3 (10% - Lập trình mạng: urllib, API key, JSON/XML, lập trình mạng Internet)
và CLO4 (Sử dụng thành thạo thư viện Python: urllib, json, xml.etree.ElementTree).
"""

import json
import time
from typing import Any, Dict, List, Tuple
import urllib.error
import urllib.parse
import urllib.request

from services.xml_service import export_products_to_xml, import_products_from_xml

__all__ = [
    "FALLBACK_BREEDS",
    "fetch_pet_breeds_via_urllib",
    "export_products_to_xml",
    "import_products_from_xml",
]

# Bộ nhớ đệm (In-Memory Cache) cho kết quả gọi API qua urllib để trang tải tức thì (< 5ms)
_BREED_API_CACHE: Dict[Tuple[str, str], Tuple[float, List[Dict[str, Any]], str]] = {}
_CACHE_TTL_SECONDS = 900.0  # Lưu cache 15 phút

# Dữ liệu dự phòng khi máy tính chấm bài không kết nối Internet
FALLBACK_BREEDS: Dict[str, List[Dict[str, str]]] = {
    "cat": [
        {
            "name": "British Shorthair (Mèo Anh Lông Ngắn)",
            "origin": "Vương quốc Anh",
            "temperament": "Điềm tĩnh, Quấn chủ, Thông minh, Dễ chăm sóc",
            "life_span": "12 - 17 năm",
            "weight_metric": "4 - 8 kg",
            "description": "Giống mèo có thân hình mũm mĩm, bộ lông dày mượt như nhung và khuôn mặt tròn bầu bĩnh rất được ưa chuộng.",
        },
        {
            "name": "Scottish Fold (Mèo Tai Cụp)",
            "origin": "Scotland",
            "temperament": "Hiền lành, Tình cảm, Hòa đồng, Thích chơi nhẹ nhàng",
            "life_span": "11 - 14 năm",
            "weight_metric": "3 - 6 kg",
            "description": "Nổi bật với đôi tai gấp về phía trước tạo vẻ ngoài giống chú cú nhỏ đáng yêu.",
        },
        {
            "name": "Persian (Mèo Ba Tư)",
            "origin": "Iran (Ba Tư)",
            "temperament": "Nhẹ nhàng, Yên tĩnh, Dịu dàng",
            "life_span": "14 - 15 năm",
            "weight_metric": "3 - 5 kg",
            "description": "Giống mèo lông dài quý phái, cần được chải lông hàng ngày và tắm sấy định kỳ tại Spa.",
        },
        {
            "name": "Maine Coon (Mèo Rừng Na Uy / Mỹ)",
            "origin": "Hoa Kỳ",
            "temperament": "Thân thiện, Thông minh, Năng động",
            "life_span": "12 - 15 năm",
            "weight_metric": "5 - 11 kg",
            "description": "Một trong những giống mèo nhà lớn nhất thế giới với bờm lông cổ dày và tính cách hiền hòa.",
        },
    ],
    "dog": [
        {
            "name": "Poodle (Toy / Miniature Poodle)",
            "origin": "Pháp / Đức",
            "temperament": "Thông minh, Lanh lợi, Trung thành, Dễ huấn luyện",
            "life_span": "12 - 15 năm",
            "weight_metric": "3 - 7 kg",
            "description": "Giống chó có bộ lông xoăn ít rụng, rất phù hợp cắt tỉa tạo kiểu Teddy tại Spa thú cưng.",
        },
        {
            "name": "Pembroke Welsh Corgi",
            "origin": "Xứ Wales (Anh)",
            "temperament": "Vui vẻ, Năng động, Thân thiện, Can đảm",
            "life_span": "12 - 14 năm",
            "weight_metric": "10 - 14 kg",
            "description": "Nổi tiếng với đôi chân ngắn đáng yêu, cặp mông tròn và nụ cười luôn rạng rỡ.",
        },
        {
            "name": "Golden Retriever",
            "origin": "Vương quốc Anh",
            "temperament": "Hiền lành, Đáng tin cậy, Thông minh, Thân thiện với trẻ nhỏ",
            "life_span": "10 - 12 năm",
            "weight_metric": "25 - 34 kg",
            "description": "Giống chó gia đình tuyệt vời với bộ lông vàng óng mượt và khả năng học hỏi nhanh.",
        },
        {
            "name": "Shiba Inu",
            "origin": "Nhật Bản",
            "temperament": "Lanh lợi, Độc lập, Trung thành, Sạch sẽ",
            "life_span": "12 - 16 năm",
            "weight_metric": "8 - 11 kg",
            "description": "Giống chó quốc khuyển của Nhật Bản có ngoại hình gọn gàng và biểu cảm khuôn mặt sinh động.",
        },
    ],
}


def fetch_pet_breeds_via_urllib(
    species: str = "cat",
    api_key: str = "",
    search_breed: str = "",
    limit: int = 8,
) -> Dict[str, Any]:
    """
    Minh họa Lập trình mạng (CLO3):
    - Dùng `urllib.request.Request` gửi HTTP GET tới REST API trên Internet.
    - Truyền `x-api-key` trong HTTP Request Headers.
    - Giải mã dữ liệu phản hồi JSON bằng `json.loads()`.
    """
    species_key = "dog" if species == "dog" else "cat"
    endpoint = (
        "https://api.thedogapi.com/v1/breeds"
        if species_key == "dog"
        else "https://api.thecatapi.com/v1/breeds"
    )

    headers = {
        "User-Agent": "MeowWoofPetShop-UrllibClient/1.0 (Python Standard Library)",
        "Accept": "application/json",
    }
    effective_key = api_key.strip() or "DEMO-API-KEY-PETSHOP-CLO3"
    headers["x-api-key"] = effective_key

    source_mode = "Internet Live API (urllib.request)"
    raw_breeds: List[Dict[str, Any]] = []

    cache_key = (species_key, effective_key)
    now_ts = time.time()
    cached_entry = _BREED_API_CACHE.get(cache_key)

    if cached_entry and (now_ts - cached_entry[0]) < _CACHE_TTL_SECONDS:
        raw_breeds = cached_entry[1]
        source_mode = cached_entry[2]
    else:
        try:
            req = urllib.request.Request(endpoint, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as response:
                raw_json = response.read().decode("utf-8")
                parsed = json.loads(raw_json)
                if isinstance(parsed, list) and parsed:
                    raw_breeds = parsed
                    _BREED_API_CACHE[cache_key] = (now_ts, raw_breeds, source_mode)
                else:
                    raw_breeds = FALLBACK_BREEDS[species_key]
        except Exception as exc:
            source_mode = f"Chế độ Offline Dự phòng ({type(exc).__name__})"
            raw_breeds = FALLBACK_BREEDS[species_key]
            _BREED_API_CACHE[cache_key] = (now_ts - _CACHE_TTL_SECONDS + 60.0, raw_breeds, source_mode)

    normalized = [
        {
            "name": item.get("name", "Không rõ"),
            "origin": item.get("origin") or item.get("country_code") or "Quốc tế",
            "temperament": item.get("temperament", "Thân thiện, dễ mến"),
            "life_span": item.get("life_span", "12 - 15 năm"),
            "weight_metric": (
                item.get("weight", {}).get("metric", "4 - 8") + " kg"
                if isinstance(item.get("weight"), dict)
                else item.get("weight_metric", "4 - 8 kg")
            ),
            "description": item.get("description")
            or f"Giống {'chó' if species_key == 'dog' else 'mèo'} {item.get('name', '')} phổ biến, tính cách: {item.get('temperament', 'năng động')}.",
        }
        for item in raw_breeds
    ]

    if search_breed.strip():
        kw = search_breed.strip().lower()
        normalized = [
            b for b in normalized
            if kw in b["name"].lower() or kw in b["origin"].lower() or kw in b["temperament"].lower()
        ]

    return {
        "endpoint": endpoint,
        "species": species_key,
        "api_key_masked": effective_key[:6] + "***" if len(effective_key) > 6 else "***",
        "source_mode": source_mode,
        "total_matched": len(normalized),
        "breeds": normalized[:limit],
    }
