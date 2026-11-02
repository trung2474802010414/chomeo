"""
check_rules.py
Script chạy thử nghiệm và kiểm tra toàn bộ các quy tắc trong thư mục `.claude/rules/`:
1. Kiểm tra kích thước file < 200 dòng (file-size.md)
2. Quét rò rỉ file nhạy cảm & .env (precomit.md)
3. Chạy toàn bộ Test Suite (CLAUDE.MD)
"""

import os
import sys
import subprocess
import unittest

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def print_header(title: str) -> None:
    print(f"\n{BLUE}============================================================{RESET}")
    print(f"{BLUE}▶ {title}{RESET}")
    print(f"{BLUE}============================================================{RESET}")


def check_file_sizes(max_lines: int = 200) -> bool:
    print_header(f"1. KIỂM TRA FILE SIZE (file-size.md: tối đa {max_lines} dòng)")
    target_dirs = ["core", "forms", "models", "services"]
    over_limit_files = []

    for d in target_dirs:
        dir_path = os.path.join(BASE_DIR, d)
        if not os.path.exists(dir_path):
            continue
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, BASE_DIR)
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = len(f.readlines())
                    if lines > max_lines:
                        over_limit_files.append((rel_path, lines))
                    else:
                        print(f"  {GREEN}✓{RESET} {rel_path} ({lines} dòng)")

    if over_limit_files:
        print(f"\n{YELLOW}⚠️  Cảnh báo: Có {len(over_limit_files)} file vượt quá {max_lines} dòng:{RESET}")
        for path, count in over_limit_files:
            print(f"  {YELLOW}• {path}: {count} dòng (Cần cân nhắc tách nhỏ theo CLAUDE.MD){RESET}")
        return False
    else:
        print(f"\n{GREEN}✅ Tuyệt vời: Mọi file trong core/ models/ forms/ services/ đều đạt chuẩn < {max_lines} dòng!{RESET}")
        return True


def check_security_and_secrets() -> bool:
    print_header("2. QUÉT BẢO MẬT & RÒ RỈ BÍ MẬT (precomit.md)")
    issues = []

    # Kiểm tra file .gitignore
    gitignore_path = os.path.join(BASE_DIR, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        if ".env" in content:
            print(f"  {GREEN}✓{RESET} .gitignore đã chặn file .env")
        else:
            issues.append(".gitignore chưa chặn file .env")
        if "*.db" in content:
            print(f"  {GREEN}✓{RESET} .gitignore đã chặn file cơ sở dữ liệu *.db")
        else:
            issues.append(".gitignore chưa chặn *.db")
    else:
        issues.append("Chưa có file .gitignore")

    if issues:
        print(f"\n{RED}❌ Phát hiện vấn đề bảo mật:{RESET}")
        for iss in issues:
            print(f"  {RED}• {iss}{RESET}")
        return False
    else:
        print(f"\n{GREEN}✅ An toàn: Cấu hình bảo vệ dữ liệu nhạy cảm đạt chuẩn!{RESET}")
        return True


def run_unit_tests() -> bool:
    print_header("3. CHẠY TEST-DRIVEN SUITE (CLAUDE.MD & tests.py)")
    test_file = os.path.join(BASE_DIR, "tests.py")
    if not os.path.exists(test_file):
        print(f"{RED}❌ Không tìm thấy file tests.py{RESET}")
        return False

    print(f"  Đang chạy: python tests.py ...")
    res = subprocess.run([sys.executable, test_file], cwd=BASE_DIR)
    if res.returncode == 0:
        print(f"\n{GREEN}✅ Toàn bộ Unit Tests đã PASS 100%!{RESET}")
        return True
    else:
        print(f"\n{RED}❌ Unit Tests thất bại (Exit code {res.returncode}){RESET}")
        return False


def main() -> None:
    print(f"{BLUE}🚀 BẮT ĐẦU KIỂM TRA QUY TẮC CLAUDE & AGENT RULES{RESET}")
    s1 = check_file_sizes(max_lines=200)
    s2 = check_security_and_secrets()
    s3 = run_unit_tests()

    print_header("TỔNG KẾT BÁO CÁO REVIEW (/review)")
    if s1 and s2 and s3:
        print(f"{GREEN}🎉 CHÚC MỪNG: Dự án của bạn vượt qua 100% quy chuẩn đề ra! Đủ điều kiện để commit.{RESET}\n")
    else:
        print(f"{YELLOW}⚠️  Có một số hạng mục cảnh báo/cần hoàn thiện trước khi commit lên git.{RESET}\n")


if __name__ == "__main__":
    main()

