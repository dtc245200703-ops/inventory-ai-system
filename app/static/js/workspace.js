const page = document.body.dataset.page;
const roleLabels = {admin: 'Quản trị viên', thu_kho: 'Thủ kho', ke_toan: 'Kế toán'};
let products = [], suppliers = [];
function option(value, text) { const el = node('option', text); el.value = value; return el; }
function fillProducts(select) {
    select.replaceChildren(option('', 'Chọn sản phẩm'));
    products.forEach(p => select.append(option(p.product_id, `${p.product_code} · ${p.product_name}${page === 'issues' ? ` (tồn: ${p.quantity_available})` : ''}`)));
}
function addLine() {
    const row = node('div', undefined, 'doc-line');
    const productLabel = node('label', 'Sản phẩm');
    const select = node('select'); select.required = true; fillProducts(select); productLabel.append(select);
    const qtyLabel = node('label', 'Số lượng');
    const qty = node('input'); qty.type = 'number'; qty.min = '1'; qty.step = '1'; qty.value = '1'; qty.required = true; qtyLabel.append(qty);
    if (page === 'issues') select.addEventListener('change', () => {
        const product = products.find(item => item.product_id === Number(select.value));
        qty.max = product ? String(product.quantity_available) : '';
        qty.setCustomValidity(product && Number(qty.value) > product.quantity_available ? `Chỉ còn ${product.quantity_available} trong kho.` : '');
    });
    qty.addEventListener('input', () => select.dispatchEvent(new Event('change')));
    const remove = node('button', 'Xóa dòng', 'btn-secondary'); remove.type = 'button'; remove.addEventListener('click', () => row.remove());
    row.append(productLabel, qtyLabel, remove); document.getElementById('documentLines').append(row);
}
function table(headers, rows) {
    const head = document.getElementById('listHead'), body = document.getElementById('listBody');
    const tr = node('tr'); headers.forEach(h => tr.append(node('th', h))); head.replaceChildren(tr); body.replaceChildren();
    if (!rows.length) { const tr = node('tr'); const td = node('td', 'Chưa có dữ liệu.', 'empty'); td.colSpan = headers.length; tr.append(td); body.append(tr); }
    rows.forEach(cells => { const row = node('tr'); cells.forEach(value => { const td = node('td'); if (value instanceof Node) td.append(value); else td.textContent = value ?? '—'; row.append(td); }); body.append(row); });
}
function userActions(user) {
    const box = node('div', undefined, 'account-actions');
    const fullName = node('input'); fullName.value=user.full_name||''; fullName.placeholder='Họ tên'; fullName.setAttribute('aria-label',`Họ tên ${user.username}`);
    const role = node('select'); role.setAttribute('aria-label', `Vai trò ${user.username}`);
    Object.entries(roleLabels).forEach(([value, label]) => role.append(option(value, label))); role.value = user.role;
    const active = node('select'); active.setAttribute('aria-label', `Trạng thái ${user.username}`);
    active.append(option('1', 'Hoạt động'), option('0', 'Chờ duyệt / Đã khóa')); active.value = user.is_active ? '1' : '0';
    const password = node('input'); password.type = 'password'; password.autocomplete = 'new-password'; password.placeholder = 'Mật khẩu mới (tùy chọn)'; password.setAttribute('aria-label', `Mật khẩu mới ${user.username}`);
    const save = node('button', 'Lưu', 'btn-secondary');
    save.addEventListener('click', async () => {
        save.disabled = true;
        try { await api(`/users/${user.id}`, {method: 'PATCH', body: JSON.stringify({full_name:fullName.value,role: role.value, is_active: active.value === '1', password: password.value || null})}); password.value = ''; message('Đã lưu. Các phiên của tài khoản này đã được đăng xuất.'); await loadList(); }
        catch (error) { message(error.message, true); } finally { save.disabled = false; }
    });
    box.append(fullName, role, active, password, save); return box;
}
async function loadList() {
    const reload = document.getElementById('reload'); reload.disabled = true;
    try {
        if (page === 'users') {
            const users = await api('/users/');
            table(['Tài khoản', 'Họ tên', 'Vai trò', 'Trạng thái', 'Quản lý'], users.map(u => [u.username, u.full_name, roleLabels[u.role], u.is_active ? 'Hoạt động' : 'Đã khóa', userActions(u)]));
        } else {
            products = await api('/products/');
            const names = new Map(products.map(p => [p.product_id, p.product_name]));
            if (page === 'products') table(['Mã hàng', 'Tên hàng', 'Đơn vị', 'Tồn tối thiểu'], products.map(p => [p.product_code, p.product_name, p.unit, p.min_stock_level]));
            if (page === 'receipts' || page === 'issues') {
                const docs = await api(`/${page}/`);
                const headers = ['Số phiếu', page === 'issues' ? 'Ngày xuất' : 'Ngày lập (giờ Việt Nam)', 'Người lập',
                    ...(page === 'issues' ? ['Người nhận', 'Lý do xuất'] : []), 'Trạng thái', 'Chi tiết'];
                table(headers, docs.map(d => {
                    const details = node('details'); details.append(node('summary', `${d.items.length} dòng hàng`)); const list = node('ul');
                    d.items.forEach(i => list.append(node('li', `${names.get(i.product_id) || i.product_id}: ${i.quantity}`))); details.append(list);
                    const stamp = d.receipt_date || d.issue_date;
                    return [d.receipt_no || d.issue_no, stamp ? new Date(stamp.endsWith('Z') ? stamp : stamp + 'Z').toLocaleString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'}) : '—', d.created_by, ...(page === 'issues' ? [d.receiver, d.reason] : []), d.status, details];
                }));
                if (document.getElementById('supplierSelect')) {
                    suppliers = await api('/suppliers/'); const select = document.getElementById('supplierSelect');
                    select.replaceChildren(option('', 'Chọn nhà cung cấp'));
                    suppliers.forEach(s => select.append(option(s.supplier_id, s.name)));
                }
                if (document.getElementById('documentLines') && !document.querySelector('.doc-line')) addLine();
            }
        }
    } catch (error) { message(error.message, true); } finally { reload.disabled = false; }
}
function bindForm(id, endpoint, build) {
    const form = document.getElementById(id); if (!form) return;
    form.addEventListener('submit', async event => {
        event.preventDefault(); const button = form.querySelector('[type="submit"]'); button.disabled = true;
        try {
            const values = Object.fromEntries(new FormData(form)); const request = build(values);
            await api(typeof endpoint === 'function' ? endpoint(values) : endpoint, {method: id === 'inventoryForm' ? 'PUT' : 'POST', body: JSON.stringify(request)});
            form.reset();
            if (id === 'documentForm') document.getElementById('documentLines').replaceChildren();
            message('Đã lưu thành công.'); await loadList();
        } catch (error) { message(error.message, true); } finally { button.disabled = false; }
    });
}
bindForm('productForm', '/products/', v => ({...v, min_stock_level: Number(v.min_stock_level)}));
bindForm('inventoryForm', v => `/inventory/${v.product_id}`, v => ({quantity_available: Number(v.quantity_available)}));
bindForm('supplierForm', '/suppliers/', v => v);
bindForm('accountForm', '/users/', v => ({...v, email: v.email || null}));
bindForm('documentForm', `/${page}/`, v => {
    const totals = new Map();
    document.querySelectorAll('.doc-line').forEach(row => { const id = Number(row.querySelector('select').value); totals.set(id, (totals.get(id) || 0) + Number(row.querySelector('input').value)); });
    if (!totals.size) throw new Error('Thêm ít nhất một dòng hàng.');
    const result = {items: [...totals].map(([product_id, quantity]) => ({product_id, quantity}))};
    if (page === 'receipts') result.supplier_id = Number(v.supplier_id); else { result.receiver = v.receiver; result.reason = v.reason; }
    return result;
});
document.getElementById('addLine')?.addEventListener('click', addLine);
document.getElementById('cancelDocument')?.addEventListener('click', () => {
    const form = document.getElementById('documentForm');
    form.reset();
    document.getElementById('documentLines').replaceChildren();
    addLine();
    message('Đã hủy nội dung phiếu đang nhập.');
});
document.getElementById('reload').addEventListener('click', loadList);
loadList();
