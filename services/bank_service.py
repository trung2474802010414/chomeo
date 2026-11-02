"""
services/bank_service.py
Quản lý cấu hình tài khoản ngân hàng và tạo mã VietQR tự động.
"""

import json
import os
from typing import Any, Dict, List

BANK_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bank_config.json"
)

SUPPORTED_BANKS: List[Dict[str, str]] = [
    {"bin": "970422", "code": "970422", "short_name": "MB", "name": "MB Bank (Ngân hàng Quân Đội)"},
    {"bin": "970436", "code": "970436", "short_name": "VCB", "name": "Vietcombank (Ngoại Thương)"},
    {"bin": "970407", "code": "970407", "short_name": "TCB", "name": "Techcombank (Kỹ Thương)"},
    {"bin": "970416", "code": "970416", "short_name": "ACB", "name": "ACB (Á Châu)"},
    {"bin": "970432", "code": "970432", "short_name": "VPB", "name": "VPBank (Việt Nam Thịnh Vượng)"},
    {"bin": "970423", "code": "970423", "short_name": "TPB", "name": "TPBank (Tiên Phong)"},
    {"bin": "970418", "code": "970418", "short_name": "BIDV", "name": "BIDV (Đầu tư & Phát triển)"},
    {"bin": "970415", "code": "970415", "short_name": "CTG", "name": "VietinBank (Công Thương)"},
    {"bin": "970405", "code": "970405", "short_name": "VBA", "name": "Agribank (Nông Nghiệp & PTNT)"},
    {"bin": "970443", "code": "970443", "short_name": "SHB", "name": "SHB (Sài Gòn - Hà Nội)"},
    {"bin": "970437", "code": "970437", "short_name": "HDB", "name": "HDBank (Phát triển TP.HCM)"},
    {"bin": "970426", "code": "970426", "short_name": "MSB", "name": "MSB (Hàng Hải)"},
    {"bin": "970441", "code": "970441", "short_name": "VIB", "name": "VIB (Quốc Tế)"},
    {"bin": "970403", "code": "970403", "short_name": "STB", "name": "Sacombank (Sài Gòn Thương Tín)"},
]

DEFAULT_BANK_CONFIG: Dict[str, Any] = {
    "bank_bin": "970422",
    "bank_name": "MB Bank (Ngân hàng Quân Đội)",
    "account_number": "0905123456",
    "account_name": "MEOW AND WOOF PET HOUSE",
    "syntax_prefix": "MEOW",
    "template": "compact2",
    "is_active": True,
}


def get_bank_config() -> Dict[str, Any]:
    """Lấy cấu hình ngân hàng hiện tại, trả về mặc định nếu chưa cấu hình."""
    if os.path.exists(BANK_CONFIG_PATH):
        try:
            with open(BANK_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = dict(DEFAULT_BANK_CONFIG)
                merged.update(data)
                return merged
        except Exception:
            pass
    return dict(DEFAULT_BANK_CONFIG)


def save_bank_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Lưu cấu hình ngân hàng do Quản trị viên tùy chỉnh vào file JSON."""
    os.makedirs(os.path.dirname(BANK_CONFIG_PATH), exist_ok=True)
    current = get_bank_config()
    current["bank_bin"] = str(payload.get("bank_bin", current["bank_bin"])).strip()
    current["bank_name"] = str(payload.get("bank_name", current["bank_name"])).strip()
    current["account_number"] = str(
        payload.get("account_number", current["account_number"])
    ).strip()
    current["account_name"] = (
        str(payload.get("account_name", current["account_name"])).strip().upper()
    )
    current["syntax_prefix"] = (
        str(payload.get("syntax_prefix", current["syntax_prefix"])).strip().upper() or "MEOW"
    )
    current["template"] = str(payload.get("template", "compact2")).strip()
    current["is_active"] = bool(payload.get("is_active", True))

    with open(BANK_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    return current


def generate_vietqr_url(amount: float, memo: str) -> str:
    """Tạo link ảnh VietQR Napas247 động theo cấu hình ngân hàng hiện tại."""
    cfg = get_bank_config()
    bin_code = cfg.get("bank_bin", "970422")
    acc_num = cfg.get("account_number", "0905123456")
    template = cfg.get("template", "compact2")
    acc_name = cfg.get("account_name", "MEOW AND WOOF PET HOUSE")

    memo_clean = memo.strip()
    import urllib.parse

    encoded_memo = urllib.parse.quote(memo_clean)
    encoded_name = urllib.parse.quote(acc_name)
    amt_int = int(amount)

    return (
        f"https://api.vietqr.io/image/{bin_code}-{acc_num}-{template}.png"
        f"?amount={amt_int}&addInfo={encoded_memo}&accountName={encoded_name}"
    )
