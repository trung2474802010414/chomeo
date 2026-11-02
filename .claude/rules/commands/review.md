# Command: Code Review (`/review`)

Quy chuẩn và checklist hướng dẫn AI Agent thực hiện rà soát mã nguồn (Code Review) trước khi tạo commit hoặc merge pull request.

---

## 1. Mục tiêu Code Review
- Đảm bảo mã nguồn đạt chuẩn kiến trúc, dễ đọc, dễ mở rộng và tuân thủ các quy tắc trong [`CLAUDE.MD`](file:///d:/TA_Web/file_TH/lab6/petshop/CLAUDE.MD) và [`AGENT.MD`](file:///d:/TA_Web/file_TH/lab6/petshop/AGENT.MD).
- Phát hiện sớm lỗi logic, lỗ hổng bảo mật và suy giảm hiệu năng trước khi đưa lên môi trường production (Vercel).

---

## 2. Checklist Đánh Giá Chi Tiết

### A. Kiến Trúc & Code Style (CLO4 & CLO5)
- [ ] **Kích thước file & hàm:** File có vượt quá 200 dòng không? Hàm có dài quá 50 dòng không? Nếu có, yêu cầu tách nhỏ module.
- [ ] **Type Safety:** Tuân thủ triệt để rule [`no-any.md`](file:///d:/TA_Web/file_TH/lab6/petshop/.claude/rules/no-any.md). Các hàm Python đều phải có đầy đủ Type Hints (`typing.Optional`, `typing.Dict`, `typing.List`, `Tuple`, ...).
- [ ] **Clean Code & Naming:** Tên hàm/biến rõ nghĩa theo chuẩn PEP 8 (snake_case cho Python) hoặc camelCase (cho TypeScript/JS). Tránh đặt tên chung chung như `data`, `item`, `temp`, `res`.

### B. Bảo Mật & Xác Thực (CLO2 & CLO3)
- [ ] **Bảo mật dữ liệu nhạy cảm:** Tuyệt đối không hardcode API Key, mật khẩu, JWT secret vào mã nguồn. Luôn lấy qua `os.environ.get()` hoặc file `.env`.
- [ ] **SQL Injection:** Không nối chuỗi trực tiếp vào câu truy vấn SQL (`f"SELECT ... {var}"`). Bắt buộc dùng tham số parameterized query (`?` hoặc `%s`).
- [ ] **CSRF & Form Validation:** Mọi route xử lý POST/PUT/DELETE từ Web Form đều phải kiểm tra `CSRF token` và dữ liệu đầu vào.
- [ ] **XSS Prevention:** Tránh render mã HTML thô từ người dùng mà không qua bộ lọc escape an toàn.

### C. Hiệu Năng & Quản Lý Tài Nguyên (Advanced Python)
- [ ] **Context Manager:** Các kết nối cơ sở dữ liệu (SQLite `DatabaseSession`), file IO, socket mạng đều phải được bọc trong khối `with ...` để tự động dọn dẹp và đóng kết nối.
- [ ] **Generator & Streaming:** Các tác vụ xuất/nhập danh mục lớn (CSV/XML/JSON/phân trang) phải dùng Generator (`yield`) để tiết kiệm RAM, tránh tải toàn bộ dữ liệu vào bộ nhớ cùng lúc.
- [ ] **Transaction Rollback:** Các thao tác trừ tồn kho hoặc tạo đơn hàng phải có cơ chế Transaction an toàn; nếu xảy ra lỗi phải `rollback()` ngay lập tức.

### D. Kiểm Thử (Test-Driven Development)
- [ ] **Test Coverage:** Tính năng mới hoặc bug fix đã có unit test tương ứng trong `tests.py` chưa?
- [ ] **Test Pass 100%:** Toàn bộ test suite phải chạy thành công trước khi hoàn thành task.

---

## 3. Định Dạng Báo Cáo Review Chuẩn

Khi chạy lệnh `/review`, Agent phải trình bày nhận xét theo 3 cấp độ rõ ràng:

1. **🔴 [Critical] - Lỗi bắt buộc phải sửa:**
   - Các lỗi bảo mật, crash ứng dụng, vi phạm transaction hoặc sai logic nghiệp vụ.
2. **🟡 [Warning] - Điểm nên tối ưu:**
   - File quá dài (> 200 dòng), thiếu type hints, code trùng lặp, thiếu try/except ở các tác vụ I/O.
3. **🟢 [Good] - Điểm sáng cần duy trì:**
   - Áp dụng tốt design pattern, code modular rõ ràng, xử lý exception chỉn chu.

