"""
services/email_config.py
Quản lý cấu hình tài khoản SMTP và email nhận thông báo Admin.
"""

import json
import os
from typing import Any, Dict


def get_smtp_credentials() -> Dict[str, Any]:
    """Lấy thông tin tài khoản SMTP từ biến môi trường, .env hoặc data/smtp_config.json."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except (ValueError, TypeError):
        port = 587
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()

    if not user or not pwd:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for env_path in (os.path.join(base_dir, ".env"), os.path.join(os.path.dirname(base_dir), ".env")):
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip('"').strip("'")
                            if k == "SMTP_USER" and not user:
                                user = v
                            elif k == "SMTP_PASS" and not pwd:
                                pwd = v
                            elif k == "SMTP_HOST" and host == "smtp.gmail.com":
                                host = v
                            elif k == "SMTP_PORT":
                                try:
                                    port = int(v)
                                except ValueError:
                                    pass
                except Exception:
                    pass

    if not user or not pwd:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "smtp_config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    user = user or cfg.get("smtp_user", "").strip()
                    pwd = pwd or cfg.get("smtp_pass", "").strip()
                    host = cfg.get("smtp_host", host) or host
                    port = int(cfg.get("smtp_port", port) or port)
            except Exception:
                pass

    return {
        "smtp_host": host or "smtp.gmail.com",
        "smtp_port": port or 587,
        "smtp_user": user,
        "smtp_pass": pwd.replace(" ", ""),
    }


def save_smtp_credentials(smtp_user: str, smtp_pass: str, smtp_host: str = "smtp.gmail.com", smtp_port: int = 587) -> None:
    """Lưu cấu hình SMTP vào data/smtp_config.json và cập nhật biến môi trường tức thì."""
    cfg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, "smtp_config.json")

    clean_pass = smtp_pass.strip().replace(" ", "")
    data = {
        "smtp_user": smtp_user.strip(),
        "smtp_pass": clean_pass,
        "smtp_host": smtp_host.strip() or "smtp.gmail.com",
        "smtp_port": smtp_port,
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.environ["SMTP_USER"] = smtp_user.strip()
    os.environ["SMTP_PASS"] = clean_pass
    os.environ["SMTP_HOST"] = smtp_host.strip() or "smtp.gmail.com"
    os.environ["SMTP_PORT"] = str(smtp_port)


def get_admin_notification_email() -> str:
    """Lấy địa chỉ Email nhận thông báo của Admin."""
    admin_mail = os.environ.get("ADMIN_NOTIFICATION_EMAIL", "").strip()
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "admin_settings.json")
    if not admin_mail and os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                admin_mail = json.load(f).get("admin_notification_email", "").strip()
        except Exception:
            pass
    if not admin_mail:
        creds = get_smtp_credentials()
        admin_mail = creds.get("smtp_user") or "admin@meowandwoof.vn"
    return admin_mail


def set_admin_notification_email(email_addr: str) -> None:
    """Lưu địa chỉ Email nhận thông báo của Admin vào data/admin_settings.json."""
    clean_mail = email_addr.strip()
    cfg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(cfg_dir, exist_ok=True)
    cfg_path = os.path.join(cfg_dir, "admin_settings.json")
    data = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data["admin_notification_email"] = clean_mail
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.environ["ADMIN_NOTIFICATION_EMAIL"] = clean_mail

