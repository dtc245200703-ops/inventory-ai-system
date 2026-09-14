let sessionPromise;
function getSession() {
    if (!sessionPromise) sessionPromise = fetch('/auth/me', {cache: 'no-store'}).then(async response => {
        if (response.status === 401) { window.location.replace('/login'); throw new Error('Phiên đã hết hạn.'); }
        if (!response.ok) throw new Error('Không tải được phiên đăng nhập.');
        return response.json();
    }).catch(error => { sessionPromise = null; throw error; });
    return sessionPromise;
}
async function api(url, options = {}) {
    const session = await getSession();
    const headers = {...options.headers};
    if (options.method && options.method !== 'GET') headers['X-CSRF-Token'] = session.csrf_token;
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(url, {...options, headers, credentials: 'same-origin', cache: 'no-store'});
    if (response.status === 401) { window.location.replace('/login'); throw new Error('Phiên đã hết hạn.'); }
    const data = response.status === 204 ? null : await response.json();
    if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Dữ liệu chưa hợp lệ. Kiểm tra các trường nhập.');
    return data;
}
function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
}
function message(text, error = false) {
    const box = document.getElementById('pageMessage');
    box.textContent = text;
    box.className = error ? 'error-message' : 'success-message';
}
document.getElementById('logout').addEventListener('click', async () => {
    try { await api('/auth/logout', {method: 'POST'}); window.location.replace('/login'); }
    catch (error) { message(error.message, true); }
});
window.addEventListener('pageshow', event => { if (event.persisted) { sessionPromise = null; getSession(); } });
