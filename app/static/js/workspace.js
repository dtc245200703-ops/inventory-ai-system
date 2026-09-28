const page = document.body.dataset.page;
const roleLabels = {admin: 'Quản trị viên', thu_kho: 'Thủ kho', ke_toan: 'Kế toán', nhan_hang: 'Nhãn hàng / Đối tác'};
let products = [], suppliers = [];
const moneyText = value => value == null ? 'Chưa có giá' : amountText(minorUnits(String(value)));
// Integer minor units keep the preview exact even for large prices.
function minorUnits(value) {
    if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
    const [whole, fraction = ''] = value.split('.');
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
}
function amountText(value) {
    return `${(value / 100n).toLocaleString('vi-VN')},${String(value % 100n).padStart(2, '0')} ₫`;
}
function updateDocumentTotal() {
    let total = 0n, known = true;
    document.querySelectorAll('.doc-line').forEach(row => {
        const product = products.find(item => item.product_id === Number(row.querySelector('select').value));
        const fallback = product?.[page === 'receipts' ? 'purchase_price' : 'sale_price'];
        const price = minorUnits(row.querySelector('.line-price').value || String(fallback ?? ''));
        const quantity = row.querySelector('.line-quantity').value;
        const valid = price !== null && /^\d+$/.test(quantity) && BigInt(quantity) > 0n;
        const amount = valid ? price * BigInt(quantity) : null;
        row.querySelector('.line-total').textContent = amount === null ? 'Chưa có giá / số lượng' : amountText(amount);
        if (amount === null) known = false; else total += amount;
    });
    const output = document.getElementById('documentTotal');
    if (output) output.textContent = known ? `Tổng tiền: ${amountText(total)}` : 'Tổng tiền: chưa đủ giá / số lượng';
}
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
    qty.className = 'line-quantity';
    const priceLabel = node('label', page === 'receipts' ? 'Giá nhập (VNĐ)' : 'Giá xuất (VNĐ)');
    const price = node('input'); price.type = 'number'; price.min = '0'; price.max = '999999999999.99'; price.step = '0.01'; price.className = 'line-price'; price.placeholder = 'Chưa có giá'; priceLabel.append(price);
    const totalLabel = node('label', 'Thành tiền'); totalLabel.append(node('output', 'Chưa có giá', 'line-total'));
    function validateStock() {
        const product = products.find(item => item.product_id === Number(select.value));
        if (page === 'issues') {
            qty.max = product ? String(product.quantity_available) : '';
            qty.setCustomValidity(product && Number(qty.value) > product.quantity_available ? `Chỉ còn ${product.quantity_available} trong kho.` : '');
        }
    }
    select.addEventListener('change', () => {
        const product = products.find(item => item.product_id === Number(select.value));
        price.value = product?.[page === 'receipts' ? 'purchase_price' : 'sale_price'] ?? '';
        validateStock(); updateDocumentTotal();
    });
    qty.addEventListener('input', () => { validateStock(); updateDocumentTotal(); });
    price.addEventListener('input', updateDocumentTotal);
    const remove = node('button', 'Xóa dòng', 'btn-secondary'); remove.type = 'button'; remove.addEventListener('click', () => { row.remove(); updateDocumentTotal(); });
    row.append(productLabel, qtyLabel, priceLabel, totalLabel, remove); document.getElementById('documentLines').append(row);
    updateDocumentTotal();
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
                    ...(page === 'issues' ? ['Người nhận', 'Lý do xuất'] : []), 'Trạng thái', 'Tổng tiền', 'Chi tiết'];
                table(headers, docs.map(d => {
                    const details = node('details'); details.append(node('summary', `${d.items.length} dòng hàng`)); const list = node('ul');
                    d.items.forEach(i => list.append(node('li', `${names.get(i.product_id) || i.product_id}: ${i.quantity} × ${moneyText(i.unit_price)} = ${moneyText(i.line_total)}`))); details.append(list);
                    const stamp = d.receipt_date || d.issue_date;
                    return [d.receipt_no || d.issue_no, stamp ? new Date(stamp.endsWith('Z') ? stamp : stamp + 'Z').toLocaleString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'}) : '—', d.created_by, ...(page === 'issues' ? [d.receiver, d.reason] : []), d.status, d.total_amount == null ? 'Chưa đủ giá' : moneyText(d.total_amount), details];
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
    const items = [...document.querySelectorAll('.doc-line')].map(row => ({
        product_id: Number(row.querySelector('select').value),
        quantity: Number(row.querySelector('.line-quantity').value),
        unit_price: row.querySelector('.line-price').value || null,
    }));
    if (!items.length) throw new Error('Thêm ít nhất một dòng hàng.');
    const result = {items};
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
