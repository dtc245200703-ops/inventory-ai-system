const formatNumber = value => Number(value).toLocaleString('vi-VN');
function stockList(id, rows, stale = false) {
    const box = document.getElementById(id);
    box.replaceChildren();
    if (!rows.length) { box.append(node('p', 'Không có mặt hàng trong danh sách này.', 'empty')); return; }
    for (const item of rows) {
        const card = node('div', undefined, 'warning-item');
        card.append(node('strong', `${item.product_code} · ${item.product_name}`));
        card.append(node('span', stale ? `Tồn ${formatNumber(item.quantity_available)} ${item.unit} · ${item.inactive_days} ngày không xuất`
            : `Tồn ${formatNumber(item.quantity_available)} ${item.unit} · Tối thiểu ${formatNumber(item.min_stock_level)}`));
        box.append(card);
    }
}
function renderChart(series) {
    const box = document.getElementById('movementChart');
    const table = document.getElementById('chartTable');
    box.replaceChildren(); table.replaceChildren();
    const maximum = Math.max(1, ...series.flatMap(row => [row.import, row.export]));
    for (const row of series) {
        const group = node('div', undefined, 'chart-group');
        const bars = node('div', undefined, 'bars');
        for (const type of ['import', 'export']) {
            const bar = node('div', undefined, `bar ${type}`);
            bar.style.height = `${Math.max(0, row[type]) / maximum * 160}px`;
            bar.title = `${row.label}: ${type === 'import' ? 'Nhập' : 'Xuất'} ${formatNumber(row[type])}`;
            bars.append(bar);
        }
        group.append(bars, node('span', row.label.length === 10 ? row.label.slice(8) : row.label.slice(2)));
        box.append(group);
        const tr = node('tr');
        tr.append(node('td', row.label), node('td', formatNumber(row.import)), node('td', formatNumber(row.export)));
        table.append(tr);
    }
}
async function loadDashboard() {
    const button = document.getElementById('refresh');
    const period = document.getElementById('period');
    button.disabled = true; period.disabled = true;
    try {
        const data = await api(`/dashboard/summary?period=${period.value}`);
        for (const [key, value] of Object.entries(data.summary)) document.getElementById(key).textContent = formatNumber(value);
        stockList('lowStockList', data.low_stock_products);
        stockList('staleStockList', data.stale_products, true);
        document.getElementById('unknownAge').textContent = data.unknown_age_products ? `${data.unknown_age_products} mặt hàng còn tồn chưa đủ lịch sử để xác định tuổi tồn.` : '';
        renderChart(data.series);
        const top = document.getElementById('topProducts'); top.replaceChildren();
        if (!data.top_products.length) top.append(node('p', 'Chưa có xuất kho trong kỳ.', 'empty'));
        for (const item of data.top_products) {
            const row = node('div', undefined, 'rank-row');
            const text = node('p'); text.append(node('span', item.product_name), node('strong', formatNumber(item.export_quantity)));
            const progress = node('progress'); progress.max = data.top_products[0].export_quantity; progress.value = item.export_quantity;
            progress.setAttribute('aria-label', `${item.product_name}: ${item.export_quantity}`);
            row.append(text, progress); top.append(row);
        }
        document.getElementById('updatedAt').textContent = `Cập nhật ${new Date(data.generated_at).toLocaleString('vi-VN')}`;
        message('');
    } catch (error) { message(`Không tải được thống kê: ${error.message}`, true); }
    finally { button.disabled = false; period.disabled = false; }
}
document.getElementById('period').addEventListener('change', loadDashboard);
document.getElementById('refresh').addEventListener('click', loadDashboard);
loadDashboard();
