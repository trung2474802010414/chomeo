# Skill: RESTful API Design & Integration Standards

Tập hợp các chuẩn mực thiết kế và tích hợp RESTful API cho ứng dụng Pet Shop, đảm bảo tính nhất quán, dễ mở rộng và tuân thủ các chuẩn công nghiệp.

---

## 1. Quy Chuẩn Đặt Tên Endpoint (URL Conventions)

- **Danh từ số nhiều:** Luôn sử dụng danh từ số nhiều ở dạng chữ thường (kebab-case) cho các tài nguyên.
  - ✅ `/api/products` (Danh sách sản phẩm)
  - ✅ `/api/products/12` (Chi tiết sản phẩm #12)
  - ✅ `/api/spa-bookings` (Lịch hẹn Spa)
  - ✅ `/api/orders` (Đơn hàng)
  - ❌ `/api/getProduct`, `/api/add-booking`, `/api/order/delete`

- **Quan hệ lồng nhau (Sub-resources):**
  - ✅ `/api/products/12/related` (Các sản phẩm liên quan đến sản phẩm #12)
  - ✅ `/api/orders/45/items` (Các mặt hàng trong đơn hàng #45)

---

## 2. Chuẩn HTTP Methods & Status Codes

| Method | Mục đích | Idempotent? | Status Thành Công | Status Thất Bại Thường Gặp |
|---|---|---|---|---|
| `GET` | Đọc dữ liệu | Có | `200 OK` | `404 Not Found` |
| `POST` | Tạo mới tài nguyên | Không | `201 Created` | `400 Bad Request`, `422 Unprocessable` |
| `PUT` | Cập nhật toàn bộ tài nguyên | Có | `200 OK` | `400 Bad Request`, `404 Not Found` |
| `PATCH` | Cập nhật một phần thuộc tính | Không | `200 OK` | `400 Bad Request`, `404 Not Found` |
| `DELETE`| Xóa tài nguyên | Có | `200 OK` hoặc `204 No Content` | `404 Not Found` |

---

## 3. Cấu Trúc Envelope JSON Nhất Quán (Uniform Response)

Mọi API trả về định dạng JSON đều phải tuân theo cấu trúc bao bọc (envelope) chuẩn sau:

### Phản Hồi Thành Công (Success Response)
```json
{
  "success": true,
  "code": 200,
  "message": "Lấy danh sách sản phẩm thành công",
  "data": [
    {
      "id": 1,
      "sku": "DOG-PET-001",
      "name": "Chó Schnauzer Tiêu Muối",
      "price": 6500000,
      "stock": 3
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total_items": 42,
    "total_pages": 5
  }
}
```

### Phản Hồi Khi Gặp Lỗi (Error Response)
```json
{
  "success": false,
  "code": 400,
  "error": {
    "type": "VALIDATION_ERROR",
    "message": "Dữ liệu gửi lên không đúng định dạng",
    "details": {
      "price": ["Giá bán không được âm."],
      "phone": ["Số điện thoại phải từ 9 đến 11 chữ số."]
    }
  }
}
```

---

## 4. Chuẩn Phân Trang, Lọc & Sắp Xếp (Query Parameters)

- **Phân trang:**
  - `page`: Số trang hiện tại (bắt đầu từ `1`, mặc định `1`).
  - `page_size` hoặc `limit`: Số phần tử trên mỗi trang (mặc định `10`, tối đa `100`).
- **Tìm kiếm:**
  - `q` hoặc `keyword`: Từ khóa tìm kiếm (tìm kiếm theo tên, mô tả, SKU).
- **Lọc đa điều kiện:**
  - `category`: Tên danh mục (`Thức ăn`, `Chó cảnh`, ...).
  - `pet_type`: Loài thú cưng (`Chó`, `Mèo`, `Chó & Mèo`).
  - `breed`: Giống chó mèo cụ thể.
  - `min_price` & `max_price`: Khoảng giá tìm kiếm.
- **Sắp xếp:**
  - `sort_by`: Định dạng trường và chiều sắp xếp (ví dụ: `price_asc`, `price_desc`, `id_desc`).

---

## 5. Xác Thực & Lập Trình Mạng (CLO3)

- **API Header Authentication:**
  - Sử dụng custom header `x-api-key: <KEY>` hoặc `Authorization: Bearer <TOKEN>`.
  - Luôn che giấu key nhạy cảm khi hiển thị trên UI hoặc log (ví dụ: `CAT-SEC***`).
- **Đa Định Dạng Dữ Liệu:**
  - Hỗ trợ xuất dữ liệu cả hai định dạng `application/json` và `application/xml` (qua `xml.etree.ElementTree`).
  - Hỗ trợ streaming file dung lượng lớn bằng `text/csv` kết hợp Python Generator để tiết kiệm bộ nhớ RAM.

