/**
 * static/js/shop.js
 * Logic Front-end cho Trang Bán Hàng & Đặt Lịch Spa (Khách hàng)
 */

const shopState = {
    page: 1,
    pageSize: 6,
    products: [],
    cart: JSON.parse(localStorage.getItem("mw_petshop_cart") || "[]"),
};

const SPA_BASE_PRICES = {
    "Tắm sấy & Vệ sinh tai móng": 150000,
    "Cắt tỉa & Tạo kiểu lông (Grooming)": 280000,
    "Cạo lông máu / Cạo vệ sinh": 180000,
    "Khám sức khỏe & Tư vấn dinh dưỡng": 120000,
    "Trông giữ thú cưng (1 ngày)": 200000,
};

function formatCurrency(val) {
    return Number(val || 0).toLocaleString("vi-VN") + " đ";
}

function escapeHtml(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function showToast(msg, isError = false) {
    const toast = document.getElementById("toastBox");
    toast.textContent = msg;
    toast.className = "toast" + (isError ? " error" : "");
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3800);
}

async function callShopApi(url, options = {}) {
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const json = await res.json();
    if (!res.ok || json.ok === false) {
        throw new Error(json.error || "Có lỗi xảy ra");
    }
    return json.data;
}

// ============================================================================
// 1. HIỂN THỊ & LỌC SẢN PHẨM TRÊN CỬA HÀNG
// ============================================================================

function getCategorySymbol(category) {
    const map = {
        "Thức ăn": "FD",
        "Vệ sinh & Chăm sóc": "VS",
        "Phụ kiện": "PK",
        "Đồ chơi": "TOY",
        "Y tế & Vitamin": "MED",
    };
    return map[category] || "PET";
}

async function fetchShopProducts(page = 1) {
    shopState.page = page;
    const keyword = document.getElementById("shopSearchInput").value.trim();
    const petType = document.getElementById("sidePetType").value;
    const category = document.getElementById("sideCategory").value;
    const minPrice = document.getElementById("sideMinPrice").value;
    const maxPrice = document.getElementById("sideMaxPrice").value;
    const inStock = document.getElementById("sideInStock").checked ? "1" : "0";
    const sortBy = document.getElementById("shopSortSelect").value;

    const qs = new URLSearchParams({
        keyword,
        pet_type: petType,
        category,
        min_price: minPrice,
        max_price: maxPrice,
        in_stock_only: inStock,
        sort_by: sortBy,
        page: String(page),
        page_size: String(shopState.pageSize),
    });

    try {
        const data = await callShopApi(`/api/products?${qs.toString()}`);
        shopState.products = data.items || [];
        renderShopProducts(shopState.products);

        document.getElementById("shopTotalItems").textContent = data.total_items;
        document.getElementById("shopPageText").textContent = `Trang ${data.page} / ${data.total_pages}`;
        document.getElementById("shopPrevPage").disabled = !data.has_prev;
        document.getElementById("shopNextPage").disabled = !data.has_next;
    } catch (err) {
        showToast(err.message, true);
    }
}

function renderShopProducts(items) {
    const grid = document.getElementById("shopProductGrid");
    if (!items.length) {
        grid.innerHTML = `<div class="empty-state">Không tìm thấy sản phẩm nào khớp với điều kiện lọc của bạn.</div>`;
        return;
    }

    grid.innerHTML = items
        .map((p) => {
            let petClass = "";
            if (p.pet_type === "Mèo") petClass = "cat";
            else if (p.pet_type === "Chó") petClass = "dog";

            let stockClass = "stock-ok";
            let stockLabel = `Còn ${p.stock}`;
            if (p.stock === 0) {
                stockClass = "stock-out";
                stockLabel = "Hết hàng";
            } else if (p.stock <= 5) {
                stockClass = "stock-low";
                stockLabel = `Chỉ còn ${p.stock}`;
            }

            const symbol = getCategorySymbol(p.category);

            return `
            <article class="product-card">
                <div>
                    <div class="product-thumb">
                        <span class="pet-badge ${petClass}">${escapeHtml(p.pet_type)}</span>
                        <span class="stock-tag ${stockClass}">${stockLabel}</span>
                        <div class="thumb-icon">${symbol}</div>
                        <span class="thumb-cat-label">${escapeHtml(p.category)}</span>
                    </div>
                    <div class="product-body">
                        <div class="product-sku">Mã SP: ${escapeHtml(p.sku)}</div>
                        <h3 class="product-title">${escapeHtml(p.name)}</h3>
                        <p class="product-desc">${escapeHtml(p.description || "")}</p>
                    </div>
                </div>
                <div class="product-footer">
                    <span class="product-price">${formatCurrency(p.price)}</span>
                    <button
                        type="button"
                        class="btn-primary"
                        onclick="addProductToShopCart(${p.id})"
                        ${p.stock <= 0 ? "disabled" : ""}
                    >
                        ${p.stock > 0 ? "+ Thêm vào giỏ" : "Tạm hết"}
                    </button>
                </div>
            </article>
        `;
        })
        .join("");
}

// ============================================================================
// 2. GIỎ HÀNG & THANH TOÁN
// ============================================================================

function saveCart() {
    localStorage.setItem("mw_petshop_cart", JSON.stringify(shopState.cart));
    const totalCount = shopState.cart.reduce((sum, item) => sum + item.quantity, 0);
    document.getElementById("cartCountBadge").textContent = totalCount;
}

function addProductToShopCart(productId) {
    const p = shopState.products.find((item) => item.id === productId);
    if (!p) return;

    const existing = shopState.cart.find((c) => c.product_id === productId);
    if (existing) {
        if (existing.quantity + 1 > p.stock) {
            showToast(`Sản phẩm "${p.name}" chỉ còn tối đa ${p.stock} món.`, true);
            return;
        }
        existing.quantity += 1;
    } else {
        shopState.cart.push({
            product_id: p.id,
            name: p.name,
            price: p.price,
            max_stock: p.stock,
            quantity: 1,
        });
    }

    saveCart();
    renderShopCartModal();
    showToast(`Đã thêm "${p.name}" vào giỏ hàng!`);
}

function updateShopCartQty(productId, delta) {
    const idx = shopState.cart.findIndex((c) => c.product_id === productId);
    if (idx === -1) return;

    const item = shopState.cart[idx];
    const nextQty = item.quantity + delta;
    if (nextQty <= 0) {
        shopState.cart.splice(idx, 1);
    } else if (nextQty > item.max_stock) {
        showToast(`Kho chỉ còn ${item.max_stock} sản phẩm này.`, true);
        return;
    } else {
        item.quantity = nextQty;
    }

    saveCart();
    renderShopCartModal();
}

function renderShopCartModal() {
    const listEl = document.getElementById("shopCartItemsList");
    const totalEl = document.getElementById("shopCartTotal");

    if (!shopState.cart.length) {
        listEl.innerHTML = `<p style="color:#6b7280; padding:12px 0;">Giỏ hàng của bạn đang trống.</p>`;
        totalEl.textContent = "0 đ";
        return;
    }

    let total = 0;
    listEl.innerHTML = shopState.cart
        .map((item) => {
            const sub = item.price * item.quantity;
            total += sub;
            return `
            <div class="cart-row">
                <div>
                    <strong>${escapeHtml(item.name)}</strong>
                    <div style="font-size:12px; color:#6b7280;">
                        ${formatCurrency(item.price)} x ${item.quantity} = <strong>${formatCurrency(sub)}</strong>
                    </div>
                </div>
                <div class="cart-qty-btns">
                    <button type="button" class="btn-light" style="padding:3px 9px;" onclick="updateShopCartQty(${item.product_id}, -1)">-</button>
                    <span>${item.quantity}</span>
                    <button type="button" class="btn-light" style="padding:3px 9px;" onclick="updateShopCartQty(${item.product_id}, 1)">+</button>
                </div>
            </div>
        `;
        })
        .join("");

    totalEl.textContent = formatCurrency(total);
}

// ============================================================================
// 3. TÍNH GIÁ SPA TỰ ĐỘNG & ĐẶT LỊCH
// ============================================================================

function updateEstimatedSpaPrice() {
    const service = document.getElementById("cBkService").value;
    const weight = parseFloat(document.getElementById("cBkWeight").value) || 0;
    const base = SPA_BASE_PRICES[service] || 150000;

    let multiplier = 1.0;
    if (weight > 10) multiplier = 1.4;
    else if (weight >= 5) multiplier = 1.2;

    const estimated = Math.round(base * multiplier);
    document.getElementById("cBkEstimatedPrice").textContent = formatCurrency(estimated);
}

// ============================================================================
// 4. KHỞI TẠO SỰ KIỆN
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    const today = new Date().toISOString().split("T")[0];
    document.getElementById("cBkDate").value = today;

    saveCart();
    fetchShopProducts(1);
    updateEstimatedSpaPrice();

    // Thanh tìm kiếm trên Header
    document.getElementById("headerSearchForm").addEventListener("submit", (e) => {
        e.preventDefault();
        fetchShopProducts(1);
        document.getElementById("section-shop").scrollIntoView({ behavior: "smooth" });
    });

    // Thanh chọn danh mục nhanh
    document.querySelectorAll("#quickCategoryNav .cat-link").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#quickCategoryNav .cat-link").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");

            document.getElementById("sideCategory").value = btn.getAttribute("data-cat");
            document.getElementById("sidePetType").value = btn.getAttribute("data-pet");
            fetchShopProducts(1);
        });
    });

    // Nút áp dụng & xóa bộ lọc bên trái
    document.getElementById("btnApplyFilter").addEventListener("click", () => {
        fetchShopProducts(1);
    });

    document.getElementById("btnResetShopFilter").addEventListener("click", () => {
        document.getElementById("shopSearchInput").value = "";
        document.getElementById("sidePetType").value = "ALL";
        document.getElementById("sideCategory").value = "ALL";
        document.getElementById("sideMinPrice").value = "";
        document.getElementById("sideMaxPrice").value = "";
        document.getElementById("sideInStock").checked = false;
        document.getElementById("shopSortSelect").value = "id_desc";
        fetchShopProducts(1);
    });

    document.getElementById("shopSortSelect").addEventListener("change", () => {
        fetchShopProducts(1);
    });

    // Phân trang
    document.getElementById("shopPrevPage").addEventListener("click", () => {
        if (shopState.page > 1) fetchShopProducts(shopState.page - 1);
    });

    document.getElementById("shopNextPage").addEventListener("click", () => {
        fetchShopProducts(shopState.page + 1);
    });

    // Mở / Đóng Modal Giỏ hàng
    document.getElementById("btnOpenCart").addEventListener("click", () => {
        renderShopCartModal();
        document.getElementById("cartModal").classList.remove("hidden");
    });

    document.getElementById("btnCloseCart").addEventListener("click", () => {
        document.getElementById("cartModal").classList.add("hidden");
    });

    document.getElementById("btnClearShopCart").addEventListener("click", () => {
        shopState.cart = [];
        saveCart();
        renderShopCartModal();
    });

    // Đặt mua hàng
    document.getElementById("shopCheckoutForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!shopState.cart.length) {
            showToast("Giỏ hàng của bạn đang trống!", true);
            return;
        }

        const phone = document.getElementById("coPhone").value.trim();
        const payload = {
            customer_name: document.getElementById("coName").value.trim(),
            phone,
            address: document.getElementById("coAddress").value.trim(),
            items: shopState.cart.map((c) => ({ product_id: c.product_id, quantity: c.quantity })),
        };

        try {
            const order = await callShopApi("/api/orders", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            showToast(`Đặt hàng thành công! Mã đơn #${order.id} - Tổng: ${formatCurrency(order.total_amount)}`);
            shopState.cart = [];
            saveCart();
            renderShopCartModal();
            document.getElementById("shopCheckoutForm").reset();
            document.getElementById("cartModal").classList.add("hidden");
            fetchShopProducts(shopState.page);

            // Tự động điền SĐT vừa đặt vào ô tra cứu để khách tiện kiểm tra
            document.getElementById("lookupPhoneInput").value = phone;
        } catch (err) {
            showToast(err.message, true);
        }
    });

    // Tính giá Spa khi đổi cân nặng hoặc gói dịch vụ
    document.getElementById("cBkService").addEventListener("change", updateEstimatedSpaPrice);
    document.getElementById("cBkWeight").addEventListener("input", updateEstimatedSpaPrice);

    // Gửi phiếu đặt lịch Spa
    document.getElementById("customerBookingForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const phone = document.getElementById("cBkPhone").value.trim();
        const payload = {
            customer_name: document.getElementById("cBkName").value.trim(),
            phone,
            pet_name: document.getElementById("cBkPetName").value.trim(),
            pet_type: document.getElementById("cBkPetType").value,
            pet_weight_kg: parseFloat(document.getElementById("cBkWeight").value),
            service_name: document.getElementById("cBkService").value,
            appointment_date: document.getElementById("cBkDate").value,
            appointment_time: document.getElementById("cBkTime").value,
            note: document.getElementById("cBkNote").value.trim(),
        };

        try {
            const booking = await callShopApi("/api/bookings", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            showToast(`Đặt lịch thành công cho bé ${booking.pet_name}! Mã lịch hẹn #${booking.id}`);
            document.getElementById("customerBookingForm").reset();
            document.getElementById("cBkDate").value = today;
            document.getElementById("cBkTime").value = "09:30";
            document.getElementById("cBkWeight").value = "4.0";
            updateEstimatedSpaPrice();

            document.getElementById("lookupPhoneInput").value = phone;
        } catch (err) {
            showToast(err.message, true);
        }
    });

    // Tra cứu đơn hàng & lịch hẹn theo số điện thoại
    document.getElementById("lookupForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const phone = document.getElementById("lookupPhoneInput").value.trim();
        if (!phone) return;

        try {
            const result = await callShopApi(`/api/lookup?phone=${encodeURIComponent(phone)}`);
            const box = document.getElementById("lookupResultBox");
            box.classList.remove("hidden");

            const ordersHtml = result.orders.length
                ? result.orders
                      .map(
                          (o) => `
                    <div class="lookup-item">
                        <div><strong>Đơn hàng #${o.id}</strong> - Ngày: ${escapeHtml(o.created_at)}</div>
                        <div>Người nhận: ${escapeHtml(o.customer_name)} (${escapeHtml(o.phone)})</div>
                        <div>Địa chỉ: ${escapeHtml(o.address)}</div>
                        <div>Sản phẩm: ${(o.items || []).map((i) => `${escapeHtml(i.name)} (x${i.quantity})`).join(", ")}</div>
                        <div>Tổng thanh toán: <strong style="color:#c2410c;">${formatCurrency(o.total_amount)}</strong></div>
                    </div>
                `
                      )
                      .join("")
                : `<p style="color:#6b7280;">Chưa tìm thấy đơn mua hàng nào với SĐT này.</p>`;

            const bookingsHtml = result.bookings.length
                ? result.bookings
                      .map(
                          (b) => `
                    <div class="lookup-item">
                        <div><strong>Lịch hẹn #${b.id}</strong> - Trạng thái: <strong>${escapeHtml(b.status)}</strong></div>
                        <div>Thú cưng: <strong>${escapeHtml(b.pet_name)}</strong> (${escapeHtml(b.pet_type)}, ${b.pet_weight_kg}kg)</div>
                        <div>Dịch vụ: ${escapeHtml(b.service_name)}</div>
                        <div>Thời gian: ${escapeHtml(b.appointment_date)} lúc ${escapeHtml(b.appointment_time)}</div>
                        <div>Chi phí: <strong style="color:#c2410c;">${formatCurrency(b.total_price)}</strong></div>
                    </div>
                `
                      )
                      .join("")
                : `<p style="color:#6b7280;">Chưa tìm thấy lịch hẹn Spa nào với SĐT này.</p>`;

            box.innerHTML = `
                <div class="lookup-box">
                    <h4>Đơn mua hàng (${result.orders.length})</h4>
                    ${ordersHtml}
                </div>
                <div class="lookup-box">
                    <h4>Lịch hẹn Spa (${result.bookings.length})</h4>
                    ${bookingsHtml}
                </div>
            `;
        } catch (err) {
            showToast(err.message, true);
        }
    });
});
