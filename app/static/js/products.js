const stockLabels = {in_stock: 'Còn hàng', low_stock: 'Dưới tối thiểu', out_of_stock: 'Hết hàng'};
const stockClasses = {in_stock: 'status-good', low_stock: 'status-warning', out_of_stock: 'status-danger'};
let editingId = null, detailProduct = null, deletingProduct = null, requestVersion = 0, debounceTimer;
const byId = id => document.getElementById(id);
const numberText = value => Number(value).toLocaleString('vi-VN');

function addOption(select, value, label) {
    const item = node('option', label); item.value = value; select.append(item);
}
async function loadCategories() {
    const [categories, units] = await Promise.all([api('/categories/'), api('/units/')]);
    let unitOptions = byId('unitOptions');
    if (!unitOptions) {
        unitOptions = node('datalist'); unitOptions.id = 'unitOptions';
        document.body.append(unitOptions);
        byId('productEditorForm').elements.unit.setAttribute('list', 'unitOptions');
    }
    unitOptions.replaceChildren();
    units.forEach(unit => addOption(unitOptions, unit.unit_name, unit.unit_name));
    const filter = byId('categoryFilter'), editor = byId('editorCategory');
    const filterValue = filter.value, editorValue = editor.value;
    filter.replaceChildren(); editor.replaceChildren();
    addOption(filter, '', 'Tất cả nhóm'); addOption(filter, '0', 'Chưa phân nhóm');
    addOption(editor, '', 'Chưa phân nhóm');
    for (const category of categories) {
        addOption(filter, category.category_id, category.category_name);
        addOption(editor, category.category_id, category.category_name);
    }
    filter.value = filterValue; editor.value = editorValue;
}
function action(label, handler, className = 'btn-secondary') {
    const button = node('button', label, className); button.type = 'button';
    button.addEventListener('click', handler); return button;
}
async function loadProducts() {
    const version = ++requestVersion;
    const query = new URLSearchParams({q: byId('productSearch').value.trim()});
    if (byId('categoryFilter').value !== '') query.set('category_id', byId('categoryFilter').value);
    byId('reloadProducts').disabled = true;
    byId('productsBody').setAttribute('aria-busy', 'true');
    try {
        const products = await api(`/products/?${query}`);
        if (version !== requestVersion) return;
        const body = byId('productsBody'); body.replaceChildren();
        byId('productCount').textContent = `${numberText(products.length)} mặt hàng phù hợp`;
        if (!products.length) {
            const row = node('tr'), cell = node('td', 'Không có hàng hóa phù hợp. Thử bỏ bộ lọc hoặc thêm hàng hóa mới.', 'empty');
            cell.colSpan = 8; row.append(cell); body.append(row);
        }
        for (const product of products) {
            const row = node('tr'); row.dataset.id = product.product_id;
            const values = [product.product_code, product.product_name, product.category_name || 'Chưa phân nhóm', product.unit,
                numberText(product.quantity_available), numberText(product.min_stock_level)];
            values.forEach(value => row.append(node('td', value)));
            const status = node('td'); status.append(node('span', stockLabels[product.stock_status], `status ${stockClasses[product.stock_status]}`));
            const actions = node('td'); const group = node('div', undefined, 'product-actions');
            const details = action('Chi tiết', () => showDetails(product.product_id)); details.dataset.action = 'details';
            const edit = action('Sửa', () => openEditor(product.product_id)); edit.dataset.action = 'edit';
            const remove = action('Xóa', () => confirmRemoval(product), 'btn-secondary delete-action'); remove.dataset.action = 'delete';
            // Keep the reason available to keyboard users as well as mouse users.
            remove.setAttribute('aria-disabled', String(!product.can_delete));
            if (!product.can_delete) remove.title = product.deletion_reason;
            group.append(details, edit, remove); actions.append(group); row.append(status, actions); body.append(row);
        }
    } catch (error) {
        if (version === requestVersion) { message(error.message, true); byId('productCount').textContent = 'Không tải được danh sách. Hãy làm mới để thử lại.'; }
    } finally {
        if (version === requestVersion) { byId('reloadProducts').disabled = false; byId('productsBody').removeAttribute('aria-busy'); }
    }
}
async function openEditor(id = null) {
    try {
        const product = id === null ? null : await api(`/products/${id}`);
        editingId = id;
        const form = byId('productEditorForm'); form.reset();
        byId('editorError').textContent = '';
        byId('editorTitle').textContent = product ? 'Sửa hàng hóa' : 'Thêm hàng hóa';
        for (const field of ['product_code', 'product_name', 'unit', 'min_stock_level', 'category_id']) {
            if (product) form.elements[field].value = product[field] ?? '';
        }
        byId('stockHint').textContent = product ? `Tồn hiện tại: ${numberText(product.quantity_available)} ${product.unit}. Sửa thông tin không thay đổi số lượng tồn.` : 'Hàng mới có tồn bằng 0. Lập phiếu nhập để tăng tồn.';
        byId('productEditor').showModal(); form.elements.product_code.focus();
    } catch (error) { message(error.message, true); }
}
async function showDetails(id) {
    try {
        detailProduct = await api(`/products/${id}`);
        const p = detailProduct;
        const timestamp = p.last_updated ? new Date(p.last_updated.endsWith('Z') ? p.last_updated : p.last_updated + 'Z').toLocaleString('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh'}) : 'Chưa có';
        const fields = [['Mã hàng', p.product_code], ['Tên hàng', p.product_name], ['Nhóm hàng', p.category_name || 'Chưa phân nhóm'], ['Đơn vị tính', p.unit], ['Số lượng tồn', numberText(p.quantity_available)], ['Tồn tối thiểu', numberText(p.min_stock_level)], ['Trạng thái', stockLabels[p.stock_status]], ['Cập nhật tồn (giờ Việt Nam)', timestamp]];
        const content = byId('detailsContent'); content.replaceChildren();
        fields.forEach(([label, value]) => content.append(node('dt', label), node('dd', value)));
        byId('deletionNote').textContent = p.deletion_reason || 'Hàng hóa chưa sử dụng, có thể xóa.';
        byId('productDetails').showModal();
    } catch (error) { message(error.message, true); }
}
function confirmRemoval(product) {
    if (!product.can_delete) { message(product.deletion_reason, true); return; }
    deletingProduct = product;
    byId('deleteDescription').textContent = `Bạn muốn xóa ${product.product_code} — ${product.product_name}? Thao tác này xóa mặt hàng khỏi danh sách.`;
    byId('deleteError').textContent = '';
    byId('deleteProductDialog').showModal();
}
byId('productEditorForm').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget, button = byId('saveProduct'); button.disabled = true;
    const values = Object.fromEntries(new FormData(form));
    values.category_id = values.category_id ? Number(values.category_id) : null;
    values.min_stock_level = Number(values.min_stock_level);
    try {
        await api(editingId === null ? '/products/' : `/products/${editingId}`, {method: editingId === null ? 'POST' : 'PUT', body: JSON.stringify(values)});
        byId('productEditor').close(); message(editingId === null ? 'Đã thêm hàng hóa. Tồn ban đầu bằng 0.' : 'Đã cập nhật thông tin hàng hóa.');
        await loadProducts();
    } catch (error) { byId('editorError').textContent = error.message; }
    finally { button.disabled = false; }
});
byId('categoryForm').addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget, button = form.querySelector('button'); button.disabled = true;
    try {
        await api('/categories/', {method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form)))});
        form.reset(); byId('categoryEditor').close(); message('Đã thêm nhóm hàng.'); await loadCategories();
    } catch (error) { byId('categoryError').textContent = error.message; }
    finally { button.disabled = false; }
});
byId('confirmDelete').addEventListener('click', async () => {
    const button = byId('confirmDelete'); button.disabled = true;
    try {
        await api(`/products/${deletingProduct.product_id}`, {method: 'DELETE'});
        byId('deleteProductDialog').close(); message('Đã xóa hàng hóa.'); await loadProducts();
    } catch (error) { byId('deleteError').textContent = error.message; await loadProducts(); }
    finally { button.disabled = false; }
});
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => byId(button.dataset.close).close()));
byId('newProduct').addEventListener('click', () => openEditor());
byId('newCategory').addEventListener('click', () => { byId('categoryError').textContent = ''; byId('categoryEditor').showModal(); });
byId('editFromDetails').addEventListener('click', () => { byId('productDetails').close(); openEditor(detailProduct.product_id); });
byId('productFilters').addEventListener('submit', event => { event.preventDefault(); clearTimeout(debounceTimer); loadProducts(); });
byId('productSearch').addEventListener('input', () => { clearTimeout(debounceTimer); debounceTimer = setTimeout(loadProducts, 250); });
byId('categoryFilter').addEventListener('change', loadProducts);
byId('clearFilters').addEventListener('click', () => { clearTimeout(debounceTimer); byId('productFilters').reset(); loadProducts(); });
byId('reloadProducts').addEventListener('click', async () => { try { await loadCategories(); await loadProducts(); } catch (error) { message(error.message, true); } });
(async () => { try { await loadCategories(); await loadProducts(); } catch (error) { message(error.message, true); } })();
