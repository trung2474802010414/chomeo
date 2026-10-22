let currentSpecies = 'All';
let currentPage = 1;
let currentUser = null;
let cart = [];

// Khởi chạy khi tải trang
document.addEventListener("DOMContentLoaded", async () => {
    await checkCurrentUser();
    fetchPets(1);
});

// ==========================================
// 1. QUẢN LÝ ĐĂNG NHẬP / ĐĂNG KÝ / PHÂN QUYỀN
// ==========================================
async function checkCurrentUser() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        currentUser = data.user;
        updateAuthUI();
    } catch (err) {
        console.error("Lỗi kiểm tra phiên đăng nhập:", err);
    }
}

function updateAuthUI() {
    const greeting = document.getElementById('userGreeting');
    const btnLogin = document.getElementById('btnLoginModal');
    const btnLogout = document.getElementById('btnLogout');
    const btnAdminAdd = document.getElementById('btnAdminAdd');

    if (currentUser) {
        const roleBadge = currentUser.role === 'admin' ? '👑 Admin' : '👤 Khách';
        greeting.innerText = `${roleBadge}: ${currentUser.full_name}`;
        greeting.style.display = 'inline-block';
        btnLogin.style.display = 'none';
        btnLogout.style.display = 'inline-block';

        // Chỉ hiển thị nút "+ Thêm Thú Cưng" nếu là Admin
        btnAdminAdd.style.display = (currentUser.role === 'admin') ? 'inline-block' : 'none';
    } else {
        greeting.style.display = 'none';
        btnLogin.style.display = 'inline-block';
        btnLogout.style.display = 'none';
        btnAdminAdd.style.display = 'none';
    }
}

function switchAuthTab(tab) {
    const loginForm = document.getElementById('loginForm');
    const regForm = document.getElementById('registerForm');
    const tabLogin = document.getElementById('tabLogin');
    const tabRegister = document.getElementById('tabRegister');

    if (tab === 'login') {
        loginForm.style.display = 'block';
        regForm.style.display = 'none';
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
    } else {
        loginForm.style.display = 'none';
        regForm.style.display = 'block';
        tabLogin.classList.remove('active');
        tabRegister.classList.add('active');
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const result = await res.json();
    alert(result.message);

    if (result.status === 'success') {
        currentUser = result.user;
        updateAuthUI();
        document.getElementById('loginForm').reset();
        toggleModal('authModal');
        fetchPets(currentPage); // Render lại để hiện nút xóa nếu là Admin
    }
}

async function handleRegister(event) {
    event.preventDefault();
    const full_name = document.getElementById('regFullName').value;
    const username = document.getElementById('regUsername').value;
    const password = document.getElementById('regPassword').value;

    const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name, username, password })
    });
    const result = await res.json();
    alert(result.message);

    if (result.status === 'success') {
        document.getElementById('registerForm').reset();
        switchAuthTab('login');
    }
}

async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    updateAuthUI();
    fetchPets(currentPage);
}

// ==========================================
// 2. LẤY DANH SÁCH THÚ CƯNG & PHÂN TRANG
// ==========================================
async function fetchPets(page = 1) {
    currentPage = page;
    const search = document.getElementById('searchInput').value;
    const sort = document.getElementById('sortSelect').value;
    const url = `/api/pets?species=${encodeURIComponent(currentSpecies)}&search=${encodeURIComponent(search)}&sort=${sort}&page=${page}&per_page=4`;
    
    try {
        const response = await fetch(url);
        const result = await response.json();
        if (result.status === "success") {
            renderPets(result.data);
            renderPagination(result.pagination);
        }
    } catch (error) {
        console.error("Lỗi khi tải dữ liệu:", error);
    }
}

function renderPets(pets) {
    const grid = document.getElementById('petGrid');
    grid.innerHTML = '';

    if (pets.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; padding: 30px;">Không tìm thấy thú cưng nào phù hợp!</p>';
        return;
    }

    const isAdmin = currentUser && currentUser.role === 'admin';

    pets.forEach(pet => {
        const formattedPrice = pet.price.toLocaleString('vi-VN');
        const deleteBtnHTML = isAdmin 
            ? `<button class="btn-delete" onclick="deletePet(${pet.id})" title="Xóa thú cưng (Admin)">🗑</button>` 
            : '';

        const card = document.createElement('div');
        card.className = 'pet-card';
        card.innerHTML = `
            <img src="${pet.image}" alt="${pet.name}" onerror="this.src='https://via.placeholder.com/300x210?text=PetHouse'">
            <div class="pet-info">
                <span class="pet-tag">${pet.species}</span>
                <h3 class="pet-name">${pet.name}</h3>
                <p class="pet-details">Giống: ${pet.breed} | ${pet.age} tháng tuổi</p>
                <div class="pet-price">${formattedPrice} VNĐ</div>
                <div class="card-actions">
                    <button class="btn-buy" onclick='addToCart(${JSON.stringify(pet)})'>+ Thêm vào giỏ</button>
                    ${deleteBtnHTML}
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

function renderPagination(pagination) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';

    if (pagination.total_pages <= 1) return;

    // Nút Trang trước
    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.innerText = '« Trước';
    prevBtn.disabled = pagination.current_page === 1;
    prevBtn.onclick = () => fetchPets(pagination.current_page - 1);
    container.appendChild(prevBtn);

    // Các nút số trang
    for (let i = 1; i <= pagination.total_pages; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === pagination.current_page ? 'active' : ''}`;
        btn.innerText = i;
        btn.onclick = () => fetchPets(i);
        container.appendChild(btn);
    }

    // Nút Trang sau
    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.innerText = 'Sau »';
    nextBtn.disabled = pagination.current_page === pagination.total_pages;
    nextBtn.onclick = () => fetchPets(pagination.current_page + 1);
    container.appendChild(nextBtn);
}

function filterSpecies(species, btnElement) {
    currentSpecies = species;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    btnElement.classList.add('active');
    fetchPets(1);
}

// ==========================================
// 3. THÊM & XÓA THÚ CƯNG (DÀNH CHO ADMIN)
// ==========================================
async function handleAddPet(event) {
    event.preventDefault();
    
    const newPet = {
        name: document.getElementById('petName').value,
        species: document.getElementById('petSpecies').value,
        breed: document.getElementById('petBreed').value,
        age: document.getElementById('petAge').value,
        price: document.getElementById('petPrice').value,
        image: document.getElementById('petImage').value
    };

    const response = await fetch('/api/pets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPet)
    });

    const result = await response.json();
    alert(result.message);
    
    if (result.status === 'success') {
        document.getElementById('addPetForm').reset();
        toggleModal('adminModal');
        fetchPets(1);
    }
}

async function deletePet(petId) {
    if (!confirm("Bạn có chắc chắn muốn xóa thú cưng này khỏi hệ thống?")) return;

    const response = await fetch(`/api/pets/${petId}`, { method: 'DELETE' });
    const result = await response.json();
    alert(result.message);
    if (result.status === 'success') {
        fetchPets(currentPage);
    }
}

// ==========================================
// 4. GIỎ HÀNG, ĐẶT HÀNG & LỊCH SỬ HÓA ĐƠN
// ==========================================
function addToCart(pet) {
    cart.push(pet);
    updateCartUI();
    alert(`Đã thêm "${pet.name}" vào giỏ hàng!`);
}

function removeFromCart(index) {
    cart.splice(index, 1);
    updateCartUI();
}

function updateCartUI() {
    document.getElementById('cartCount').innerText = cart.length;
    const cartItemsDiv = document.getElementById('cartItems');
    cartItemsDiv.innerHTML = '';

    let total = 0;
    cart.forEach((item, index) => {
        total += item.price;
        cartItemsDiv.innerHTML += `
            <div class="cart-item">
                <span>${item.name} (${item.price.toLocaleString('vi-VN')} đ)</span>
                <button onclick="removeFromCart(${index})" style="color:red; border:none; background:none; cursor:pointer; font-weight:bold;">Xóa</button>
            </div>
        `;
    });

    document.getElementById('cartTotalPrice').innerText = total.toLocaleString('vi-VN');
}

async function handleCheckout(event) {
    event.preventDefault();
    if (cart.length === 0) {
        alert("Giỏ hàng của bạn đang trống!");
        return;
    }

    const totalPrice = cart.reduce((sum, item) => sum + item.price, 0);
    const itemNames = cart.map(item => item.name).join(", ");

    const orderData = {
        customer_name: document.getElementById('cusName').value,
        phone: document.getElementById('cusPhone').value,
        address: document.getElementById('cusAddress').value,
        total_price: totalPrice,
        items: itemNames
    };

    const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
    });

    const result = await response.json();
    alert(result.message);

    if (result.status === 'success') {
        cart = [];
        updateCartUI();
        document.getElementById('checkoutForm').reset();
        toggleModal('cartModal');
    }
}

async function openOrdersModal() {
    toggleModal('ordersModal');
    const res = await fetch('/api/orders');
    const data = await res.json();

    if (data.status === 'success') {
        document.getElementById('statTotalOrders').innerText = data.total_orders;
        document.getElementById('statTotalRevenue').innerText = data.total_revenue.toLocaleString('vi-VN') + ' VNĐ';

        const tbody = document.getElementById('ordersTableBody');
        tbody.innerHTML = '';

        if (data.orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Chưa có đơn hàng nào.</td></tr>';
            return;
        }

        data.orders.forEach(o => {
            tbody.innerHTML += `
                <tr>
                    <td><b>#${o.id}</b></td>
                    <td>${o.customer_name}</td>
                    <td>${o.phone}</td>
                    <td>${o.address}</td>
                    <td>${o.items}</td>
                    <td style="color:#d63031; font-weight:bold;">${o.total_price.toLocaleString('vi-VN')} đ</td>
                    <td>${o.created_at}</td>
                </tr>
            `;
        });
    }
}

function toggleModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.style.display = (modal.style.display === 'flex') ? 'none' : 'flex';
}