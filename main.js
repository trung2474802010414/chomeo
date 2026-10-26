/**
 * static/js/main.js
 * Vanilla JavaScript điều khiển giao diện và giao tiếp với REST API thuần Python.
 */

const state = {
    currentPage: 1,
    pageSize: 6,
    products: [],
    cart: [],
};

// Định dạng tiền tệ VNĐ
function formatVND(amount) {
    return Number(amount || 0).toLocaleString("vi-VN") + " đ";
}

// Hiển thị thông báo
function showAlert(message, isError = false) {
    const box = document.getElementById("alertBox");
    box.textContent = message;
    box.className = "alert " + (isError ? "alert-error" : "alert-success");
    box.classList.remove("hidden");
    setTimeout(() => {
        box.classList.add("hidden");
    }, 4500);
}

// Cập nhật thông tin thực thi từ Decorator @api_handler ở Backend
function updateApiMeta(meta) {
    if (!meta) return;
    document.getElementById("metaHandler").textContent = meta.handler || "-";
    document.getElementById("metaTime").textContent = (meta.execution_ms ?? 0) + " ms";
}

// Hàm gọi API chung
async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const json = await response.json();
    if (json._meta) {
        updateApiMeta(json._meta);
    }
    if (!response.ok || json.ok === false) {
        throw new Error(json.error || "Có lỗi xảy ra khi gọi API");
    }
    return json.data !== undefined ? json.data : json;
}

// ============================================================================
// 1. QUẢN LÝ SẢN PHẨM, LỌC & PHÂN TRANG
// ============================================================================

async function loadProducts(page = 1) {
    state.currentPage = page;
    const params = new URLSearchParams({
        keyword: document.getElementById("filterKeyword").value.trim(),
        category: document.getElementById("filterCategory").value,
        pet_type: document.getElementById("filterPetType").value,
        min_price: document.getElementById("filterMinPrice").value,
        max_price: document.getElementById("filterMaxPrice").value,
        sort_by: document.getElementById("filterSort").value,
        in_stock_only: document.getElementById("filterInStock").checked ? "1" : "0",
        page: String(page),
        page_size: String(state.pageSize),
    });

    try {
        const result = await apiRequest(`/api/products?${params.toString()}`);
        state.products = result.items || [];
        renderProductTable(state.products);

        document.getElementById("totalProductCount").textContent = result.total_items;
        document.getElementById("paginationInfo").textContent = `Trang ${result.page} / ${result.total_pages}`;
        document.getElementById("pageIndicator").textContent = `Trang ${result.page} / ${result.total_pages}`;
        document.getElementById("btnPrevPage").disabled = !result.has_prev;
        document.getElementById("btnNextPage").disabled = !result.has_next;
    } catch (err) {
        showAlert(err.message, true);
    }
}

function renderProductTable(items) {
    const tbody = document.getElementById("productTableBody");
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center">Không tìm thấy sản phẩm phù hợp.</td></tr>`;
        return;
    }

    tbody.innerHTML = items
        .map((p) => {
            let badgeClass = "badge-ok";
            if (p.stock === 0) badgeClass = "badge-out";
            else if (p.stock <= 5) badgeClass = "badge-warn";

            return `
            <tr>
                <td><strong>${escapeHtml(p.sku)}</strong></td>
                <td>
                    <div><strong>${escapeHtml(p.name)}</strong></div>
                    <div class="muted-text" style="margin:0">${escapeHtml(p.description || "")}</div>
                </td>
                <td>${escapeHtml(p.category)}</td>
                <td>${escapeHtml(p.pet_type)}</td>
                <td class="text-right"><strong>${formatVND(p.price)}</strong></td>
                <td class="text-center">
                    <span class="badge ${badgeClass}">${p.stock} (${escapeHtml(p.stock_status)})</span>
                </td>
                <td class="text-center">
                    <button type="button" class="btn btn-sm btn-primary" onclick="addToCart(${p.id})" ${p.stock <= 0 ? "disabled" : ""}>+ Giỏ</button>
                    <button type="button" class="btn btn-sm" onclick="openEditProduct(${p.id})">Sửa</button>
                    <button type="button" class="btn btn-sm btn-danger" onclick="deleteProduct(${p.id})">Xóa</button>
                </td>
            </tr>
        `;
        })
        .join("");
}

function openEditProduct(id) {
    const p = state.products.find((item) => item.id === id);
    if (!p) return;

    document.getElementById("productFormTitle").textContent = `Cập nhật sản phẩm #${p.id}`;
    document.getElementById("prodId").value = p.id;
    document.getElementById("prodSku").value = p.sku;
    document.getElementById("prodName").value = p.name;
    document.getElementById("prodCategory").value = p.category;
    document.getElementById("prodPetType").value = p.pet_type;
    document.getElementById("prodPrice").value = p.price;
    document.getElementById("prodStock").value = p.stock;
    document.getElementById("prodDesc").value = p.description || "";

    document.getElementById("productForm").classList.remove("hidden");
}

function resetProductForm() {
    document.getElementById("productFormTitle").textContent = "Thêm sản phẩm mới";
    document.getElementById("prodId").value = "";
    document.getElementById("productForm").reset();
}

async function deleteProduct(id) {
    if (!confirm(`Bạn có chắc muốn xóa sản phẩm #${id}?`)) return;
    try {
        await apiRequest(`/api/products/${id}`, { method: "DELETE" });
        showAlert(`Đã xóa sản phẩm #${id}.`);
        loadProducts(state.currentPage);
        loadDashboardStats();
    } catch (err) {
        showAlert(err.message, true);
    }
}

// ============================================================================
// 2. GIỎ HÀNG & TẠO ĐƠN HÀNG (TRANSACTION)
// ============================================================================

function addToCart(productId) {
    const product = state.products.find((p) => p.id === productId);
    if (!product) return;

    const existing = state.cart.find((item) => item.product_id === productId);
    if (existing) {
        if (existing.quantity + 1 > product.stock) {
            showAlert(`Sản phẩm "${product.name}" chỉ còn ${product.stock} món trong kho.`, true);
            return;
        }
        existing.quantity += 1;
    } else {
        state.cart.push({
            product_id: product.id,
            name: product.name,
            price: product.price,
            max_stock: product.stock,
            quantity: 1,
        });
    }
    renderCart();
}

function changeCartQty(productId, delta) {
    const idx = state.cart.findIndex((i) => i.product_id === productId);
    if (idx === -1) return;
    const item = state.cart[idx];
    const nextQty = item.quantity + delta;
    if (nextQty <= 0) {
        state.cart.splice(idx, 1);
    } else if (nextQty > item.max_stock) {
        showAlert(`Tồn kho tối đa của "${item.name}" là ${item.max_stock}.`, true);
        return;
    } else {
        item.quantity = nextQty;
    }
    renderCart();
}

function renderCart() {
    const container = document.getElementById("cartContainer");
    const totalEl = document.getElementById("cartTotalAmount");

    if (!state.cart.length) {
        container.innerHTML = `<p class="muted-text">Chưa có sản phẩm nào trong giỏ.</p>`;
        totalEl.textContent = "0 đ";
        return;
    }

    let total = 0;
    container.innerHTML = state.cart
        .map((item) => {
            const sub = item.price * item.quantity;
            total += sub;
            return `
            <div class="cart-item">
                <div class="cart-item-info">
                    <div><strong>${escapeHtml(item.name)}</strong></div>
                    <div class="muted-text" style="margin:0">${formatVND(item.price)} x ${item.quantity} = ${formatVND(sub)}</div>
                </div>
                <div class="cart-item-controls">
                    <button type="button" class="btn btn-sm" onclick="changeCartQty(${item.product_id}, -1)">-</button>
                    <span>${item.quantity}</span>
                    <button type="button" class="btn btn-sm" onclick="changeCartQty(${item.product_id}, 1)">+</button>
                </div>
            </div>
        `;
        })
        .join("");

    totalEl.textContent = formatVND(total);
}

// ============================================================================
// 3. LỊCH HẸN SPA CHÓ MÈO
// ============================================================================

async function loadBookings() {
    const statusFilter = document.getElementById("bookingStatusFilter").value;
    try {
        const result = await apiRequest(`/api/bookings?status=${encodeURIComponent(statusFilter)}&page=1&page_size=20`);
        const tbody = document.getElementById("bookingTableBody");
        const items = result.items || [];

        if (!items.length) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center">Chưa có lịch hẹn nào.</td></tr>`;
            return;
        }

        const statuses = ["Chờ xác nhận", "Đã xác nhận", "Hoàn thành", "Đã hủy"];
        tbody.innerHTML = items
            .map((b) => {
                const optionsHtml = statuses
                    .map((st) => `<option value="${st}" ${b.status === st ? "selected" : ""}>${st}</option>`)
                    .join("");

                return `
                <tr>
                    <td>#${b.id}</td>
                    <td>
                        <strong>${escapeHtml(b.customer_name)}</strong><br>
                        <span class="muted-text">${escapeHtml(b.phone)}</span>
                    </td>
                    <td>
                        <strong>${escapeHtml(b.pet_name)}</strong> (${escapeHtml(b.pet_type)} - ${b.pet_weight_kg}kg)
                        ${b.note ? `<div class="muted-text" style="margin:0">Ghi chú: ${escapeHtml(b.note)}</div>` : ""}
                    </td>
                    <td>${escapeHtml(b.service_name)}</td>
                    <td>${escapeHtml(b.appointment_date)} lúc ${escapeHtml(b.appointment_time)}</td>
                    <td class="text-right"><strong>${formatVND(b.total_price)}</strong></td>
                    <td>
                        <select onchange="updateBookingStatus(${b.id}, this.value)">
                            ${optionsHtml}
                        </select>
                    </td>
                </tr>
            `;
            })
            .join("");
    } catch (err) {
        showAlert(err.message, true);
    }
}

async function updateBookingStatus(bookingId, newStatus) {
    try {
        await apiRequest(`/api/bookings/${bookingId}/status`, {
            method: "PUT",
            body: JSON.stringify({ status: newStatus }),
        });
        showAlert(`Đã cập nhật trạng thái lịch hẹn #${bookingId} sang "${newStatus}".`);
        loadDashboardStats();
    } catch (err) {
        showAlert(err.message, true);
        loadBookings();
    }
}

// ============================================================================
// 4. DANH SÁCH ĐƠN HÀNG & BÁO CÁO THỐNG KÊ
// ============================================================================

async function loadOrders() {
    try {
        const result = await apiRequest("/api/orders?page=1&page_size=25");
        const tbody = document.getElementById("orderTableBody");
        const items = result.items || [];

        if (!items.length) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center">Chưa có đơn hàng nào.</td></tr>`;
            return;
        }

        tbody.innerHTML = items
            .map((o) => {
                const detailLines = (o.items || [])
                    .map((line) => `${escapeHtml(line.name)} (SL: ${line.quantity} x ${formatVND(line.price)})`)
                    .join("<br>");

                return `
                <tr>
                    <td><strong>#${o.id}</strong></td>
                    <td>${escapeHtml(o.created_at)}</td>
                    <td><strong>${escapeHtml(o.customer_name)}</strong></td>
                    <td>${escapeHtml(o.phone)}</td>
                    <td>${escapeHtml(o.address)}</td>
                    <td>${detailLines}</td>
                    <td class="text-right"><strong>${formatVND(o.total_amount)}</strong></td>
                </tr>
            `;
            })
            .join("");
    } catch (err) {
        showAlert(err.message, true);
    }
}

async function loadDashboardStats() {
    try {
        const stats = await apiRequest("/api/stats");
        document.getElementById("statTotalProducts").textContent = stats.total_products;
        document.getElementById("statTotalUnits").textContent = stats.total_stock_units;
        document.getElementById("statInventoryVal").textContent = formatVND(stats.total_inventory_value);
        document.getElementById("statOrderRev").textContent = formatVND(stats.order_revenue);
        document.getElementById("statSpaRev").textContent = formatVND(stats.spa_revenue);
        document.getElementById("statUniqueCust").textContent = stats.unique_customers_count;

        // Bảng phân tích theo danh mục
        const catBody = document.getElementById("categoryStatsBody");
        const breakdown = stats.category_breakdown || {};
        const catEntries = Object.entries(breakdown);
        catBody.innerHTML = catEntries.length
            ? catEntries
                  .map(
                      ([cat, info]) => `
                <tr>
                    <td><strong>${escapeHtml(cat)}</strong></td>
                    <td class="text-center">${info.product_count}</td>
                    <td class="text-center">${info.stock_units}</td>
                    <td class="text-right">${formatVND(info.inventory_value)}</td>
                </tr>
            `
                  )
                  .join("")
            : `<tr><td colspan="4" class="text-center">Chưa có dữ liệu</td></tr>`;

        // Bảng sắp hết hàng
        const lowBody = document.getElementById("lowStockBody");
        const lowItems = stats.low_stock_products || [];
        lowBody.innerHTML = lowItems.length
            ? lowItems
                  .map(
                      (p) => `
                <tr>
                    <td>#${p.id}</td>
                    <td><strong>${escapeHtml(p.sku)}</strong></td>
                    <td>${escapeHtml(p.name)}</td>
                    <td class="text-center"><span class="badge ${p.stock === 0 ? "badge-out" : "badge-warn"}">${p.stock}</span></td>
                </tr>
            `
                  )
                  .join("")
            : `<tr><td colspan="4" class="text-center">Tất cả sản phẩm đều còn tồn kho dồi dào (&gt; 5).</td></tr>`;
    } catch (err) {
        showAlert(err.message, true);
    }
}

function escapeHtml(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ============================================================================
// KHỞI TẠO SỰ KIỆN KHI TRANG TẢI XONG
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // Ngày mặc định cho form đặt lịch Spa là hôm nay
    const todayStr = new Date().toISOString().split("T")[0];
    document.getElementById("bkDate").value = todayStr;

    // Chuyển đổi các Tab
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            document.getElementById(targetId).classList.add("active");

            if (targetId === "tab-bookings") loadBookings();
            if (targetId === "tab-orders") loadOrders();
            if (targetId === "tab-data") loadDashboardStats();
        });
    });

    // Nút bật/tắt form thêm sản phẩm
    document.getElementById("btnToggleProductForm").addEventListener("click", () => {
        resetProductForm();
        document.getElementById("productForm").classList.toggle("hidden");
    });

    document.getElementById("btnCancelProduct").addEventListener("click", () => {
        resetProductForm();
        document.getElementById("productForm").classList.add("hidden");
    });

    // Submit thêm/sửa sản phẩm
    document.getElementById("productForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const prodId = document.getElementById("prodId").value;
        const payload = {
            sku: document.getElementById("prodSku").value.trim(),
            name: document.getElementById("prodName").value.trim(),
            category: document.getElementById("prodCategory").value,
            pet_type: document.getElementById("prodPetType").value,
            price: Number(document.getElementById("prodPrice").value),
            stock: Number(document.getElementById("prodStock").value),
            description: document.getElementById("prodDesc").value.trim(),
        };

        try {
            if (prodId) {
                await apiRequest(`/api/products/${prodId}`, {
                    method: "PUT",
                    body: JSON.stringify(payload),
                });
                showAlert(`Đã cập nhật sản phẩm #${prodId}.`);
            } else {
                await apiRequest("/api/products", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
                showAlert("Đã thêm sản phẩm mới thành công.");
            }
            resetProductForm();
            document.getElementById("productForm").classList.add("hidden");
            loadProducts(state.currentPage);
            loadDashboardStats();
        } catch (err) {
            showAlert(err.message, true);
        }
    });

    // Bộ lọc sản phẩm
    document.getElementById("filterForm").addEventListener("submit", (e) => {
        e.preventDefault();
        loadProducts(1);
    });

    document.getElementById("btnResetFilter").addEventListener("click", () => {
        document.getElementById("filterForm").reset();
        loadProducts(1);
    });

    // Phân trang
    document.getElementById("btnPrevPage").addEventListener("click", () => {
        if (state.currentPage > 1) loadProducts(state.currentPage - 1);
    });

    document.getElementById("btnNextPage").addEventListener("click", () => {
        loadProducts(state.currentPage + 1);
    });

    // Giỏ hàng & Đặt hàng
    document.getElementById("btnClearCart").addEventListener("click", () => {
        state.cart = [];
        renderCart();
    });

    document.getElementById("checkoutForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!state.cart.length) {
            showAlert("Giỏ hàng đang trống, vui lòng chọn sản phẩm trước.", true);
            return;
        }

        const payload = {
            customer_name: document.getElementById("orderCustName").value.trim(),
            phone: document.getElementById("orderPhone").value.trim(),
            address: document.getElementById("orderAddress").value.trim(),
            items: state.cart.map((c) => ({ product_id: c.product_id, quantity: c.quantity })),
        };

        try {
            const order = await apiRequest("/api/orders", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            showAlert(`Tạo đơn hàng #${order.id} thành công! Tổng thanh toán: ${formatVND(order.total_amount)}`);
            state.cart = [];
            renderCart();
            document.getElementById("checkoutForm").reset();
            loadProducts(state.currentPage);
            loadDashboardStats();
        } catch (err) {
            showAlert(err.message, true);
        }
    });

    // Lọc & Đặt lịch Spa
    document.getElementById("bookingStatusFilter").addEventListener("change", () => {
        loadBookings();
    });

    document.getElementById("bookingForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
            customer_name: document.getElementById("bkCustName").value.trim(),
            phone: document.getElementById("bkPhone").value.trim(),
            pet_name: document.getElementById("bkPetName").value.trim(),
            pet_type: document.getElementById("bkPetType").value,
            pet_weight_kg: Number(document.getElementById("bkWeight").value),
            service_name: document.getElementById("bkService").value,
            appointment_date: document.getElementById("bkDate").value,
            appointment_time: document.getElementById("bkTime").value,
            note: document.getElementById("bkNote").value.trim(),
        };

        try {
            const created = await apiRequest("/api/bookings", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            showAlert(`Đã đăng ký lịch hẹn #${created.id} cho bé ${created.pet_name} (Phí: ${formatVND(created.total_price)}).`);
            document.getElementById("bookingForm").reset();
            document.getElementById("bkDate").value = todayStr;
            document.getElementById("bkTime").value = "10:00";
            document.getElementById("bkWeight").value = "4.0";
            loadBookings();
            loadDashboardStats();
        } catch (err) {
            showAlert(err.message, true);
        }
    });

    // Tải lại đơn hàng
    document.getElementById("btnRefreshOrders").addEventListener("click", () => {
        loadOrders();
    });

    // Đọc file CSV từ máy tính đưa vào Textarea
    document.getElementById("csvFileInput").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
            document.getElementById("csvTextArea").value = evt.target.result;
        };
        reader.readAsText(file, "UTF-8");
    });

    // Thực thi Import CSV
    document.getElementById("csvImportForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const csvText = document.getElementById("csvTextArea").value;
        try {
            const summary = await apiRequest("/api/products/import-csv", {
                method: "POST",
                body: JSON.stringify({ csv_text: csvText }),
            });
            const resBox = document.getElementById("csvImportResult");
            resBox.classList.remove("hidden");
            resBox.innerHTML = `
                <div><strong>Kết quả Import CSV:</strong> Thêm mới: <strong>${summary.imported}</strong> | Cập nhật: <strong>${summary.updated}</strong></div>
                ${summary.errors && summary.errors.length ? `<div style="color:#991b1b;margin-top:4px">Lỗi: ${summary.errors.join("; ")}</div>` : ""}
            `;
            showAlert(`Import hoàn tất: +${summary.imported} mới, cập nhật ${summary.updated} sản phẩm.`);
            loadProducts(1);
            loadDashboardStats();
        } catch (err) {
            showAlert(err.message, true);
        }
    });

    // Khởi chạy dữ liệu ban đầu
    loadProducts(1);
    loadDashboardStats();
});
