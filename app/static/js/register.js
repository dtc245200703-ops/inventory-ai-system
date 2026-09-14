document.getElementById('registerForm').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button');
    const box = document.getElementById('registerMessage');
    const payload = Object.fromEntries(new FormData(form));
    box.className = 'error-message';
    if (payload.password !== payload.password_confirmation) {
        box.textContent = 'Mật khẩu xác nhận không khớp.';
        return;
    }
    payload.email = payload.email || null;
    button.disabled = true; box.textContent = '';
    try {
        const response = await fetch('/auth/register', {method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-Requested-With': 'inventory-app'},
            body: JSON.stringify(payload)});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Thông tin chưa hợp lệ. Kiểm tra tên đăng nhập, email và mật khẩu.');
        form.reset(); form.remove();
        box.className = 'success-message'; box.textContent = data.message;
        document.getElementById('loginLink').focus();
    } catch (error) { box.textContent = error.message || 'Không kết nối được máy chủ.'; }
    finally { button.disabled = false; }
});
