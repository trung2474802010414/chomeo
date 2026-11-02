# Rule: File Size & Component Limits

Quy chuẩn giới hạn kích thước file và độ dài hàm để duy trì tính module hóa, sạch và dễ bảo trì.

---

## 1. Quy định giới hạn
- **File kích thước tối đa:** Mỗi file mã nguồn (`.py`, `.ts`, `.tsx`, `.js`) không được vượt quá **200 dòng code**.
- **Hàm/Phương thức tối đa:** Mỗi hàm/method lý tưởng dưới **50 dòng code** và chỉ đảm nhận 1 nhiệm vụ duy nhất (Single Responsibility Principle).
- **Component UI:** Tách các khối giao diện lặp lại thành Macro Jinja2 (`templates/base.html`) hoặc component riêng biệt.

---

## 2. Hướng dẫn xử lý khi file vượt quá 200 dòng
- Nếu một file controller/service phình to:
  - Tách các hàm truy vấn DB sang `services/`.
  - Tách các hàm helper/tiện ích sang `core/` hoặc `utils/`.
  - Tách các schema/validation sang `forms/`.

