document.getElementById('loginForm').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button');
    const message = document.getElementById('loginError');
    button.disabled = true;
    message.textContent = '';
    try {
        const response = await fetch('/auth/login', {method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-Requested-With': 'inventory-app'},
            body: JSON.stringify(Object.fromEntries(new FormData(form)))});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Kiểm tra thông tin đăng nhập.');
        window.location.replace('/');
    } catch (error) { message.textContent = error.message || 'Không kết nối được máy chủ.'; }
    finally { button.disabled = false; }
});
