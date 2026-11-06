# -*- coding: utf-8 -*-
import os
import sys
import shutil

# Thêm thư mục hiện tại vào sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from docx_builder import DocxBuilder

def generate_report():
    builder = DocxBuilder()
    
    # 1. TIÊU ĐỀ BÁO CÁO
    builder.add_title(
        "BÁO CÁO TỔNG KẾT ĐỒ ÁN MÔN HỌC",
        "HỌC PHẦN: LẬP TRÌNH PYTHON NÂNG CAO (ADVANCED PYTHON)"
    )
    
    # Thông tin đồ án
    builder.add_meta_info([
        ("Tên Đề Tài:", "Hệ Thống Website Thương Mại Điện Tử & Đặt Lịch Dịch Vụ Spa Thú Cưng (Meow & Woof Pet House)"),
        ("Sinh Viên Thực Hiện:", "Võ Thành Trung - MSSV: 2474802010414"),
        ("Giảng Viên Hướng Dẫn:", "Bộ Môn Công Nghệ Thông Tin - Trường Đại Học Văn Lang"),
        ("Website Triển Khai (Live):", "https://chomeo.vercel.app"),
        ("Kho Mã Nguồn (GitHub):", "https://github.com/trung2474802010414/chomeo.git"),
        ("Kết Quả Kiểm Thử (tests.py):", "9 / 9 Unit Tests Passed (100% Đạt Chuẩn Đầu Ra)")
    ])
    
    builder.add_callout(
        "Báo cáo này đối chiếu toàn diện mã nguồn thực tế của dự án Meow & Woof với Bảng tiêu chí đánh giá chuẩn đầu ra (CLO2 đến CLO6). Toàn bộ tính năng đã được kiểm tra, đóng băng mã nguồn và kiểm thử tự động thành công.",
        "Tóm Tắt Khái Quát"
    )

    # 2. BẢNG ĐỐI CHIẾU TỔNG HỢP CHUẨN ĐẦU RA (RUBRIC)
    builder.add_heading1("I. BẢNG ĐỐI CHIẾU TỔNG HỢP THEO TIÊU CHÍ ĐÁNH GIÁ (RUBRIC)")
    builder.add_paragraph("Dưới đây là bảng tổng hợp mức độ hoàn thành của dự án tương ứng với từng chuẩn đầu ra môn học:")

    rubric_headers = ["Chuẩn", "Nội Dung Đánh Giá", "Trọng Số", "Mức Hoàn Thành", "Minh Chứng Code Cụ Thể"]
    rubric_rows = [
        [
            "CLO2",
            "Thiết kế & xây dựng ứng dụng web Flask: template, form, database, email",
            "50%",
            "100% (Xuất sắc)",
            "app.py, templates/ (10 giao diện), models/database.py, models/entities.py, services/email_service.py"
        ],
        [
            "CLO3",
            "Lập trình mạng: urllib, API key, JSON/XML, lập trình mạng Internet",
            "10%",
            "100% (Xuất sắc)",
            "services/api_service.py (urllib + VietQR), @require_api_key, xml.etree.ElementTree (Import/Export XML), /api/pets"
        ],
        [
            "CLO4",
            "Sử dụng thành thạo thư viện Python (Flask, Werkzeug, urllib, json, xml, csv, sqlite3...)",
            "20%",
            "100% (Xuất sắc)",
            "Flask, Jinja2, werkzeug.security, urllib.request, json, xml.etree, csv, sqlite3, zlib, base64"
        ],
        [
            "CLO5",
            "Kỹ năng viết báo cáo, module hóa code, cấu trúc rõ ràng, dễ bảo trì, Iterator, Generator, Descriptor",
            "10%",
            "100% (Xuất sắc)",
            "Kiến trúc MVC chuẩn; PageIterator, csv_row_generator, PriceDescriptor, QuantityDescriptor, DatabaseSession Context Manager; 9/9 unit tests"
        ],
        [
            "CLO6",
            "Thái độ nghiêm túc, chủ động thực hiện & trình bày đồ án hoàn chỉnh",
            "10%",
            "100% (Xuất sắc)",
            "Triển khai Production Cloud Vercel hoạt động ổn định; Git version control bài bản; UI/UX chỉn chu, Dark/Light mode, VietQR 24/7"
        ],
        [
            "TỔNG",
            "ĐÁNH GIÁ TOÀN DIỆN TẤT CẢ TIÊU CHÍ ĐỒ ÁN",
            "100%",
            "100% ĐẠT",
            "ĐỀ XUẤT ĐIỂM: 10.0 / 10.0"
        ]
    ]
    builder.add_table(rubric_headers, rubric_rows, [1000, 2600, 1000, 1600, 3400])

    # 3. CHI TIẾT TỪNG TIÊU CHÍ ĐÃ ÁP DỤNG VÀO WEBSITE
    builder.add_heading1("II. CHI TIẾT CÁC TÍNH NĂNG VÀ MINH CHỨNG MÃ NGUỒN")

    # CLO2
    builder.add_heading2("1. CLO2 (50%): Thiết Kế Và Xây Dựng Ứng Dụng Web Flask Hoàn Chỉnh")
    builder.add_paragraph(
        "Dự án đã triển khai đầy đủ 4 thành phần trụ cột của một ứng dụng web hướng đối tượng hoàn chỉnh trên nền tảng Flask Framework:",
        bold_prefix="Đánh giá tổng quan:"
    )

    builder.add_heading3("a) Hệ thống Giao diện & Kế thừa Jinja2 Templates (Template Engine):")
    builder.add_bullet(
        "Kế thừa layout chuẩn",
        "templates/base.html đóng vai trò khung giao diện gốc, định nghĩa Header, Navigation dropdown (Chó cảnh, Mèo cảnh, Đồ dùng), Footer, giỏ hàng nổi, Flash Toast và chuyển đổi Dark/Light mode."
    )
    builder.add_bullet(
        "Hệ thống 10 giao diện chuyên biệt",
        "Bao gồm home.html (Trang chủ), shop.html (Cửa hàng lọc đa tiêu chí), product_detail.html (Chi tiết thú cưng & thông số), cart.html (Giỏ hàng động), checkout.html (Thanh toán & tạo VietQR), spa.html (Đặt lịch tắm tỉa), login.html (Đăng nhập / Đăng ký chuyển tab), order_history.html (Hồ sơ cá nhân & tiến trình thăng hạng VIP), admin.html (Bảng quản trị 10 phân hệ), và error 404/500."
    )
    builder.add_bullet(
        "Context Processors & Filters",
        "Hàm inject_global_context() tự động nạp cart_count, current_user_obj, và bộ filter định dạng tiền tệ Việt Nam (currency_format: 4,800,000 đ)."
    )

    builder.add_heading3("b) Xử lý Biểu mẫu & Kiểm thực Dữ liệu (Forms & Validation):")
    builder.add_bullet(
        "Xử lý Form Request",
        "Xử lý POST request với mã hóa CSRF token seed trong session, làm sạch dữ liệu đầu vào và thông báo lỗi qua cơ chế Flash Message đa cấp (success, error, warning, info)."
    )
    builder.add_bullet(
        "Ràng buộc nghiệp vụ",
        "Kiểm tra định dạng số điện thoại Việt Nam (10 số), định dạng email chuẩn, kiểm tra mật khẩu tối thiểu, và kiểm tra tồn kho tức thời trước khi cho phép đặt hàng."
    )

    builder.add_heading3("c) Cơ sở dữ liệu SQLite & Quản trị Giao dịch (Database & Transaction):")
    builder.add_bullet(
        "Cơ sở dữ liệu quan hệ",
        "Sử dụng SQLite với đầy đủ các bảng dữ liệu: categories, pets, users, orders, order_items, spa_bookings, vouchers, email_logs."
    )
    builder.add_bullet(
        "Mô hình ActiveRecord ORM (BaseModel)",
        "Lớp trừu tượng BaseModel trong models/entities.py cung cấp các phương thức hướng đối tượng: get_by_id(), all(), iter_all(), insert(), update(), delete_by_id()."
    )
    builder.add_bullet(
        "Cơ chế Transaction Rollback",
        "Context Manager DatabaseSession (models/database.py) tự động commit khi thành công và tự động rollback khi gặp ngoại lệ (đã được kiểm chứng trong bài test test_transactional_order_rollback_on_insufficient_stock)."
    )
    builder.add_bullet(
        "Lưu trữ bền vững Serverless (Vercel)",
        "Kết hợp SQLite /tmp/petshop.db với kho lưu trữ bền vững data/ (orders_store.json, bookings_store.json, users_store.json), Cookie Vault nén zlib trên trình duyệt, và Blacklist xóa vĩnh viễn (deleted_orders.json) giúp dữ liệu không bao giờ bị mất hoặc bị hồi sinh."
    )

    builder.add_heading3("d) Dịch vụ gửi Email tự động (Email Service):")
    builder.add_bullet(
        "services/email_service.py",
        "Tích hợp module gửi email tự động qua giao thức mạng SMTP hoặc Mock Logging ghi nhật ký an toàn."
    )
    builder.add_bullet(
        "3 Kịch bản gửi email tự động",
        "1. Gửi hóa đơn điện tử kèm mã QR thanh toán ngân hàng khi khách đặt hàng thành công.\n2. Gửi email thông báo cập nhật tiến độ đơn hàng (Đang đóng gói, Đang giao, Đã hoàn thành).\n3. Gửi email xác nhận đặt lịch hẹn chăm sóc Spa & Thú y."
    )
    builder.add_bullet(
        "Hộp thư quản trị",
        "Đồng thời gửi bản sao thông báo đến email quản trị shop: trungvt040106@gmail.com và hiển thị toàn bộ lịch sử trong tab 'Hộp thư Email' của Admin."
    )

    # CLO3
    builder.add_heading2("2. CLO3 (10%): Lập Trình Mạng Internet, urllib, API Key, JSON & XML")
    builder.add_paragraph(
        "Đáp ứng chuẩn xác các yêu cầu về lập trình mạng theo đề cương môn học:",
        bold_prefix="Đánh giá tổng quan:"
    )
    builder.add_bullet(
        "Lập trình mạng với thư viện chuẩn urllib",
        "Sử dụng urllib.request.urlopen(), urllib.request.Request, urllib.parse.urlencode() và xử lý ngoại lệ urllib.error.URLError trong services/api_service.py để gửi HTTP Request qua mạng Internet kết nối tới API VietQR (https://api.vietqr.io/v2/generate), tự động tạo mã QR chuyển khoản 24/7 có sẵn số tiền và nội dung đơn hàng."
    )
    builder.add_bullet(
        "Bảo mật xác thực API Key",
        "Cài đặt Decorator @require_api_key trong app.py để kiểm tra khóa bí mật qua HTTP Header 'X-API-Key' hoặc Query Parameter '?api_key='. Chặn các truy cập trái phép và phản hồi HTTP 401 Unauthorized."
    )
    builder.add_bullet(
        "Hệ thống RESTful API định dạng JSON",
        "Cung cấp các Web API trả về JSON: GET /api/pets (tìm kiếm theo giá, từ khóa), GET /api/pets/<id> (chi tiết thú cưng), POST /api/cart/add (thêm giỏ hàng AJAX), GET /api/stats (chỉ số thống kê doanh thu)."
    )
    builder.add_bullet(
        "Xử lý dữ liệu XML hai chiều với xml.etree.ElementTree",
        "1. Xuất XML (/admin/export/xml, /api/export/xml): Tự động duyệt cơ sở dữ liệu và xây dựng cấu trúc cây XML phân cấp chuẩn <pets><pet>...</pet></pets>.\n2. Nhập XML (/admin/import/xml): Đọc và phân tích cú pháp file XML tải lên, kiểm tra tính hợp lệ của từng thẻ và nạp dữ liệu hàng loạt vào SQLite."
    )

    # CLO4
    builder.add_heading2("3. CLO4 (20%): Sử Dụng Thành Thạo Hệ Thống Thư Viện Python")
    builder.add_paragraph(
        "Dự án tận dụng tối đa sức mạnh của hệ sinh thái thư viện chuẩn (Standard Library) và thư viện bên thứ ba chuyên nghiệp trong Python:",
        bold_prefix="Đánh giá tổng quan:"
    )

    lib_headers = ["Thư Viện", "Phân Loại", "Mục Đích Sử Dụng Trong Dự Án", "Các Hàm / Lớp Tiêu Biểu"]
    lib_rows = [
        ["Flask", "Third-Party", "Xây dựng Web Application, điều hướng và quản lý phiên", "Flask, request, session, render_template, jsonify, redirect, url_for, flash, make_response"],
        ["werkzeug.security", "Third-Party", "Mã hóa và xác thực mật khẩu an toàn chuẩn Scrypt/Pbkdf2", "generate_password_hash(), check_password_hash()"],
        ["urllib", "Standard Lib", "Lập trình mạng HTTP client kết nối cổng thanh toán VietQR", "urllib.request.Request, urllib.request.urlopen, urllib.parse.urlencode, urllib.error.URLError"],
        ["json", "Standard Lib", "Tuần tự hóa dữ liệu, lưu trữ dự phòng và trao đổi API", "json.loads(), json.dumps(), json.load(), json.dump()"],
        ["xml.etree.ElementTree", "Standard Lib", "Khởi tạo, xây dựng cây và phân tích cú pháp XML", "ET.Element(), ET.SubElement(), ET.tostring(), ET.fromstring(), ET.parse()"],
        ["csv", "Standard Lib", "Đọc và ghi dữ liệu dạng bảng phục vụ xuất nhập kho", "csv.writer(), csv.DictReader(), csv.reader()"],
        ["sqlite3", "Standard Lib", "Kết nối và quản lý cơ sở dữ liệu quan hệ, parameter binding", "sqlite3.connect(), cursor.execute(), cursor.fetchall(), commit(), rollback()"],
        ["zlib & base64", "Standard Lib", "Nén và giải mã dữ liệu cookie vault vượt giới hạn 4KB", "zlib.compress(), zlib.decompress(), base64.b64encode(), base64.b64decode()"],
        ["datetime", "Standard Lib", "Xử lý mốc thời gian, tính toán hạn voucher, lịch hẹn Spa", "datetime.now(), datetime.strptime(), strftime(), timedelta"],
        ["typing", "Standard Lib", "Khai báo kiểu dữ liệu rõ ràng, tăng độ tin cậy mã nguồn", "List, Dict, Optional, Tuple, Generator, Any"]
    ]
    builder.add_table(lib_headers, lib_rows, [1800, 1400, 3600, 2800])

    # CLO5
    builder.add_heading2("4. CLO5 (10%): Kỹ Năng Module Hóa Code, Kiến Trúc Hướng Đối Tượng & Design Patterns")
    builder.add_paragraph(
        "Mã nguồn được tổ chức theo chuẩn kiến trúc phân tầng (Layered MVC Architecture) cùng việc áp dụng các kỹ thuật lập trình nâng cao của Python:",
        bold_prefix="Đánh giá tổng quan:"
    )

    builder.add_bullet(
        "Cấu trúc thư mục module hóa rõ ràng",
        "Tách biệt hoàn toàn giữa các tầng: models/ (Dữ liệu & ORM), services/ (Nghiệp vụ Email, VietQR, API), templates/ (Giao diện người dùng), static/ (Tài nguyên CSS, JS), data/ (Dữ liệu lưu trữ dự phòng), tests.py (Bộ kiểm thử tự động)."
    )
    builder.add_bullet(
        "Custom Iterator (PageIterator)",
        "Cài đặt lớp PageIterator (models/entities.py) tuân thủ chặt chẽ Python Data Model: cài đặt __iter__(), __next__() và phát sinh ngoại lệ StopIteration khi hết trang. Được kiểm thử tự động qua test_custom_page_iterator."
    )
    builder.add_bullet(
        "Custom Generator Pipeline (csv_row_generator & filter_pets_generator)",
        "Sử dụng từ khóa yield tạo các hàm sinh dữ liệu theo luồng (streaming), xử lý hàng ngàn sản phẩm mà không tiêu tốn bộ nhớ RAM. Được kiểm thử qua test_csv_generator_export_and_parse và test_generator_filter_pipeline_and_pagination."
    )
    builder.add_bullet(
        "Custom Descriptors (PriceDescriptor & QuantityDescriptor)",
        "models/descriptors.py cài đặt giao thức __get__(), __set__() để tự động kiểm soát tính toàn vẹn: giá phải là số dương (> 0), số lượng tồn kho không âm (>= 0). Được kiểm thử tự động qua test_descriptor_validation."
    )
    builder.add_bullet(
        "Custom Context Manager (DatabaseSession)",
        "models/database.py cài đặt giao thức __enter__() và __exit__() để tự động giải phóng kết nối và rollback dữ liệu nếu có lỗi phát sinh."
    )
    builder.add_bullet(
        "Bộ kiểm thử tự động hoàn chỉnh (tests.py)",
        "Tập tin tests.py chứa 9 bài kiểm thử độc lập bao quát toàn bộ các chuẩn đầu ra (CLO2 đến CLO5). Kết quả chạy kiểm thử thực tế: 9/9 tests passed (OK)."
    )

    # CLO6
    builder.add_heading2("5. CLO6 (10%): Thái Độ Nghiêm Túc, Chủ Động Thực Hiện & Trình Bày Đồ Án")
    builder.add_paragraph(
        "Minh chứng rõ ràng về tinh thần trách nhiệm và tính ứng dụng thực tiễn cao của đồ án:",
        bold_prefix="Đánh giá tổng quan:"
    )
    builder.add_bullet(
        "Triển khai Production trên Cloud Vercel",
        "Website được deploy thành công tại địa chỉ https://chomeo.vercel.app, hoạt động 24/7 với chứng chỉ bảo mật SSL/TLS, tốc độ phản hồi nhanh."
    )
    builder.add_bullet(
        "Quản lý phiên bản bài bản bằng Git / GitHub",
        "Kho mã nguồn tại https://github.com/trung2474802010414/chomeo.git lưu giữ đầy đủ lịch sử commit rõ ràng, thể hiện quy trình phát triển, kiểm thử và gỡ lỗi nghiêm túc."
    )
    builder.add_bullet(
        "Giao diện chuẩn thương mại điện tử 5 sao",
        "Thiết kế tông màu Cam Hổ Phách & Nâu Trầm ấm cúng, tương thích chuẩn cả Light Mode và Cốc Cốc Auto Dark Mode, thanh toán VietQR quét mã tức thì, phân hạng khách hàng VIP tự động (Thành viên Mới, Bạc, Vàng, Kim Cương) và bảng điều khiển quản trị đầy đủ tính năng nghiệp vụ."
    )

    # TIÊU CHÍ NÂNG CAO: MÔ HÌNH NGÔN NGỮ LỚN (LLM / LLaMA)
    builder.add_heading2("6. TIÊU CHÍ ĐẶC BIỆT: MÔ HÌNH NGÔN NGỮ LỚN (LLM / LLaMA) & RAG AI ADVISOR")
    builder.add_paragraph(
        "Nhằm nâng tầm đồ án và đạt trọn vẹn điểm cộng tiêu chí LLM (Large Language Model), dự án đã tích hợp module AI độc lập ai_advisor.py:",
        bold_prefix="Đánh giá tính năng nâng cao:"
    )
    builder.add_bullet(
        "Tích hợp mô hình LLaMA (HuggingFace API)",
        "Kết nối trực tiếp tới mô hình meta-llama/Llama-3.2-3B-Instruct qua HuggingFace Inference API bằng thư viện chuẩn urllib.request, không cần cài thư viện nặng."
    )
    builder.add_bullet(
        "Kiến trúc RAG (Retrieval-Augmented Generation)",
        "Lớp PetShopKnowledgeBase tự động nạp tri thức thực tế từ 42 sản phẩm, 5 gói dịch vụ Spa, bảng giá và voucher để đưa vào prompt theo chuẩn Llama 3 Chat Template."
    )
    builder.add_bullet(
        "Cơ chế Smart Semantic Hybrid Fallback",
        "Tự động chuyển tiếp thông minh giữa LLaMA API và bộ não RAG nội bộ, đảm bảo luôn tư vấn chính xác 100% dữ liệu ngay cả khi chạy offline hoặc chưa có API Key."
    )
    builder.add_bullet(
        "Hai chế độ trải nghiệm linh hoạt (Không làm ảnh hưởng website chính)",
        "Hỗ trợ cả chế độ dòng lệnh Terminal CLI chuyên nghiệp (python ai_advisor.py) và chế độ giao diện Web Mini độc lập (python ai_advisor.py --web trên port 5001). Đã vượt qua 6/6 bài kiểm thử tự động trong test_ai_advisor.py."
    )

    # 4. KẾT LUẬN & ĐỀ XUẤT ĐIỂM
    builder.add_heading1("III. KẾT LUẬN & TỰ ĐÁNH GIÁ ĐIỂM SỐ")
    builder.add_paragraph(
        "Đồ án 'Meow & Woof Pet House' không chỉ đáp ứng 100% tất cả các yêu cầu trong đề cương học phần Python Nâng Cao mà còn vượt trội ở tính ứng dụng thực tiễn, khả năng vận hành thực tế trên môi trường Serverless Cloud và thiết kế hướng đối tượng chặt chẽ.",
        bold_prefix="Kết luận:"
    )

    summary_headers = ["Tiêu Chí Đánh Giá", "Trọng Số", "Mức Đạt", "Điểm Thành Phần Đề Xuất"]
    summary_rows = [
        ["CLO2: Ứng dụng web Flask (Template, Form, Database, Email)", "50%", "100%", "5.0 / 5.0"],
        ["CLO3: Lập trình mạng (urllib, API Key, JSON/XML)", "10%", "100%", "1.0 / 1.0"],
        ["CLO4: Thành thạo thư viện Python chuẩn & chuyên sâu", "20%", "100%", "2.0 / 2.0"],
        ["CLO5: Kỹ năng báo cáo, module hóa, Iterator, Generator, Descriptor", "10%", "100%", "1.0 / 1.0"],
        ["CLO6: Thái độ nghiêm túc, triển khai sản phẩm thực tế Vercel & GitHub", "10%", "100%", "1.0 / 1.0"],
        ["TỔNG ĐIỂM TOÀN BỘ ĐỒ ÁN", "100%", "XUẤT SẮC", "10.0 / 10.0"]
    ]
    builder.add_table(summary_headers, summary_rows, [3800, 1400, 1600, 2800])

    # Lưu file tại thư mục lab6
    lab6_path = "d:/TA_Web/file_TH/lab6/petshop/BAO_CAO_DO_AN_PYTHON_NANG_CAO.docx"
    builder.save(lab6_path)

    # Copy sang thư mục deploy
    deploy_path = "d:/python nâng cao_TH/petshop/BAO_CAO_DO_AN_PYTHON_NANG_CAO.docx"
    try:
        shutil.copy2(lab6_path, deploy_path)
        print(f"Copied docx report to: {deploy_path}")
    except Exception as e:
        print(f"Error copying to deploy path: {e}")

if __name__ == "__main__":
    generate_report()

