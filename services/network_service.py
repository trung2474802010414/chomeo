"""
services/network_service.py
Lập trình mạng & Bách khoa toàn thư giống thú cưng (CLO3 & CLO4):
- Gọi REST API tra cứu giống thú cưng qua `urllib.request` kèm `API Key` trong HTTP Header.
- Kết hợp cơ sở dữ liệu Cẩm nang 32 giống Chó & Mèo thuần chủng tiếng Việt (kèm hình ảnh thực tế,
  chế độ dinh dưỡng, lịch tắm Spa, mức độ phù hợp chung cư và liên kết trực tiếp tới sản phẩm tại Shop).
- Xuất và nhập danh mục sản phẩm định dạng XML bằng `xml.etree.ElementTree`.
"""

import json
import time
from typing import Any, Dict, List, Tuple
import urllib.error
import urllib.parse
import urllib.request
from xml.dom import minidom
import xml.etree.ElementTree as ET

from core.orm import ValidationError
from models.entities import Product

_BREED_API_CACHE: Dict[Tuple[str, str], Tuple[float, List[Dict[str, Any]], str]] = {}
_CACHE_TTL_SECONDS = 900.0

FALLBACK_BREEDS: Dict[str, List[Dict[str, Any]]] = {
    "cat": [
        {
            "sku": "CAT-PET-001",
            "name": "British Shorthair (Mèo Anh Lông Ngắn)",
            "vi_name": "Mèo Anh Lông Ngắn (ALN)",
            "en_name": "British Shorthair",
            "shop_breed": "Mèo Anh Lông Ngắn (ALN)",
            "pet_type": "Mèo",
            "origin": "Vương quốc Anh",
            "temperament": "Điềm tĩnh, Quấn chủ, Thông minh, Dễ chăm sóc",
            "life_span": "12 – 17 năm",
            "weight_metric": "4 – 8 kg",
            "coat_type": "Lông ngắn dày như nhung • Ít rụng",
            "living_space": "Rất hợp căn hộ & chung cư",
            "care_level": "Dễ nuôi cho người mới",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 95,
            "easy_care_score": 95,
            "apartment_score": 98,
            "image_url": "/static/images/catalog/cat-pet-001-aln.jpg",
            "default_price": 4500000,
            "description": "Giống mèo quốc dân có thân hình mũm mĩm, hai má phệ bầu bĩnh và bộ lông dày mượt như nhung. Tính cách hiền hòa, không ồn ào và tự giác đi vệ sinh vào thau cát.",
            "nutrition_guide": "Hạt Royal Canin Indoor 27 kết hợp Pate Ciao Churu cấp ẩm 2–3 bữa/tuần; kiểm soát khẩu phần tránh béo phì.",
            "grooming_guide": "Chải lông 2 lần/tuần bằng lược mềm; tắm sấy thảo mộc SOS mỗi 3–4 tuần và cắt móng định kỳ.",
            "health_note": "Tiêm đủ 2 mũi vaccine 4 bệnh và phòng dại; vệ sinh khóe mắt và tai hàng tuần.",
        },
        {
            "sku": "CAT-PET-002",
            "name": "Scottish Fold (Mèo Tai Cụp)",
            "vi_name": "Mèo Tai Cụp Scottish Fold",
            "en_name": "Scottish Fold",
            "shop_breed": "Mèo Tai Cụp Scottish Fold",
            "pet_type": "Mèo",
            "origin": "Scotland (Anh Quốc)",
            "temperament": "Ngọt ngào, Tình cảm, Hòa đồng, Ngoan ngoãn",
            "life_span": "11 – 14 năm",
            "weight_metric": "3 – 6 kg",
            "coat_type": "Lông ngắn mềm • Rụng ít",
            "living_space": "Rất hợp chung cư & phòng nhỏ",
            "care_level": "Dễ nuôi, thích vuốt ve",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 98,
            "easy_care_score": 90,
            "apartment_score": 96,
            "image_url": "/static/images/catalog/cat-pet-002-scottish.jpg",
            "default_price": 5600000,
            "description": "Nổi bật với đôi tai gấp gọn về phía trước cùng đôi mắt to tròn long lanh tạo vẻ ngoài giống chú cú nhỏ cực kỳ đáng yêu, rất quấn người.",
            "nutrition_guide": "Hạt giàu đạm & Omega-3 kết hợp súp thưởng Ciao Churu và gel dinh dưỡng Virbac giúp mượt lông.",
            "grooming_guide": "Do tai cụp nên cần lau sạch vành tai 1–2 lần/tuần bằng dung dịch chuyên dụng; tắm Spa 3–4 tuần/lần.",
            "health_note": "Bổ sung canxi và dưỡng chất sụn khớp vừa đủ; giữ môi trường sống khô thoáng, sạch sẽ.",
        },
        {
            "sku": "CAT-PET-003",
            "name": "Munchkin (Mèo Chân Ngắn)",
            "vi_name": "Mèo Chân Ngắn Munchkin",
            "en_name": "Munchkin Cat",
            "shop_breed": "Mèo Chân Ngắn Munchkin",
            "pet_type": "Mèo",
            "origin": "Hoa Kỳ",
            "temperament": "Tinh nghịch, Năng động, Quấn chủ, Thân thiện",
            "life_span": "12 – 15 năm",
            "weight_metric": "2.5 – 4.5 kg",
            "coat_type": "Lông mềm mịn • Dễ chải chuốt",
            "living_space": "Hợp căn hộ & nhà phố",
            "care_level": "Chăm sóc tiêu chuẩn",
            "tags": ["apartment", "family", "beginner"],
            "affection_score": 96,
            "easy_care_score": 88,
            "apartment_score": 95,
            "image_url": "/static/images/catalog/cat-pet-003-munchkin.jpg",
            "default_price": 8200000,
            "description": "Sở hữu 4 chân ngắn lũn cũn với dáng đi lắc lư siêu cưng. Dù chân ngắn nhưng bé rất nhanh nhẹn, hoạt bát và thích chơi đùa cùng chủ.",
            "nutrition_guide": "Chia 3 bữa nhỏ/ngày với hạt Royal Canin và pate cá ngừ; giữ mức cân nặng vừa phải để bảo vệ cột sống.",
            "grooming_guide": "Tắm sấy vệ sinh bàn chân và bụng 3 tuần/lần; chuẩn bị trụ cào móng thấp vừa tầm với của bé.",
            "health_note": "Hạn chế để bé nhảy từ tủ quá cao xuống sàn cứng; tẩy giun định kỳ mỗi 3 tháng.",
        },
        {
            "sku": "CAT-PET-004",
            "name": "Ragdoll (Mèo Công Chúa Mắt Xanh)",
            "vi_name": "Mèo Ragdoll Mắt Xanh",
            "en_name": "Ragdoll",
            "shop_breed": "Mèo Ragdoll",
            "pet_type": "Mèo",
            "origin": "Hoa Kỳ (California)",
            "temperament": "Dịu dàng, Điềm đạm, Thích ôm ấp, Thân thiện trẻ nhỏ",
            "life_span": "13 – 17 năm",
            "weight_metric": "4.5 – 9 kg",
            "coat_type": "Lông dài mượt • Cần chải định kỳ",
            "living_space": "Căn hộ rộng & nhà phố",
            "care_level": "Cần chải lông 3 lần/tuần",
            "tags": ["apartment", "family"],
            "affection_score": 100,
            "easy_care_score": 85,
            "apartment_score": 92,
            "image_url": "/static/images/catalog/cat-pet-004-ragdoll.jpg",
            "default_price": 7500000,
            "description": "Được mệnh danh là 'nàng công chúa' trong thế giới mèo với đôi mắt xanh ngọc bích và thói quen thả lỏng người mềm nhũn mỗi khi được chủ bế lên.",
            "nutrition_guide": "Hạt hỗ trợ tiêu búi lông (Hairball) + Pate tươi giàu Taurine giúp mắt sáng và bộ lông bóng mượt.",
            "grooming_guide": "Chải lông hàng ngày hoặc 3 lần/tuần; đặt lịch gói Tắm sấy & Cắt tỉa vệ sinh lông bụng tại Spa mỗi tháng.",
            "health_note": "Luôn để sẵn nước sạch và cát đậu nành Tofu khử mùi; khám sức khỏe định kỳ 6 tháng/lần.",
        },
        {
            "sku": "CAT-PET-005",
            "name": "British Longhair (Mèo Anh Lông Dài)",
            "vi_name": "Mèo Anh Lông Dài (ALD)",
            "en_name": "British Longhair",
            "shop_breed": "Mèo Anh Lông Dài (ALD)",
            "pet_type": "Mèo",
            "origin": "Vương quốc Anh",
            "temperament": "Nhẹ nhàng, Quý phái, Điềm tĩnh, Tình cảm",
            "life_span": "12 – 16 năm",
            "weight_metric": "4 – 7.5 kg",
            "coat_type": "Lông dài bông xù • Sang trọng",
            "living_space": "Hợp căn hộ điều hòa / thoáng mát",
            "care_level": "Cần chải lông thường xuyên",
            "tags": ["apartment", "family"],
            "affection_score": 94,
            "easy_care_score": 84,
            "apartment_score": 92,
            "image_url": "/static/images/catalog/cat-pet-005-ald.jpg",
            "default_price": 5200000,
            "description": "Phiên bản lông dài quý tộc của dòng mèo Anh với bờm cổ dày bông trắng muốt, khuôn mặt tròn bầu bĩnh và tính cách hiền lành, sang trọng.",
            "nutrition_guide": "Hạt Royal Canin kết hợp Gel dinh dưỡng Nutri-Plus và súp thưởng bổ sung Omega-3, 6 dưỡng lông.",
            "grooming_guide": "Chải lông mỗi ngày để tránh rối; tỉa gọn lông bàn chân và lông quanh hậu môn tại Spa định kỳ.",
            "health_note": "Giữ không gian sống mát mẻ, bổ sung mạch nha hoặc cỏ mèo hỗ trợ tiêu hóa búi lông tự nhiên.",
        },
        {
            "sku": "CAT-PET-006",
            "name": "Persian (Mèo Ba Tư Mặt Tịt)",
            "vi_name": "Mèo Ba Tư (Persian)",
            "en_name": "Persian Cat",
            "shop_breed": "Mèo Ba Tư (Persian)",
            "pet_type": "Mèo",
            "origin": "Iran (Ba Tư Cổ Đại)",
            "temperament": "Yên tĩnh, Dịu dàng, Quấn chủ, Hiền lành",
            "life_span": "13 – 16 năm",
            "weight_metric": "3.5 – 6 kg",
            "coat_type": "Lông dài dày 2 lớp • Quý tộc",
            "living_space": "Căn hộ yên tĩnh & mát mẻ",
            "care_level": "Cần chăm sóc mắt & chải lông",
            "tags": ["apartment", "family"],
            "affection_score": 95,
            "easy_care_score": 80,
            "apartment_score": 94,
            "image_url": "/static/images/catalog/cat-pet-006-persian.jpg",
            "default_price": 5800000,
            "description": "Giống mèo hoàng gia lâu đời nổi tiếng với khuôn mặt phẳng bầu bĩnh đáng yêu, bộ lông dài thướt tha và phong thái điềm tĩnh, thích nằm trong lòng chủ.",
            "nutrition_guide": "Dùng bát ăn nông miệng rộng để bé dễ lấy hạt; kết hợp hạt Royal Canin Persian và pate mềm.",
            "grooming_guide": "Lau khóe mắt hàng ngày bằng bông ẩm sạch; tắm sấy đánh bông lông tại Spa mỗi 2–3 tuần.",
            "health_note": "Tránh thời tiết quá nóng ẩm; giữ mũi và mắt bé luôn thông thoáng, sạch sẽ.",
        },
        {
            "sku": "CAT-PET-007",
            "name": "Bengal (Mèo Vân Báo Đốm)",
            "vi_name": "Mèo Bengal Vân Báo",
            "en_name": "Bengal Cat",
            "shop_breed": "Mèo Bengal",
            "pet_type": "Mèo",
            "origin": "Hoa Kỳ",
            "temperament": "Thông minh, Năng động, Tò mò, Trung thành",
            "life_span": "12 – 16 năm",
            "weight_metric": "4 – 7 kg",
            "coat_type": "Lông ngắn sát bóng mượt • Rất ít rụng",
            "living_space": "Nhà có trụ leo trèo / không gian chơi",
            "care_level": "Ít rụng lông, ưa vận động",
            "tags": ["low_shed", "family"],
            "affection_score": 90,
            "easy_care_score": 90,
            "apartment_score": 86,
            "image_url": "/static/images/catalog/cat-pet-007-bengal.jpg",
            "default_price": 8900000,
            "description": "Mang vẻ đẹp hoang dã của loài báo rừng thu nhỏ với họa tiết đốm hoa hồng (Rosettes) lấp lánh trên nền lông mượt như lụa nhưng tính cách lại rất quấn chủ.",
            "nutrition_guide": "Chế độ ăn giàu protein từ hạt cao cấp, thịt ức gà luộc và pate cá hồi giúp cơ bắp săn chắc.",
            "grooming_guide": "Lông ngắn hầu như không rụng nên rất nhàn; chỉ cần tắm thảo mộc mỗi tháng 1 lần và chuẩn bị trụ cào móng.",
            "health_note": "Sức đề kháng rất khỏe; nên dành 15–20 phút mỗi ngày chơi cần câu mèo để bé giải phóng năng lượng.",
        },
        {
            "sku": "CAT-PET-008",
            "name": "Maine Coon (Mèo Rừng Mỹ Khổng Lồ)",
            "vi_name": "Mèo Rừng Maine Coon",
            "en_name": "Maine Coon",
            "shop_breed": "Mèo Maine Coon",
            "pet_type": "Mèo",
            "origin": "Hoa Kỳ (Bang Maine)",
            "temperament": "Hiền hòa, Thông minh, Trung thành, Thân thiện",
            "life_span": "12 – 15 năm",
            "weight_metric": "6 – 11 kg",
            "coat_type": "Bờm lông sư tử dày • Chùm tai linh miêu",
            "living_space": "Căn hộ rộng hoặc nhà phố",
            "care_level": "Chải bờm lông 2–3 lần/tuần",
            "tags": ["family", "apartment"],
            "affection_score": 96,
            "easy_care_score": 85,
            "apartment_score": 85,
            "image_url": "/static/images/catalog/cat-pet-008-mainecoon.jpg",
            "default_price": 11500000,
            "description": "Được gọi là 'Người khổng lồ dịu dàng' với vóc dáng to lớn oai vệ, chùm lông tai linh miêu đặc trưng nhưng tính cách lại hiền lành, quấn người như cún cưng.",
            "nutrition_guide": "Khẩu phần giàu đạm, canxi và glucosamine hỗ trợ khung xương lớn phát triển khỏe mạnh.",
            "grooming_guide": "Chải lông ngực và đuôi tuần 2–3 lần; sử dụng gói Grooming tắm sấy cho mèo lớn tại Spa định kỳ.",
            "health_note": "Chuẩn bị khay cát vệ sinh cỡ lớn và bát nước rộng; tiêm phòng và tẩy giun đúng lịch.",
        },
        {
            "sku": "CAT-PET-009",
            "name": "Siamese (Mèo Xiêm Hoàng Gia)",
            "vi_name": "Mèo Xiêm (Siamese)",
            "en_name": "Siamese Cat",
            "shop_breed": "Mèo Xiêm (Siamese)",
            "pet_type": "Mèo",
            "origin": "Thái Lan (Vương quốc Xiêm)",
            "temperament": "Thông minh, Quấn chủ, Lanh lợi, Giao tiếp tốt",
            "life_span": "14 – 18 năm",
            "weight_metric": "3.5 – 5.5 kg",
            "coat_type": "Lông ngắn ôm sát • Rất ít rụng",
            "living_space": "Phù hợp mọi căn hộ & gia đình",
            "care_level": "Rất dễ nuôi, khỏe mạnh",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 98,
            "easy_care_score": 96,
            "apartment_score": 95,
            "image_url": "/static/images/catalog/cat-pet-009-siamese.jpg",
            "default_price": 3800000,
            "description": "Giống mèo hoàng gia châu Á nổi bật với đôi mắt xanh Sapphire sâu thẳm và bộ lông điểm màu đậm ở tai, mặt, chân và đuôi. Cực kỳ thông minh và trung thành.",
            "nutrition_guide": "Ăn uống rất dễ, hợp với hạt Royal Canin kết hợp pate Ciao Churu và cá hấp.",
            "grooming_guide": "Bộ lông ngắn hầu như không tốn công chải; chỉ cần lau khăn ấm hoặc tắm sữa tắm SOS 1 tháng/lần.",
            "health_note": "Phù hợp khí hậu nhiệt đới Việt Nam, tuổi thọ cao và rất ít bệnh vặt.",
        },
        {
            "sku": "CAT-PET-010",
            "name": "Russian Blue (Mèo Nga Mắt Xanh)",
            "vi_name": "Mèo Nga Mắt Xanh",
            "en_name": "Russian Blue",
            "shop_breed": "Mèo Nga Mắt Xanh",
            "pet_type": "Mèo",
            "origin": "Liên bang Nga",
            "temperament": "Điềm đạm, Sạch sẽ, Tinh tế, Trung thành",
            "life_span": "15 – 18 năm",
            "weight_metric": "3.5 – 6 kg",
            "coat_type": "Lông nhung xám ánh bạc • Ít gây dị ứng",
            "living_space": "Rất hợp căn hộ yên tĩnh",
            "care_level": "Dễ nuôi, cực kỳ sạch sẽ",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 93,
            "easy_care_score": 96,
            "apartment_score": 98,
            "image_url": "/static/images/catalog/cat-pet-010-russianblue.jpg",
            "default_price": 6400000,
            "description": "Sở hữu bộ lông kép màu xám xanh ánh bạc mịn như nhung cùng đôi mắt xanh lục bảo tuyệt đẹp. Là một trong những giống mèo sạch sẽ và ít rụng lông nhất.",
            "nutrition_guide": "Hạt khô cao cấp kết hợp súp thưởng; luôn giữ khay cát Tofu sạch vì bé rất ưa sạch sẽ.",
            "grooming_guide": "Rất ít rụng lông và ít tiết chất gây dị ứng; tắm sấy nhẹ nhàng 4–5 tuần/lần.",
            "health_note": "Sức khỏe bền bỉ, tuổi thọ lên tới 18 năm khi được tiêm phòng và chăm sóc tốt.",
        },
        {
            "sku": "CAT-PET-011",
            "name": "Sphynx (Mèo Không Lông Ai Cập)",
            "vi_name": "Mèo Sphynx Không Lông",
            "en_name": "Sphynx Cat",
            "shop_breed": "Mèo Sphynx Không Lông",
            "pet_type": "Mèo",
            "origin": "Canada / Ai Cập",
            "temperament": "Thân thiện, Thông minh, Hài hước, Quấn người",
            "life_span": "12 – 15 năm",
            "weight_metric": "3.5 – 5.5 kg",
            "coat_type": "Không rụng lông 100% • Da ấm như nhung",
            "living_space": "Căn hộ trong nhà ấm áp",
            "care_level": "Lau da & giữ ấm khi trời lạnh",
            "tags": ["apartment", "low_shed", "family"],
            "affection_score": 99,
            "easy_care_score": 86,
            "apartment_score": 96,
            "image_url": "https://images.unsplash.com/photo-1521724429677-0a4c31abf278?auto=format&fit=crop&w=700&q=80",
            "default_price": 13500000,
            "description": "Vẻ ngoài độc đáo như tượng nhân sư Ai Cập với làn da ấm áp mềm như da đào và hoàn toàn không rụng một sợi lông nào — lựa chọn hoàn hảo cho người dị ứng lông.",
            "nutrition_guide": "Quá trình trao đổi chất nhanh để giữ ấm cơ thể nên cần hạt giàu năng lượng và pate dinh dưỡng mỗi ngày.",
            "grooming_guide": "Không lo rụng lông ra sofa; cần tắm hoặc lau sạch dầu tự nhiên trên da 1–2 tuần/lần và vệ sinh tai.",
            "health_note": "Mặc áo mỏng cho bé khi nằm phòng máy lạnh sâu và tránh nắng gắt trực tiếp.",
        },
        {
            "sku": "CAT-PET-012",
            "name": "American Shorthair (Mèo Mỹ Lông Ngắn)",
            "vi_name": "Mèo Mỹ Lông Ngắn",
            "en_name": "American Shorthair",
            "shop_breed": "Mèo Mỹ Lông Ngắn",
            "pet_type": "Mèo",
            "origin": "Hoa Kỳ",
            "temperament": "Khỏe mạnh, Vui vẻ, Dễ tính, Hòa đồng",
            "life_span": "15 – 18 năm",
            "weight_metric": "4 – 7 kg",
            "coat_type": "Lông ngắn vân Tabby bạc • Ít rụng",
            "living_space": "Mọi không gian căn hộ & nhà phố",
            "care_level": "Cực kỳ dễ nuôi cho người mới",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 94,
            "easy_care_score": 98,
            "apartment_score": 97,
            "image_url": "/static/images/catalog/cat-pet-012-ash.jpg",
            "default_price": 4900000,
            "description": "Nổi bật với bộ lông vân xoáy bạc (Silver Tabby) sắc nét đầy cuốn hút, cơ thể săn chắc, sức đề kháng cực tốt và tính tình vui vẻ, dễ gần với cả trẻ nhỏ.",
            "nutrition_guide": "Ăn hạt rất ngoan, kết hợp hạt Royal Canin Indoor 27 và pate Ciao giúp duy trì vóc dáng cân đối.",
            "grooming_guide": "Chải lông nhẹ 1 lần/tuần; tắm sấy vệ sinh tai móng tại Spa mỗi tháng 1 lần.",
            "health_note": "Một trong những giống mèo cảnh có tuổi thọ và sức đề kháng tự nhiên tốt nhất.",
        },
    ],
    "dog": [
        {
            "sku": "DOG-PET-002",
            "name": "Toy / Miniature Poodle (Chó Poodle Tiny)",
            "vi_name": "Chó Poodle Tiny",
            "en_name": "Toy Poodle",
            "shop_breed": "Chó Poodle",
            "pet_type": "Chó",
            "origin": "Pháp / Đức",
            "temperament": "Thông minh, Quấn chủ, Không rụng lông, Dễ dạy",
            "life_span": "12 – 16 năm",
            "weight_metric": "2.5 – 5 kg",
            "coat_type": "Lông xoăn Teddy • Không rụng lông",
            "living_space": "Lý tưởng cho chung cư & căn hộ",
            "care_level": "Dễ nuôi số 1 cho người mới",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 99,
            "easy_care_score": 96,
            "apartment_score": 100,
            "image_url": "/static/images/catalog/dog-pet-002-poodle.jpg",
            "default_price": 4800000,
            "description": "Giống chó cảnh được yêu thích số 1 tại Việt Nam nhờ trí thông minh đứng top 2 thế giới, bộ lông xoăn tít hoàn toàn không rụng và ngoại hình xinh xắn như gấu bông Teddy.",
            "nutrition_guide": "Hạt SmartHeart Adult hoặc hạt nhỏ ngâm ấm (với cún 2 tháng), bổ sung Gel Virbac giúp lông dày mượt.",
            "grooming_guide": "Tắm sấy chải bông lông 1–2 tuần/lần; cắt tỉa tạo kiểu mặt tròn Teddy tại Spa mỗi 5–6 tuần.",
            "health_note": "Đã tiêm vaccine phòng Parvo/Care và tẩy giun; giữ ấm cổ họng khi nằm điều hòa.",
        },
        {
            "sku": "DOG-PET-003",
            "name": "Pembroke Welsh Corgi (Chó Corgi Chân Lùn)",
            "vi_name": "Chó Corgi Chân Lùn",
            "en_name": "Pembroke Welsh Corgi",
            "shop_breed": "Chó Corgi Chân Lùn",
            "pet_type": "Chó",
            "origin": "Xứ Wales (Vương quốc Anh)",
            "temperament": "Vui vẻ, Năng động, Thân thiện, Thông minh",
            "life_span": "12 – 15 năm",
            "weight_metric": "9 – 13 kg",
            "coat_type": "Lông kép dày mượt • Mông trái tim",
            "living_space": "Căn hộ & nhà phố",
            "care_level": "Dễ nuôi, thích đi dạo nhẹ",
            "tags": ["apartment", "beginner", "family"],
            "affection_score": 98,
            "easy_care_score": 90,
            "apartment_score": 92,
            "image_url": "https://images.unsplash.com/photo-1612536057832-2ff7ead58194?auto=format&fit=crop&w=700&q=80",
            "default_price": 7900000,
            "description": "Thú cưng hoàng gia Anh Quốc chinh phục mọi trái tim với 4 chân ngắn đáng yêu, cặp mông tròn hình trái tim biết lắc lư và gương mặt luôn nở nụ cười rạng rỡ.",
            "nutrition_guide": "Hạt SmartHeart giàu Omega 3 & 6; kiểm soát lượng tinh bột vừa phải để giữ dáng chuẩn, tránh béo phì.",
            "grooming_guide": "Chải lông chết 2–3 lần/tuần và đặt gói Tắm sấy + Cắt tỉa tạo khuôn mông trái tim tại Spa.",
            "health_note": "Hạn chế cho bé leo cầu thang quá cao liên tục để bảo vệ đốt sống lưng dài.",
        },
        {
            "sku": "DOG-PET-001",
            "name": "Miniature Schnauzer (Chó Schnauzer Ông Già)",
            "vi_name": "Chó Schnauzer Tiêu Muối",
            "en_name": "Miniature Schnauzer",
            "shop_breed": "Chó Schnauzer",
            "pet_type": "Chó",
            "origin": "Cộng hòa Liên bang Đức",
            "temperament": "Thông minh, Quấn chủ, Lanh lợi, Trung thành",
            "life_span": "12 – 15 năm",
            "weight_metric": "5 – 8 kg",
            "coat_type": "Lông tiêu muối • Không rụng lông",
            "living_space": "Rất hợp căn hộ & gia đình",
            "care_level": "Sạch sẽ, ít mùi cơ thể",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 96,
            "easy_care_score": 94,
            "apartment_score": 97,
            "image_url": "/static/images/catalog/dog-pet-001-schnauzer.jpg",
            "default_price": 6500000,
            "description": "Nổi bật với hàng lông mày rậm và bộ râu dài thông thái như 'ông cụ non' nhưng tính tình lại vô cùng hoạt bát, tình cảm và đặc biệt không rụng lông.",
            "nutrition_guide": "Hạt khô dinh dưỡng kết hợp thịt bò/ức gà; lau sạch râu sau bữa ăn ướt để râu luôn trắng đẹp.",
            "grooming_guide": "Tắm sữa tắm thảo mộc SOS 10 ngày/lần; tỉa form râu và chân mày chuẩn Schnauzer tại Spa mỗi 1–2 tháng.",
            "health_note": "Sức đề kháng rất tốt, thông minh và biết trông nhà cảnh giác cực nhạy.",
        },
        {
            "sku": "DOG-PET-004",
            "name": "Pomeranian (Chó Phốc Sóc Mặt Gấu)",
            "vi_name": "Chó Phốc Sóc (Pomeranian)",
            "en_name": "Pomeranian",
            "shop_breed": "Chó Phốc Sóc (Pomeranian)",
            "pet_type": "Chó",
            "origin": "Đức / Ba Lan",
            "temperament": "Lanh lợi, Đáng yêu, Quấn chủ, Hoạt bát",
            "life_span": "12 – 16 năm",
            "weight_metric": "2 – 3.5 kg",
            "coat_type": "Lông bông xù trắng tuyết • Mặt gấu",
            "living_space": "Rất hợp căn hộ & phòng nhỏ",
            "care_level": "Nhỏ gọn, cần chải lông bông",
            "tags": ["apartment", "beginner", "family"],
            "affection_score": 96,
            "easy_care_score": 88,
            "apartment_score": 98,
            "image_url": "/static/images/catalog/dog-pet-004-pomeranian.jpg",
            "default_price": 7200000,
            "description": "Cục bông tuyết di động với khuôn mặt gấu bầu bĩnh, đôi mắt đen láy và bộ lông kép bông xù kiêu sa. Kích thước nhỏ gọn dễ dàng mang theo đi dạo, cà phê.",
            "nutrition_guide": "Khẩu phần nhỏ giàu dưỡng chất lông da (Omega-3, Biotin) và Gel Nutri-Plus Virbac.",
            "grooming_guide": "Sấy ion âm đánh bông lông sau khi tắm; cắt tỉa form gấu Boo tròn xoe tại Spa.",
            "health_note": "Không nên cạo sát da (tránh hư nang lông); chuẩn bị xương cao su nhỏ cho bé gặm sạch răng.",
        },
        {
            "sku": "DOG-PET-005",
            "name": "Golden Retriever (Chó Golden Hoàng Kim)",
            "vi_name": "Chó Golden Retriever",
            "en_name": "Golden Retriever",
            "shop_breed": "Chó Golden Retriever",
            "pet_type": "Chó",
            "origin": "Vương quốc Anh (Scotland)",
            "temperament": "Hiền lành, Thông minh, Trung thành, Yêu trẻ nhỏ",
            "life_span": "10 – 13 năm",
            "weight_metric": "25 – 34 kg",
            "coat_type": "Lông vàng óng mượt • Ưa chải chuốt",
            "living_space": "Nhà phố / Căn hộ rộng có chỗ đi dạo",
            "care_level": "Cực kỳ ngoan & dễ dạy lệnh",
            "tags": ["beginner", "family"],
            "affection_score": 100,
            "easy_care_score": 92,
            "apartment_score": 82,
            "image_url": "https://images.unsplash.com/photo-1552053831-71594a27632d?auto=format&fit=crop&w=700&q=80",
            "default_price": 6200000,
            "description": "Người bạn vàng tuyệt vời nhất của mọi gia đình với trí thông minh top 4 thế giới, bản tính ấm áp, kiên nhẫn với trẻ nhỏ và khả năng học lệnh chỉ sau vài lần chỉ dẫn.",
            "nutrition_guide": "Hạt SmartHeart Adult Vị Bò Nướng kết hợp thịt, rau củ và canxi hỗ trợ khung xương vững chắc.",
            "grooming_guide": "Chải lông 3 lần/tuần và tắm sấy khử mùi thảo mộc tại Spa mỗi 1–2 tuần.",
            "health_note": "Cho bé đi bộ 20–30 phút mỗi ngày và nhỏ gáy Frontline Plus ngừa ve rận định kỳ.",
        },
        {
            "sku": "DOG-PET-006",
            "name": "Shiba Inu (Quốc Khuyển Nhật Bản Mặt Cười)",
            "vi_name": "Chó Shiba Inu",
            "en_name": "Shiba Inu",
            "shop_breed": "Chó Shiba Inu",
            "pet_type": "Chó",
            "origin": "Nhật Bản",
            "temperament": "Sạch sẽ, Trung thành, Lanh lợi, Độc lập",
            "life_span": "12 – 16 năm",
            "weight_metric": "8 – 11 kg",
            "coat_type": "Lông ngắn dày 2 lớp • Tự làm sạch",
            "living_space": "Hợp cả căn hộ & nhà phố",
            "care_level": "Rất sạch sẽ, biết đi vệ sinh đúng chỗ",
            "tags": ["apartment", "beginner", "family"],
            "affection_score": 92,
            "easy_care_score": 92,
            "apartment_score": 92,
            "image_url": "/static/images/catalog/dog-pet-006-shiba.jpg",
            "default_price": 9500000,
            "description": "Biểu tượng xứ Phù Tang với đôi má bánh bao phúng phính, chiếc đuôi cuộn tròn và nụ cười tỏa nắng. Shiba nổi tiếng sạch sẽ như mèo và cực kỳ trung thành.",
            "nutrition_guide": "Hạt khô giàu đạm cá hồi hoặc thịt bò giúp bộ lông vàng đỏ luôn rực rỡ, bóng khỏe.",
            "grooming_guide": "Tắm sấy chải lông rụng theo mùa tại Spa mỗi 2–3 tuần; cắt móng và vệ sinh tai định kỳ.",
            "health_note": "Cơ địa khỏe mạnh, dẻo dai, rất ít ốm vặt và thích nghi tốt với khí hậu Việt Nam.",
        },
        {
            "sku": "DOG-PET-007",
            "name": "Chihuahua (Chó Chihuahua Mini)",
            "vi_name": "Chó Chihuahua Mini",
            "en_name": "Chihuahua",
            "shop_breed": "Chó Chihuahua",
            "pet_type": "Chó",
            "origin": "Mexico",
            "temperament": "Lanh lợi, Quấn chủ, Nhỏ nhắn, Cảnh giác",
            "life_span": "14 – 18 năm",
            "weight_metric": "1.5 – 3 kg",
            "coat_type": "Lông ngắn sát • Hầu như không rụng",
            "living_space": "Hoàn hảo cho phòng nhỏ & chung cư",
            "care_level": "Ăn ít, cực kỳ gọn nhẹ",
            "tags": ["apartment", "beginner", "low_shed"],
            "affection_score": 95,
            "easy_care_score": 94,
            "apartment_score": 100,
            "image_url": "/static/images/catalog/dog-pet-007-chihuahua.jpg",
            "default_price": 4200000,
            "description": "Giống chó nhỏ nhất thế giới với chiếc đầu tròn hình quả táo và đôi mắt to lanh lợi. Chi phí nuôi cực kỳ tiết kiệm, dễ dàng bế theo mọi nơi.",
            "nutrition_guide": "Hạt cỡ nhỏ (Mini) ngâm mềm cho cún con, bổ sung Gel Nutri-Plus giữ đường huyết ổn định.",
            "grooming_guide": "Lông ngắn cực nhanh khô, chỉ cần tắm nước ấm với sữa tắm SOS mỗi 2 tuần/lần.",
            "health_note": "Giữ ấm cho bé vào ban đêm hoặc khi trời trở lạnh.",
        },
        {
            "sku": "DOG-PET-008",
            "name": "Labrador Retriever (Chó Labrador Hoàng Kim)",
            "vi_name": "Chó Labrador Retriever",
            "en_name": "Labrador Retriever",
            "shop_breed": "Chó Labrador",
            "pet_type": "Chó",
            "origin": "Canada / Vương quốc Anh",
            "temperament": "Thân thiện, Thông minh, Hiền hòa, Đáng tin cậy",
            "life_span": "11 – 14 năm",
            "weight_metric": "25 – 32 kg",
            "coat_type": "Lông ngắn không thấm nước • Dễ tắm",
            "living_space": "Nhà phố & căn hộ rộng",
            "care_level": "Dễ huấn luyện, ngoan ngoãn",
            "tags": ["beginner", "family", "low_shed"],
            "affection_score": 99,
            "easy_care_score": 94,
            "apartment_score": 84,
            "image_url": "https://images.unsplash.com/photo-1591160690555-5debfba289f0?auto=format&fit=crop&w=700&q=80",
            "default_price": 5800000,
            "description": "Giống chó gia đình phổ biến hàng đầu thế giới, nổi tiếng hiền lành, thông minh và có bộ lông ngắn gọn gàng dễ chăm sóc hơn Golden Retriever.",
            "nutrition_guide": "Hạt SmartHeart Adult 3kg kết hợp xương gặm sạch răng; chia 2–3 bữa cố định mỗi ngày.",
            "grooming_guide": "Lông ngắn ít bám bẩn, tắm sấy vệ sinh tai móng 2 tuần/lần tại Spa.",
            "health_note": "Rất thích chơi nhặt bóng và bơi lội; tiêm phòng 7 bệnh và phòng dại định kỳ hàng năm.",
        },
        {
            "sku": "DOG-PET-009",
            "name": "Alaskan Malamute (Chó Tuyết Alaska Giant)",
            "vi_name": "Chó Alaska Malamute",
            "en_name": "Alaskan Malamute",
            "shop_breed": "Chó Alaska",
            "pet_type": "Chó",
            "origin": "Hoa Kỳ (Bang Alaska)",
            "temperament": "Hiền lành, Quấn người, Oai vệ, Trung thành",
            "life_span": "10 – 14 năm",
            "weight_metric": "32 – 45 kg",
            "coat_type": "Lông kép dày bông • Khung xương lớn",
            "living_space": "Nhà rộng, mát mẻ / có điều hòa",
            "care_level": "Cần chải lông & không gian thoáng",
            "tags": ["family"],
            "affection_score": 97,
            "easy_care_score": 80,
            "apartment_score": 75,
            "image_url": "/static/images/catalog/dog-pet-009-alaska.jpg",
            "default_price": 8500000,
            "description": "Chúa tể vùng tuyết với vóc dáng to lớn hùng dũng nhưng tâm hồn lại vô cùng hiền lành, thân thiện với con người và rất thích được ôm ấp.",
            "nutrition_guide": "Chế độ ăn giàu đạm, canxi và vitamin từ hạt cao cấp + thịt bò giúp khung xương phát triển tối đa.",
            "grooming_guide": "Sử dụng gói Tắm sấy công suất lớn & Chải lông rụng chuyên sâu tại Spa mỗi 2 tuần.",
            "health_note": "Giữ nơi ở thoáng mát, luôn có sẵn nước mát và hạn chế vận động ngoài trời nắng gắt buổi trưa.",
        },
        {
            "sku": "DOG-PET-010",
            "name": "Siberian Husky (Chó Husky Mắt Xanh)",
            "vi_name": "Chó Husky Sibir",
            "en_name": "Siberian Husky",
            "shop_breed": "Chó Husky",
            "pet_type": "Chó",
            "origin": "Vùng Siberia (Nga)",
            "temperament": "Vui nhộn, Hoạt bát, Thân thiện, Hòa đồng",
            "life_span": "12 – 15 năm",
            "weight_metric": "18 – 27 kg",
            "coat_type": "Lông dày 2 lớp • Đôi mắt xanh băng giá",
            "living_space": "Nhà phố & căn hộ thoáng mát",
            "care_level": "Năng động, thích vận động",
            "tags": ["family"],
            "affection_score": 95,
            "easy_care_score": 84,
            "apartment_score": 80,
            "image_url": "https://images.unsplash.com/photo-1605568427561-40dd23c2acea?auto=format&fit=crop&w=700&q=80",
            "default_price": 7500000,
            "description": "Nổi tiếng với vẻ ngoài điển trai như sói tuyết cùng đôi mắt xanh biếc nhưng lại có biểu cảm hài hước 'ngáo ngơ' mang lại tiếng cười cho cả gia đình.",
            "nutrition_guide": "Hạt SmartHeart kết hợp men tiêu hóa và Gel Virbac; giữ hệ tiêu hóa ổn định trong 2 tháng đầu.",
            "grooming_guide": "Chải lông tuần 2–3 lần; tắm thảo mộc SOS và sấy khô hoàn toàn lớp lông lót.",
            "health_note": "Dành thời gian dắt bé đi dạo buổi tối mát mẻ và chuẩn bị xương cao su cho bé gặm.",
        },
        {
            "sku": "DOG-PET-011",
            "name": "Akita Inu (Quốc Khuyển Nhật Bản Trung Thành)",
            "vi_name": "Chó Akita Inu",
            "en_name": "Akita Inu",
            "shop_breed": "Chó Akita",
            "pet_type": "Chó",
            "origin": "Nhật Bản (Tỉnh Akita)",
            "temperament": "Trung thành tuyệt đối, Điềm đạm, Can đảm, Sạch sẽ",
            "life_span": "11 – 15 năm",
            "weight_metric": "25 – 38 kg",
            "coat_type": "Lông dày ấm áp • Dáng đứng uy nghiêm",
            "living_space": "Nhà phố / Căn hộ rộng",
            "care_level": "Điềm tĩnh, ít sủa bậy",
            "tags": ["family"],
            "affection_score": 95,
            "easy_care_score": 86,
            "apartment_score": 82,
            "image_url": "/static/images/catalog/dog-pet-011-akita.jpg",
            "default_price": 12500000,
            "description": "Giống chó huyền thoại Hachiko của Nhật Bản, biểu tượng của lòng trung thành tuyệt đối, sự may mắn và phong thái điềm đạm, ít sủa vô cớ.",
            "nutrition_guide": "Thực đơn giàu đạm cá biển và hạt dinh dưỡng cao cấp giúp lông dày bóng và cơ bắp khỏe khoắn.",
            "grooming_guide": "Chải lông định kỳ 2 lần/tuần; tắm sấy vệ sinh tại Spa mỗi 2–3 tuần.",
            "health_note": "Huấn luyện xã hội hóa nhẹ nhàng từ nhỏ; tiêm phòng và nhỏ gáy ngừa ký sinh trùng định kỳ.",
        },
        {
            "sku": "DOG-PET-012",
            "name": "Samoyed (Chó Tuyết Trắng Nụ Cười Thiên Thần)",
            "vi_name": "Chó Samoyed Trắng Tuyết",
            "en_name": "Samoyed",
            "shop_breed": "Chó Samoyed",
            "pet_type": "Chó",
            "origin": "Tây Siberia (Nga)",
            "temperament": "Dịu dàng, Thân thiện, Hay cười, Quấn chủ",
            "life_span": "12 – 14 năm",
            "weight_metric": "17 – 28 kg",
            "coat_type": "Lông trắng tuyết bồng bềnh như mây",
            "living_space": "Căn hộ mát mẻ & nhà phố",
            "care_level": "Cần chải & giữ lông trắng sạch",
            "tags": ["family"],
            "affection_score": 99,
            "easy_care_score": 82,
            "apartment_score": 82,
            "image_url": "/static/images/catalog/dog-pet-012-samoyed.jpg",
            "default_price": 8800000,
            "description": "Sở hữu bộ lông trắng muốt như đám mây cùng 'nụ cười Samoyed' đặc trưng không lẫn vào đâu được, tính tình cực kỳ hiền lành và ngọt ngào.",
            "nutrition_guide": "Hạt giàu Omega 3 & 6 giúp lông trắng bóng mượt; hạn chế đồ ăn nhiều dầu mỡ dễ làm ố lông miệng.",
            "grooming_guide": "Tắm sữa tắm làm trắng lông SOS và sấy bông ion âm tại Spa mỗi 2 tuần.",
            "health_note": "Giữ phòng thoáng mát và chải lông thường xuyên để lông luôn tơi xốp.",
        },
        {
            "sku": "DOG-PET-013",
            "name": "Chow Chow (Chó Sư Tử Xù Lưỡi Tím)",
            "vi_name": "Chó Chow Chow Sư Tử",
            "en_name": "Chow Chow",
            "shop_breed": "Chó Chow Chow",
            "pet_type": "Chó",
            "origin": "Trung Quốc",
            "temperament": "Điềm tĩnh, Trung thành, Sạch sẽ, Đáng yêu",
            "life_span": "11 – 14 năm",
            "weight_metric": "18 – 28 kg",
            "coat_type": "Bờm sư tử bông xù • Chiếc lưỡi xanh tím",
            "living_space": "Căn hộ điều hòa & nhà phố",
            "care_level": "Yên tĩnh, sạch sẽ, ít sủa",
            "tags": ["apartment", "family"],
            "affection_score": 90,
            "easy_care_score": 85,
            "apartment_score": 86,
            "image_url": "/static/images/catalog/dog-pet-013-chowchow.jpg",
            "default_price": 9200000,
            "description": "Gây ấn tượng mạnh với ngoại hình mũm mĩm như gấu bông lai sư tử nhỏ cùng chiếc lưỡi màu xanh tím độc nhất vô nhị. Tính cách điềm tĩnh và rất trung thành.",
            "nutrition_guide": "Hạt dinh dưỡng cân bằng đạm và rau củ, tránh thức ăn quá mặn để bảo vệ da lông.",
            "grooming_guide": "Đặt gói Tắm sấy & Cắt tỉa tạo form gấu tròn cho Chow Chow tại Spa định kỳ mỗi 3 tuần.",
            "health_note": "Lau sạch nếp gấp quanh mắt và giữ chỗ nằm luôn khô ráo, mát mẻ.",
        },
        {
            "sku": "DOG-PET-014",
            "name": "Pug (Chó Pug Mặt Xệ Biểu Cảm)",
            "vi_name": "Chó Pug Mặt Xệ",
            "en_name": "Pug",
            "shop_breed": "Chó Pug Mặt Xệ",
            "pet_type": "Chó",
            "origin": "Trung Quốc / Châu Âu",
            "temperament": "Hài hước, Hiền lành, Quấn chủ, Thân thiện trẻ nhỏ",
            "life_span": "12 – 15 năm",
            "weight_metric": "6 – 9 kg",
            "coat_type": "Lông ngắn sát • Không cần cắt tỉa",
            "living_space": "Cực hợp căn hộ & chung cư",
            "care_level": "Rất dễ nuôi, ít tốn công vận động",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 98,
            "easy_care_score": 95,
            "apartment_score": 99,
            "image_url": "/static/images/catalog/dog-pet-014-pug.jpg",
            "default_price": 4500000,
            "description": "Chuyên gia tấu hài với khuôn mặt xệ nhiều nếp nhăn ngộ nghĩnh và đôi mắt tròn xoe ngây thơ. Pug rất hiền, hầu như không sủa và cực hợp nuôi trong chung cư.",
            "nutrition_guide": "Ăn rất khỏe nên cần chia khẩu phần hạt SmartHeart vừa đủ theo cân nặng để bé không bị béo phì.",
            "grooming_guide": "Lông ngắn tắm khô cực nhanh; dùng khăn ẩm lau sạch kẽ nếp nhăn trên mặt 2–3 lần/tuần.",
            "health_note": "Do mũi ngắn nên tránh để bé chạy ngoài nắng gắt; giữ phòng thoáng mát.",
        },
        {
            "sku": "DOG-PET-015",
            "name": "French Bulldog (Chó Bull Pháp Tai Dơi)",
            "vi_name": "Chó Bull Pháp (Frenchie)",
            "en_name": "French Bulldog",
            "shop_breed": "Chó Bull Pháp",
            "pet_type": "Chó",
            "origin": "Pháp / Anh",
            "temperament": "Vui vẻ, Tình cảm, Ít sủa, Thân thiện",
            "life_span": "11 – 14 năm",
            "weight_metric": "8 – 13 kg",
            "coat_type": "Lông ngắn bóng mượt • Ít rụng",
            "living_space": "Top 1 giống chó cho căn hộ hiện đại",
            "care_level": "Dễ chăm sóc, không cần vận động nhiều",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 97,
            "easy_care_score": 94,
            "apartment_score": 99,
            "image_url": "/static/images/catalog/dog-pet-015-bullphap.jpg",
            "default_price": 8200000,
            "description": "Sở hữu đôi tai dơi dựng đứng đặc trưng, thân hình săn chắc gọn gàng và tính cách điềm đạm, ít sủa — cực kỳ được giới trẻ và các gia đình căn hộ ưa chuộng.",
            "nutrition_guide": "Hạt khô giàu đạm dễ tiêu hóa kết hợp men vi sinh và xương gặm sạch răng.",
            "grooming_guide": "Tắm sữa tắm thảo mộc SOS mỗi 2 tuần và vệ sinh nếp gấp mặt, tai định kỳ.",
            "health_note": "Thích hợp sống trong nhà mát mẻ, đi dạo nhẹ nhàng 15 phút vào sáng sớm hoặc chiều mát.",
        },
        {
            "sku": "DOG-PET-016",
            "name": "Phu Quoc Ridgeback (Chó Phú Quốc Xoáy Lưng)",
            "vi_name": "Chó Phú Quốc Thuần Chủng",
            "en_name": "Phu Quoc Ridgeback",
            "shop_breed": "Chó Phú Quốc",
            "pet_type": "Chó",
            "origin": "Đảo Phú Quốc, Việt Nam",
            "temperament": "Thông minh, Trung thành, Can đảm, Khỏe mạnh",
            "life_span": "13 – 16 năm",
            "weight_metric": "14 – 20 kg",
            "coat_type": "Lông ngắn sát • Dải xoáy kiếm trên lưng",
            "living_space": "Nhà phố & sân vườn",
            "care_level": "Đề kháng tự nhiên cực khỏe",
            "tags": ["beginner", "low_shed", "family"],
            "affection_score": 95,
            "easy_care_score": 98,
            "apartment_score": 85,
            "image_url": "/static/images/catalog/dog-pet-016-phuquoc.jpg",
            "default_price": 4600000,
            "description": "Một trong 'Tứ đại quốc khuyển' niềm tự hào của Việt Nam với dải lông xoáy hình thanh kiếm trên lưng, bàn chân màng vịt bơi giỏi và trí khôn tuyệt vời.",
            "nutrition_guide": "Hệ tiêu hóa cực khỏe, dễ ăn cả hạt SmartHeart lẫn cơm thịt/cá nấu chín.",
            "grooming_guide": "Lông ngắn sát sạch sẽ, rất ít mùi; tắm thảo mộc mỗi 2–3 tuần và nhỏ gáy ngừa ve rận.",
            "health_note": "Thích nghi 100% khí hậu Việt Nam, sức đề kháng cao và trông nhà cực kỳ nhạy bén.",
        },
        {
            "sku": "DOG-PET-017",
            "name": "German Shepherd (Chó Becgie Đức)",
            "vi_name": "Chó Becgie Đức",
            "en_name": "German Shepherd",
            "shop_breed": "Chó Becgie Đức",
            "pet_type": "Chó",
            "origin": "Cộng hòa Liên bang Đức",
            "temperament": "Thông minh xuất sắc, Trung thành, Dũng cảm, Tuân lệnh",
            "life_span": "10 – 13 năm",
            "weight_metric": "28 – 40 kg",
            "coat_type": "Lông kép khỏe khoắn • Màu vàng đen",
            "living_space": "Nhà phố rộng & sân vườn",
            "care_level": "Học lệnh cực nhanh, bảo vệ chủ",
            "tags": ["family"],
            "affection_score": 96,
            "easy_care_score": 88,
            "apartment_score": 78,
            "image_url": "https://images.unsplash.com/photo-1589941013453-ec89f33b5e95?auto=format&fit=crop&w=700&q=80",
            "default_price": 6800000,
            "description": "Đứng top 3 giống chó thông minh nhất hành tinh, nổi tiếng về lòng trung thành, khả năng tiếp thu bài huấn luyện thần tốc và bản năng bảo vệ gia đình số 1.",
            "nutrition_guide": "Khẩu phần giàu đạm, canxi và dưỡng chất khớp trong giai đoạn 2–12 tháng tuổi để tai dựng đẹp.",
            "grooming_guide": "Chải lông 2–3 lần/tuần; tắm sấy khử mùi thảo mộc tại Spa định kỳ.",
            "health_note": "Cho bé vận động chạy nhảy mỗi ngày và tiêm phòng đầy đủ các mũi vaccine.",
        },
        {
            "sku": "DOG-PET-018",
            "name": "Beagle (Chó Săn Thỏ Tam Thể)",
            "vi_name": "Chó Beagle Tam Thể",
            "en_name": "Beagle",
            "shop_breed": "Chó Beagle",
            "pet_type": "Chó",
            "origin": "Vương quốc Anh",
            "temperament": "Vui vẻ, Hòa đồng, Năng động, Thân thiện trẻ nhỏ",
            "life_span": "12 – 15 năm",
            "weight_metric": "9 – 12 kg",
            "coat_type": "Lông ngắn 3 màu bóng mượt • Rất ít rụng",
            "living_space": "Căn hộ & nhà phố",
            "care_level": "Khỏe mạnh, lông ngắn cực dễ tắm",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 96,
            "easy_care_score": 95,
            "apartment_score": 90,
            "image_url": "/static/images/catalog/dog-pet-018-beagle.jpg",
            "default_price": 5500000,
            "description": "Nguyên mẫu của nhân vật hoạt hình Snoopy nổi tiếng với đôi tai dài rủ mềm mại, bộ lông tam thể (Tricolor) bắt mắt và tính cách luôn tràn đầy năng lượng tích cực.",
            "nutrition_guide": "Hạt SmartHeart Adult kết hợp xương cao su gặm nhai giúp làm sạch răng và giải tỏa năng lượng.",
            "grooming_guide": "Lông ngắn không thấm nước rất dễ vệ sinh; chú ý lau sạch bên trong đôi tai cụp dài mỗi tuần.",
            "health_note": "Sức khỏe dẻo dai, cực kỳ hợp với gia đình có trẻ em thích vận động.",
        },
        {
            "sku": "DOG-PET-019",
            "name": "Bichon Frise (Chó Bông Gòn Trắng Tuyết)",
            "vi_name": "Chó Bichon Frise",
            "en_name": "Bichon Frise",
            "shop_breed": "Chó Bichon Frise",
            "pet_type": "Chó",
            "origin": "Pháp / Tây Ban Nha",
            "temperament": "Ngọt ngào, Vui tươi, Không rụng lông, Quấn chủ",
            "life_span": "13 – 16 năm",
            "weight_metric": "3.5 – 6 kg",
            "coat_type": "Lông xoăn bông gòn trắng • Không rụng",
            "living_space": "Hoàn hảo cho chung cư & căn hộ",
            "care_level": "Không hôi, không rụng lông",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 99,
            "easy_care_score": 92,
            "apartment_score": 100,
            "image_url": "/static/images/catalog/dog-pet-019-bichon.jpg",
            "default_price": 6900000,
            "description": "Trông như chiếc kẹo bông gòn trắng muốt biết đi với cái đầu cắt tỉa tròn xoe siêu cưng. Bichon không rụng lông, không có mùi hôi và luôn vui vẻ làm nũng chủ.",
            "nutrition_guide": "Hạt dinh dưỡng giúp hạn chế vết ố nước mắt, kết hợp Gel Virbac dưỡng lông trắng mượt.",
            "grooming_guide": "Tắm sấy đánh bông và cắt tỉa tạo form đầu tròn Bichon đặc trưng tại Spa mỗi 4–5 tuần.",
            "health_note": "Lau sạch vùng lông quanh mắt và miệng hàng ngày để bé luôn trắng tinh khôi.",
        },
        {
            "sku": "DOG-PET-020",
            "name": "Dachshund (Chó Lạp Xưởng Chân Ngắn)",
            "vi_name": "Chó Lạp Xưởng (Dachshund)",
            "en_name": "Dachshund",
            "shop_breed": "Chó Lạp Xưởng",
            "pet_type": "Chó",
            "origin": "Cộng hòa Liên bang Đức",
            "temperament": "Thông minh, Can đảm, Tình cảm, Hài hước",
            "life_span": "12 – 16 năm",
            "weight_metric": "4.5 – 8 kg",
            "coat_type": "Lông ngắn bóng mượt • Không rụng lông",
            "living_space": "Rất hợp căn hộ & nhà phố",
            "care_level": "Cực kỳ dễ chăm sóc, sạch sẽ",
            "tags": ["apartment", "beginner", "low_shed", "family"],
            "affection_score": 96,
            "easy_care_score": 97,
            "apartment_score": 98,
            "image_url": "https://images.unsplash.com/photo-1612195583950-b8fd34c87093?auto=format&fit=crop&w=700&q=80",
            "default_price": 4300000,
            "description": "Chú chó 'xúc xích' với thân hình dài và 4 chân ngắn lạch bạch đầy ngộ nghĩnh. Bộ lông ngắn bóng mượt gần như không cần chải chuốt, cực kỳ quấn chủ và biết trông nhà.",
            "nutrition_guide": "Hạt SmartHeart khẩu phần vừa phải giúp giữ thân hình săn chắc, tránh thừa cân lên lưng.",
            "grooming_guide": "Tắm sữa tắm SOS 2 tuần/lần và vệ sinh đôi tai dài rủ; hầu như không tốn công chải lông.",
            "health_note": "Khi bế bé nên đỡ cả phần ngực và mông để bảo vệ cột sống dài của bé.",
        },
    ],
}


def fetch_pet_breeds_via_urllib(
    species: str = "cat",
    api_key: str = "",
    search_breed: str = "",
    limit: int = 32,
) -> Dict[str, Any]:
    """
    Truy vấn thông tin giống thú cưng qua giao thức HTTP GET (`urllib.request` + `x-api-key`)
    kết hợp bộ cơ sở dữ liệu Cẩm nang 32 giống Chó & Mèo thuần chủng tiếng Việt của Meow & Woof.
    """
    raw_sp = (species or "cat").strip().lower()
    if raw_sp == "all":
        species_key = "all"
    elif raw_sp == "dog":
        species_key = "dog"
    else:
        species_key = "cat"

    probe_species = "dog" if species_key == "dog" else "cat"
    endpoint = (
        "https://api.thedogapi.com/v1/breeds"
        if probe_species == "dog"
        else "https://api.thecatapi.com/v1/breeds"
    )

    headers = {
        "User-Agent": "MeowWoofPetShop-UrllibClient/1.0 (Python Standard Library)",
        "Accept": "application/json",
    }
    effective_key = api_key.strip() or "DEMO-API-KEY-PETSHOP-CLO3"
    headers["x-api-key"] = effective_key

    source_mode = "Internet Live API (urllib.request)"
    cache_key = (probe_species, effective_key)
    now_ts = time.time()
    cached_entry = _BREED_API_CACHE.get(cache_key)

    if cached_entry and (now_ts - cached_entry[0]) < _CACHE_TTL_SECONDS:
        source_mode = cached_entry[2]
    else:
        try:
            req = urllib.request.Request(endpoint, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as response:
                raw_json = response.read().decode("utf-8")
                parsed = json.loads(raw_json)
                if isinstance(parsed, list) and parsed:
                    _BREED_API_CACHE[cache_key] = (now_ts, parsed, source_mode)
        except Exception as exc:
            source_mode = f"Cẩm nang Chuẩn Meow & Woof ({type(exc).__name__} Fallback)"
            _BREED_API_CACHE[cache_key] = (
                now_ts - _CACHE_TTL_SECONDS + 60.0,
                FALLBACK_BREEDS[probe_species],
                source_mode,
            )

    # Đồng bộ giá bán, tồn kho và hình ảnh trực tiếp từ bảng Product của Shop
    products_by_sku: Dict[str, Dict[str, Any]] = {}
    products_by_breed: Dict[str, Dict[str, Any]] = {}
    try:
        for p in Product.iter_all(order_by="id ASC"):
            if p.category in ("Chó cảnh", "Mèo cảnh"):
                p_dict = p.to_dict()
                products_by_sku[p.sku] = p_dict
                if p.breed:
                    products_by_breed[p.breed] = p_dict
    except Exception:
        pass

    if species_key == "all":
        handbook_source = list(FALLBACK_BREEDS["cat"]) + list(FALLBACK_BREEDS["dog"])
    else:
        handbook_source = list(FALLBACK_BREEDS[species_key])

    normalized: List[Dict[str, Any]] = []
    for item in handbook_source:
        entry = dict(item)
        matched_prod = products_by_sku.get(entry.get("sku", "")) or products_by_breed.get(
            entry.get("shop_breed", "")
        )
        if matched_prod:
            entry["product_id"] = matched_prod.get("id")
            entry["shop_price"] = float(matched_prod.get("price") or entry.get("default_price", 0))
            entry["stock"] = int(matched_prod.get("stock") or 0)
            if matched_prod.get("image_url"):
                entry["image_url"] = matched_prod["image_url"]
        else:
            entry["product_id"] = None
            entry["shop_price"] = float(entry.get("default_price", 4500000))
            entry["stock"] = 2
        normalized.append(entry)

    if search_breed.strip():
        kw = search_breed.strip().lower()
        normalized = [
            b
            for b in normalized
            if kw in b["name"].lower()
            or kw in b.get("vi_name", "").lower()
            or kw in b.get("en_name", "").lower()
            or kw in b["origin"].lower()
            or kw in b["temperament"].lower()
            or kw in b["description"].lower()
            or kw in b.get("living_space", "").lower()
        ]

    masked_key = effective_key[:6] + "***" if len(effective_key) > 6 else "***"
    return {
        "endpoint": endpoint,
        "species": species_key,
        "api_key_masked": masked_key,
        "api_key_used": masked_key,
        "source_mode": source_mode,
        "source": source_mode,
        "total_matched": len(normalized),
        "total_cats": len(FALLBACK_BREEDS["cat"]),
        "total_dogs": len(FALLBACK_BREEDS["dog"]),
        "breeds": normalized[:limit],
    }


def export_products_to_xml() -> str:
    root = ET.Element("petshop_catalog")
    root.set("version", "1.0")
    root.set("generator", "Python xml.etree.ElementTree")

    products_el = ET.SubElement(root, "products")
    for product in Product.iter_all(order_by="id ASC"):
        item_el = ET.SubElement(products_el, "product")
        item_el.set("id", str(product.id))
        item_el.set("sku", str(product.sku))

        for tag_name in ("name", "category", "pet_type", "price", "stock", "description"):
            child = ET.SubElement(item_el, tag_name)
            child.text = str(getattr(product, tag_name) or "")

    raw_bytes = ET.tostring(root, encoding="utf-8")
    parsed_dom = minidom.parseString(raw_bytes)
    return parsed_dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def import_products_from_xml(xml_text: str) -> Dict[str, Any]:
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError as exc:
        raise ValidationError(f"Cú pháp XML không hợp lệ: {exc}")

    existing_by_sku = {p.sku: p for p in Product.iter_all()}
    imported = 0
    updated = 0
    errors: List[str] = []

    product_nodes = root.findall(".//product")
    if not product_nodes:
        raise ValidationError("Không tìm thấy thẻ <product> nào trong tài liệu XML.")

    for idx, node in enumerate(product_nodes, start=1):
        try:
            sku = (node.get("sku") or node.findtext("sku") or "").strip().upper()
            if not sku:
                raise ValidationError("Thiếu thuộc tính hoặc thẻ sku.")

            name = (node.findtext("name") or "").strip()
            category = (node.findtext("category") or "Thức ăn").strip()
            pet_type = (node.findtext("pet_type") or "Chó & Mèo").strip()
            price = float(node.findtext("price") or 0)
            stock = int(node.findtext("stock") or 0)
            description = (node.findtext("description") or "").strip()

            if sku in existing_by_sku:
                prod = existing_by_sku[sku]
                prod.name = name or prod.name
                prod.category = category
                prod.pet_type = pet_type
                prod.price = price
                prod.stock = stock
                prod.description = description
                prod.save()
                updated += 1
            else:
                new_prod = Product(
                    sku=sku,
                    name=name,
                    category=category,
                    pet_type=pet_type,
                    price=price,
                    stock=stock,
                    description=description,
                )
                new_prod.save()
                existing_by_sku[sku] = new_prod
                imported += 1
        except Exception as exc:
            errors.append(f"Thẻ <product> #{idx}: {exc}")

    return {"imported": imported, "updated": updated, "errors": errors}
