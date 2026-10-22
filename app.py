import sqlite3
import time
import csv
import io
import hashlib
import math
from functools import wraps
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Iterator
from flask import Flask, render_template, request, jsonify, session, Response

app = Flask(__name__)
app.secret_key = "pethouse_secret_key_advanced_python"
DB_NAME = "pets.db"

# ==========================================
# KỸ THUẬT 1: MÃ HÓA MẬT KHẨU (SHA-256 HASHING)
# ==========================================
def hash_password(password: str) -> str:
    salt = "PetShop_Salt_2026"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

# ==========================================
# KỸ THUẬT 2: CUSTOM DECORATORS (LOG & PHÂN QUYỀN)
# ==========================================
def log_execution(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        print(f"[LOG] Đang thực thi: {func.__name__} | Method: {request.method} | Path: {request.path}")
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"[LOG] Hoàn thành {func.__name__} trong {(end_time - start_time)*1000:.2f} ms")
        return result
    return wrapper

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get("user")
        if not user or user.get("role") != "admin":
            return jsonify({
                "status": "error",
                "message": "Truy cập bị từ chối! Chỉ Admin mới có quyền thực hiện thao tác này."
            }), 403
        return func(*args, **kwargs)
    return wrapper

# ==========================================
# KỸ THUẬT 3: CONTEXT MANAGER (QUẢN LÝ DATABASE)
# ==========================================
class DatabaseConnection:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Cursor:
        self.conn = sqlite3.connect(self.db_name)
        self.conn.row_factory = sqlite3.Row
        return self.conn.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

# ==========================================
# KỸ THUẬT 4: OOP & DATACLASS
# ==========================================
@dataclass
class Pet:
    id: Optional[int]
    name: str
    species: str
    breed: str
    age: int
    price: int
    image: str
    status: str = "Còn hàng"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ==========================================
# KHỞI TẠO DATABASE VÀ DỮ LIỆU MẪU
# ==========================================
def init_db() -> None:
    with DatabaseConnection(DB_NAME) as cursor:
        # 1. Bảng Người dùng (Users)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'customer'
            )
        ''')
        # 2. Bảng Thú cưng (Pets)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                species TEXT NOT NULL,
                breed TEXT NOT NULL,
                age INTEGER NOT NULL,
                price INTEGER NOT NULL,
                image TEXT NOT NULL,
                status TEXT DEFAULT 'Còn hàng'
            )
        ''')
        # 3. Bảng Đơn hàng (Orders)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                total_price INTEGER NOT NULL,
                items TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Thêm tài khoản Admin và Khách hàng mẫu
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()["count"] == 0:
            sample_users = [
                ("admin", hash_password("123456"), "Quản Trị Viên", "admin"),
                ("khachhang", hash_password("123456"), "Nguyễn Văn Khách", "customer")
            ]
            cursor.executemany('''
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', sample_users)

        # Thêm 9 thú cưng mẫu để kiểm thử Phân trang (4 thú cưng/trang -> 3 trang)
        cursor.execute("SELECT COUNT(*) as count FROM pets")
        if cursor.fetchone()["count"] == 0:
            sample_pets = [
                # --- 10 BÉ CHÓ ---
                ("Bé Corgi Mông To", "Chó", "Pembroke Welsh Corgi", 3, 12000000, "https://images.unsplash.com/photo-1612536057832-2ff7ead58194?w=500"),
                ("Cún Poodle Tiny Nâu Đỏ", "Chó", "Toy Poodle", 2, 5500000, "https://images.unsplash.com/photo-1616149562385-1d84e79478bb?w=500"),
                ("Husky Ngáo Tuyết Trắng", "Chó", "Siberian Husky", 5, 9000000, "https://images.unsplash.com/photo-1605568427561-40dd23c2acea?w=500"),
                ("Golden Retriever Vàng Óng", "Chó", "Golden Retriever", 4, 11000000, "https://images.unsplash.com/photo-1552053831-71594a27632d?w=500"),
                ("Chó Shiba Inu Cười Tươi", "Chó", "Shiba Inu", 3, 14000000, "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=500"),
                ("Cục Bông Phốc Sóc Trắng", "Chó", "Pomeranian", 2, 9500000, "https://images.unsplash.com/photo-1591769225440-811ad7d6eab3?w=500"),
                ("Bé Pug Mặt Xệ Đáng Yêu", "Chó", "Pug", 4, 4800000, "https://images.unsplash.com/photo-1517849845537-4d257902454a?w=500"),
                ("Samoyed Tuyết Trắng Mỉm Cười", "Chó", "Samoyed", 5, 13500000, "https://images.unsplash.com/photo-1529472119196-cb724127a98e?w=500"),
                ("Bull Pháp Tai Dơi Bụ Bẫm", "Chó", "French Bulldog", 3, 10500000, "https://images.unsplash.com/photo-1583337130417-3346a1be7dee?w=500"),
                ("Chó Lạp Xưởng Chân Ngắn", "Chó", "Dachshund", 3, 4200000, "https://images.unsplash.com/photo-1612195583950-b8fd34c87093?w=500"),

                # --- 10 BÉ MÈO ---
                ("Mèo Anh Lông Ngắn Xám Xanh", "Mèo", "British Shorthair", 4, 8500000, "https://images.unsplash.com/photo-1573865526739-10659fec78a5?w=500"),
                ("Mèo Munchkin Chân Ngắn", "Mèo", "Munchkin", 3, 15000000, "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=500"),
                ("Mèo Ba Tư Mặt Tịt Trắng", "Mèo", "Persian", 4, 7000000, "https://images.unsplash.com/photo-1583795128727-6ec3642408f8?w=500"),
                ("Mèo Ragdoll Mắt Xanh Ngọc", "Mèo", "Ragdoll", 5, 16500000, "https://images.unsplash.com/photo-1533738363-b7f9aef128ce?w=500"),
                ("Mèo Tai Cụp Scottish Fold", "Mèo", "Scottish Fold", 3, 9800000, "https://images.unsplash.com/photo-1592194996308-7b43878e84a6?w=500"),
                ("Mèo Anh Lông Dài Màu Kem", "Mèo", "British Longhair", 4, 8900000, "https://images.unsplash.com/photo-1543852786-1cf6624b9987?w=500"),
                ("Mèo Bengal Vân Báo Hoang Dã", "Mèo", "Bengal", 6, 18000000, "https://images.unsplash.com/photo-1513245543132-31f507417b26?w=500"),
                ("Mèo Xiêm Hoàng Gia Mắt Xanh", "Mèo", "Siamese", 3, 4500000, "https://images.unsplash.com/photo-1518791841217-8f162f1e1131?w=500"),
                ("Mèo Maine Coon Khổng Lồ", "Mèo", "Maine Coon", 6, 22000000, "https://images.unsplash.com/photo-1561948955-570b270e7c36?w=500"),
                ("Mèo Golden Béo Ú Má Phính", "Mèo", "British Shorthair Golden", 4, 17500000, "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=500")
            ]
            cursor.executemany('''
                INSERT INTO pets (name, species, breed, age, price, image)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', sample_pets)

@app.route("/")
def index():
    return render_template("index.html")

# ==========================================
# CÁC API ĐĂNG NHẬP / ĐĂNG KÝ (AUTH)
# ==========================================
@app.route("/api/auth/register", methods=["POST"])
@log_execution
def register():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    full_name = data.get("full_name", "").strip()

    if not all([username, password, full_name]):
        return jsonify({"status": "error", "message": "Vui lòng điền đầy đủ thông tin!"}), 400

    pwd_hash = hash_password(password)
    try:
        with DatabaseConnection(DB_NAME) as cursor:
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, 'customer')
            ''', (username, pwd_hash, full_name))
        return jsonify({"status": "success", "message": "Đăng ký thành công! Bạn có thể đăng nhập ngay."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Tên đăng nhập này đã tồn tại!"}), 400

@app.route("/api/auth/login", methods=["POST"])
@log_execution
def login():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    pwd_hash = hash_password(password)

    with DatabaseConnection(DB_NAME) as cursor:
        cursor.execute('''
            SELECT id, username, full_name, role FROM users
            WHERE username = ? AND password_hash = ?
        ''', (username, pwd_hash))
        user = cursor.fetchone()

    if user:
        session["user"] = dict(user)
        return jsonify({
            "status": "success",
            "message": f"Chào mừng {user['full_name']} quay trở lại!",
            "user": dict(user)
        })
    return jsonify({"status": "error", "message": "Sai tên đăng nhập hoặc mật khẩu!"}), 401

@app.route("/api/auth/logout", methods=["POST"])
@log_execution
def logout():
    session.pop("user", None)
    return jsonify({"status": "success", "message": "Đã đăng xuất thành công!"})

@app.route("/api/auth/me", methods=["GET"])
def get_current_user():
    return jsonify({"user": session.get("user")})

# ==========================================
# CÁC API THÚ CƯNG (CÓ PHÂN TRANG & SẮP XẾP)
# ==========================================
@app.route("/api/pets", methods=["GET"])
@log_execution
def get_pets():
    species_filter: str = request.args.get("species", "All")
    search_query: str = request.args.get("search", "").strip()
    sort_by: str = request.args.get("sort", "newest")
    page: int = int(request.args.get("page", 1))
    per_page: int = int(request.args.get("per_page", 4)) # Hiển thị 4 thú cưng mỗi trang

    where_clause = " WHERE 1=1"
    params: List[Any] = []

    if species_filter != "All":
        where_clause += " AND species = ?"
        params.append(species_filter)
    
    if search_query:
        where_clause += " AND (name LIKE ? OR breed LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    order_clause = " ORDER BY id DESC"
    if sort_by == "price_asc":
        order_clause = " ORDER BY price ASC"
    elif sort_by == "price_desc":
        order_clause = " ORDER BY price DESC"

    with DatabaseConnection(DB_NAME) as cursor:
        # Đếm tổng số lượng thú cưng khớp điều kiện để chia trang
        cursor.execute(f"SELECT COUNT(*) as total FROM pets {where_clause}", params)
        total_items = cursor.fetchone()["total"]
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

        # Lấy dữ liệu theo trang bằng LIMIT và OFFSET
        offset = (page - 1) * per_page
        query = f"SELECT * FROM pets {where_clause} {order_clause} LIMIT ? OFFSET ?"
        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()
        pets = [Pet(**dict(row)).to_dict() for row in rows]

    return jsonify({
        "status": "success",
        "data": pets,
        "pagination": {
            "current_page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        }
    })

@app.route("/api/pets", methods=["POST"])
@log_execution
@admin_required
def add_pet():
    data = request.json
    try:
        new_pet = Pet(
            id=None,
            name=data["name"],
            species=data["species"],
            breed=data["breed"],
            age=int(data["age"]),
            price=int(data["price"]),
            image=data["image"]
        )
        with DatabaseConnection(DB_NAME) as cursor:
            cursor.execute('''
                INSERT INTO pets (name, species, breed, age, price, image)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (new_pet.name, new_pet.species, new_pet.breed, new_pet.age, new_pet.price, new_pet.image))
        
        return jsonify({"status": "success", "message": "Thêm thú cưng thành công!"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/pets/<int:pet_id>", methods=["DELETE"])
@log_execution
@admin_required
def delete_pet(pet_id: int):
    with DatabaseConnection(DB_NAME) as cursor:
        cursor.execute("DELETE FROM pets WHERE id = ?", (pet_id,))
    return jsonify({"status": "success", "message": f"Đã xóa thú cưng ID #{pet_id}"})

# ==========================================
# CÁC API ĐƠN HÀNG & XUẤT EXCEL/CSV (GENERATOR)
# ==========================================
@app.route("/api/orders", methods=["POST"])
@log_execution
def create_order():
    data = request.json
    customer_name = data.get("customer_name")
    phone = data.get("phone")
    address = data.get("address")
    total_price = data.get("total_price")
    items = data.get("items")

    if not all([customer_name, phone, address, items]):
        return jsonify({"status": "error", "message": "Vui lòng điền đầy đủ thông tin nhận hàng!"}), 400

    with DatabaseConnection(DB_NAME) as cursor:
        cursor.execute('''
            INSERT INTO orders (customer_name, phone, address, total_price, items)
            VALUES (?, ?, ?, ?, ?)
        ''', (customer_name, phone, address, total_price, items))

    return jsonify({"status": "success", "message": "Đặt hàng thành công! Đơn hàng đã được lưu vào hệ thống."}), 201

@app.route("/api/orders", methods=["GET"])
@log_execution
def get_orders():
    with DatabaseConnection(DB_NAME) as cursor:
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")
        orders = [dict(row) for row in cursor.fetchall()]

    total_revenue = sum(o["total_price"] for o in orders)
    return jsonify({
        "status": "success",
        "orders": orders,
        "total_orders": len(orders),
        "total_revenue": total_revenue
    })

# KỸ THUẬT 5: GENERATOR FUNCTION (YIELD) STREAM DỮ LIỆU CSV
@app.route("/api/orders/export", methods=["GET"])
@log_execution
def export_orders_csv():
    with DatabaseConnection(DB_NAME) as cursor:
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")
        orders = [dict(row) for row in cursor.fetchall()]

    def generate_csv() -> Iterator[str]:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Ký tự BOM giúp Microsoft Excel nhận diện đúng chuẩn UTF-8 Tiếng Việt
        yield '\ufeff'
        
        writer.writerow(["Mã Đơn", "Khách Hàng", "Số Điện Thoại", "Địa Chỉ Giao", "Thú Cưng Đã Mua", "Tổng Tiền (VNĐ)", "Ngày Đặt"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for o in orders:
            writer.writerow([f"#{o['id']}", o["customer_name"], f"'{o['phone']}", o["address"], o["items"], o["total_price"], o["created_at"]])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return Response(
        generate_csv(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=Bao_Cao_Don_Hang_PetHouse.csv"}
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)