(() => {
    const el = id => document.getElementById(id);
    const isAdmin = document.body.dataset.role === 'admin';
    const labels = {pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Từ chối'};
    const number = value => Number(value).toLocaleString('vi-VN');
    const stamp = value => value ? new Date(value.endsWith('Z') ? value : value + 'Z').toLocaleString('vi-VN') : '—';
    const money = value => value == null ? 'Chưa có giá' : `${number(value)} ₫`;
    let catalog = [], requests = [], reviewing = null, submitting = false;
    function addLine() {
        if (el('requestLines').children.length >= 100) return;
        const row = node('div', undefined, 'request-line');
        const label = node('label', 'Hàng hóa'), select = node('select'); select.required = true;
        const blank = node('option', 'Chọn hàng hóa'); blank.value = ''; select.append(blank);
        catalog.forEach(p => { const opt = node('option', `${p.product_code} · ${p.product_name} (${p.unit})`); opt.value = p.product_id; select.append(opt); });
        label.append(select);
        const qtyLabel = node('label', 'Số lượng'), qty = node('input'); qty.type = 'number'; qty.min = '1'; qty.max = '1000000000'; qty.step = '1'; qty.value = '1'; qty.required = true; qtyLabel.append(qty);
        const remove = node('button', 'Xóa dòng', 'btn-secondary'); remove.type = 'button'; remove.addEventListener('click', () => row.remove());
        row.append(label, qtyLabel, remove); el('requestLines').append(row);
    }
    function received() {
        const totals = new Map();
        for (const r of requests.filter(r => r.status === 'approved' && r.issue)) {
            for (const item of r.issue.items) {
                const p = r.items.find(p => p.product_id === item.product_id);
                if (!totals.has(item.product_id)) totals.set(item.product_id, {...p, quantity: 0});
                totals.get(item.product_id).quantity += item.quantity;
            }
        }
        const body = el('receivedBody'); body.replaceChildren();
        for (const p of totals.values()) { const row = node('tr'); [p.product_code, p.product_name, p.unit, number(p.quantity)].forEach(v => row.append(node('td', v))); body.append(row); }
        if (!totals.size) { const row = node('tr'), cell = node('td', 'Chưa có hàng được xuất từ yêu cầu đã duyệt.', 'empty'); cell.colSpan = 4; row.append(cell); body.append(row); }
    }
    function render() {
        for (const status of Object.keys(labels)) el(`${status}Count`).textContent = number(requests.filter(r => r.status === status).length);
        if (!isAdmin) received();
        const box = el('requestsList'); box.replaceChildren();
        const rows = requests.filter(r => !el('requestFilter').value || r.status === el('requestFilter').value);
        for (const r of rows) {
            const card = node('article', undefined, 'request-card'), header = node('header');
            header.append(node('strong', `YC${r.id}${isAdmin ? ' · ' + r.partner_name : ''}`), node('span', labels[r.status], `request-status ${r.status}`));
            card.append(header, node('p', `Gửi lúc ${stamp(r.created_at)}`, 'muted'));
            const list = node('ul'); r.items.forEach(i => list.append(node('li', `${i.product_code} · ${i.product_name}: ${number(i.quantity)} ${i.unit}`))); card.append(list);
            if (r.note) card.append(node('p', `Ghi chú: ${r.note}`));
            if (r.reviewed_at) card.append(node('p', `${r.reviewed_by} · ${stamp(r.reviewed_at)}`, 'muted'));
            if (r.review_note) card.append(node('p', `Phản hồi: ${r.review_note}`));
            if (r.issue) {
                const details = node('details'), lines = node('ul');
                details.append(node('summary', `Phiếu ${r.issue.issue_no} · ${r.issue.total_amount == null ? 'Chưa đủ giá' : money(r.issue.total_amount)}`));
                r.issue.items.forEach(i => { const p = r.items.find(p => p.product_id === i.product_id); lines.append(node('li', `${p.product_name}: ${number(i.quantity)} ${p.unit} × ${money(i.unit_price)} = ${money(i.line_total)}`)); });
                details.append(lines); card.append(details);
            }
            if (isAdmin && r.status === 'pending') {
                const button = node('button', 'Xét duyệt', 'primary'); button.type = 'button'; button.addEventListener('click', () => openReview(r.id)); card.append(button);
            }
            box.append(card);
        }
        if (!rows.length) box.append(node('p', 'Không có yêu cầu trong trạng thái này.', 'empty'));
    }
    async function load() {
        el('refreshRequests').disabled = true;
        try { requests = await api('/partner-requests/'); render(); }
        catch (error) { message(error.message, true); }
        finally { el('refreshRequests').disabled = false; }
    }
    async function openReview(id) {
        if (submitting) return;
        try {
            const [r, products] = await Promise.all([api(`/partner-requests/${id}`), api('/products/')]);
            if (r.status !== 'pending') { await load(); throw Error('Yêu cầu này đã được xét duyệt.'); }
            reviewing = id; el('reviewTitle').textContent = `YC${id} · ${r.partner_name}`;
            const box = el('reviewItems'); box.replaceChildren();
            box.append(node('p', 'Duyệt sẽ xuất toàn bộ số lượng bên dưới, theo giá xuất mặc định tại thời điểm duyệt.', 'muted'));
            const list = node('ul');
            r.items.forEach(i => { const p = products.find(p => p.product_id === i.product_id); list.append(node('li', `${i.product_name}: yêu cầu ${number(i.quantity)} ${i.unit} · Tồn ${number(p?.quantity_available ?? 0)} · Giá ${money(p?.sale_price)}`)); });
            box.append(list); if (r.note) box.append(node('p', `Ghi chú: ${r.note}`));
            el('reviewForm').reset(); el('reviewError').textContent = ''; el('reviewDialog').showModal();
        } catch (error) { message(error.message, true); }
    }
    el('partnerRequestForm')?.addEventListener('submit', async event => {
        event.preventDefault(); if (submitting) return;
        const items = [...el('requestLines').children].map(row => ({product_id: Number(row.querySelector('select').value), quantity: Number(row.querySelector('input').value)}));
        if (!items.length) { el('requestError').textContent = 'Thêm ít nhất một dòng hàng.'; return; }
        submitting = true; el('submitRequest').disabled = true; el('requestError').textContent = '';
        try { await api('/partner-requests/', {method: 'POST', body: JSON.stringify({items, note: el('requestNote').value.trim() || null})}); el('partnerRequestForm').reset(); el('requestLines').replaceChildren(); addLine(); message('Đã gửi yêu cầu. Vui lòng chờ quản trị viên xét duyệt.'); await load(); }
        catch (error) { el('requestError').textContent = error.message; }
        finally { submitting = false; el('submitRequest').disabled = false; }
    });
    el('reviewForm')?.addEventListener('submit', async event => {
        event.preventDefault(); if (submitting) return;
        const decision = event.submitter?.value; if (!decision) return;
        const note = el('reviewNote').value.trim();
        if (decision === 'reject' && !note) { el('reviewError').textContent = 'Vui lòng nhập lý do từ chối.'; el('reviewNote').focus(); return; }
        submitting = true; el('approveRequest').disabled = el('rejectRequest').disabled = true;
        try { await api(`/partner-requests/${reviewing}/review`, {method: 'POST', body: JSON.stringify({decision, note: note || null})}); el('reviewDialog').close(); message(decision === 'approve' ? 'Đã duyệt, tạo phiếu xuất và cập nhật tồn kho.' : 'Đã từ chối yêu cầu.'); await load(); }
        catch (error) { el('reviewError').textContent = error.message; }
        finally { submitting = false; el('approveRequest').disabled = el('rejectRequest').disabled = false; }
    });
    el('closeReview')?.addEventListener('click', () => { if (!submitting) el('reviewDialog').close(); });
    el('reviewDialog')?.addEventListener('cancel', event => { if (submitting) event.preventDefault(); });
    el('addRequestLine')?.addEventListener('click', addLine);
    el('requestFilter').addEventListener('change', render);
    el('refreshRequests').addEventListener('click', load);
    (async () => { try { if (!isAdmin) { catalog = await api('/partner-requests/products'); addLine(); } await load(); } catch (error) { message(error.message, true); } })();
})();
