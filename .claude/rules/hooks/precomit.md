# Hook: Pre-Commit Quality & Security Gate

Quy định và các bước kiểm tra tự động bắt buộc trước khi thực hiện `git commit` trong dự án Meow & Woof Pet Shop.

---

## 1. Mục Đích & Nguyên Tắc
- Ngăn chặn triệt để việc commit mã lỗi, mã chưa được format, hoặc vô tình đẩy các thông tin nhạy cảm (API Keys, Secrets, Passwords) lên repository.
- Đảm bảo toàn bộ mã nguồn tuân thủ nghiêm ngặt các quy tắc trong [`CLAUDE.MD`](file:///d:/TA_Web/file_TH/lab6/petshop/CLAUDE.MD), [`AGENT.MD`](file:///d:/TA_Web/file_TH/lab6/petshop/AGENT.MD) và [`no-any.md`](file:///d:/TA_Web/file_TH/lab6/petshop/.claude/rules/no-any.md).

---

## 2. Các Bước Kiểm Tra Trước Khi Commit (5-Step Checklist)

### Bước 1: Quét Rò Rỉ Bí Mật (Secret & Environment Scan)
- [ ] Không commit file `.env`, file cơ sở dữ liệu tạm thời (`*.db`, `*.sqlite3`).
- [ ] Không chứa thông tin đăng nhập thực, SMTP passwords hoặc private keys trong code.
- [ ] File `.gitignore` phải bao gồm:
  ```gitignore
  .env
  *.db
  *.sqlite3
  __pycache__/
  .pytest_cache/
  node_modules/
  dist/
  .vercel/
  ```

### Bước 2: Kiểm Tra Định Dạng Code (Formatting & Linting)
- **Python:**
  - Đảm bảo tuân thủ chuẩn PEP 8.
  - Sử dụng `black` hoặc `ruff` để tự động định dạng mã:
    ```bash
    black --line-length 120 .
    ```
- **Frontend (HTML / CSS / JS):**
  - Đảm bảo không có thẻ đóng bị thiếu, CSS không chứa các rule trùng lặp gây xung đột màu hiển thị.

### Bước 3: Kiểm Tra Type Hints & Type Safety
- **Python Type Checking:**
  - Chạy `mypy` để rà soát Type Hints:
    ```bash
    mypy . --ignore-missing-imports
    ```
  - Tuyệt đối không để sót các hàm thiếu type hints của tham số hoặc kiểu trả về.

### Bước 4: Chạy Bộ Kiểm Thử Tự Động (Unit Test Suite)
- **Bắt buộc:** Toàn bộ test suite phải vượt qua 100% trước khi tạo commit:
  ```bash
  python petshop/tests.py
  # hoặc
  pytest
  ```
- Nếu có bất kỳ test case nào fail, **hủy bỏ quá trình commit** và sửa lỗi trước.

### Bước 5: Kiểm Tra Định Dạng Commit Message (Conventional Commits)
- Tiêu đề commit phải tuân thủ chuẩn Conventional Commits (có thể viết bằng tiếng Việt hoặc tiếng Anh rõ nghĩa):
  - `feat`: Tính năng mới (ví dụ: `feat(spa): làm lại giao diện đặt lịch spa 1-chạm`)
  - `fix`: Sửa lỗi (ví dụ: `fix(auth): khắc phục lỗi mất session khi đóng trình duyệt`)
  - `refactor`: Tái cấu trúc code mà không đổi logic (ví dụ: `refactor(orm): tối ưu generator query`)
  - `style`: Chỉnh sửa giao diện, CSS (ví dụ: `style(shop): tăng độ tương phản nút chi tiết`)
  - `test`: Bổ sung hoặc cập nhật unit tests (ví dụ: `test(clo2): thêm test case cho đăng ký khách hàng`)
  - `docs`: Cập nhật tài liệu, README, rules

---

## 3. Script Mẫu Hook Pre-Commit (`.git/hooks/pre-commit`)

Bạn có thể lưu nội dung sau vào file `.git/hooks/pre-commit` (và cấp quyền thực thi `chmod +x`):

```bash
#!/bin/sh
echo "🔍 [Pre-Commit Hook] Bắt đầu kiểm tra chất lượng mã nguồn..."

# 1. Kiểm tra file .env có bị stage nhầm không
if git diff --cached --name-only | grep -E '^\.env$'; then
    echo "❌ Lỗi: File .env không được phép commit lên git!"
    exit 1
fi

# 2. Chạy bộ kiểm thử tự động
echo "🧪 [Pre-Commit Hook] Chạy Unit Tests..."
python tests.py
if [ $? -ne 0 ]; then
    echo "❌ Lỗi: Unit tests thất bại! Vui lòng sửa lỗi trước khi commit."
    exit 1
fi

echo "✅ [Pre-Commit Hook] Mọi kiểm tra hợp lệ! Tiến hành commit..."
exit 0
```

