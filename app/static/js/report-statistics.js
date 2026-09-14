const reportNumber = value => Number(value).toLocaleString('vi-VN');
const reportEl = id => document.getElementById(id);
const reportItem = text => node('p', text, 'section-gap');

async function loadReport() {
    const period = reportEl('reportPeriod').value, selected = reportEl('reportDate').value;
    const query = new URLSearchParams({period, selected});
    try {
        const data = await api(`/reports/?${query}`);
        for (const key of ['opening','import','export','closing']) reportEl(`report-${key}`).textContent = reportNumber(data.summary[key]);
        const body = reportEl('reportRows'); body.replaceChildren();
        for (const item of data.products) {
            const row = node('tr');
            [item.product_code,item.product_name,item.opening,item.import,item.export,item.closing].forEach(value => row.append(node('td',typeof value==='number'?reportNumber(value):value)));
            body.append(row);
        }
        const highlights=reportEl('reportHighlights'); highlights.replaceChildren(
            reportItem(data.most_exported?`Xuất nhiều nhất: ${data.most_exported.product_code} · ${data.most_exported.product_name} (${reportNumber(data.most_exported.export)})`:'Chưa có xuất kho trong kỳ.'),
            reportItem(data.least_exported?`Xuất ít nhất: ${data.least_exported.product_code} · ${data.least_exported.product_name} (${reportNumber(data.least_exported.export)})`:'Chưa có sản phẩm.'),
            reportItem(`Hàng tồn lâu: ${data.stale_products.length} mặt hàng`));
        const low=reportEl('reportLowStock'); low.replaceChildren();
        for(const item of data.low_stock_products) low.append(reportItem(`${item.product_code} · ${item.product_name}: tồn ${reportNumber(item.closing)}, tối thiểu ${reportNumber(item.min_stock_level)}`));
        if(!data.low_stock_products.length) low.append(reportItem('Không có hàng dưới mức tối thiểu.'));
        reportEl('excelExport').href=`/reports/export.xls?${query}`;
        reportEl('pdfExport').href=`/reports/export.pdf?${query}`;
    } catch(error) { message(error.message,true); }
}
reportEl('reportDate').value=new Date().toISOString().slice(0,10);
const now=new Date();
for(let month=1;month<=12;month++) reportEl('aiMonth').append(Object.assign(document.createElement('option'),{value:month,textContent:String(month).padStart(2,'0')}));
reportEl('aiMonth').value=now.getMonth()+1; reportEl('aiYear').value=now.getFullYear();
function updateAiPeriod(){document.querySelector('[data-ai^="/ai/inventory-report"]').dataset.ai=`/ai/inventory-report?month=${reportEl('aiMonth').value}&year=${reportEl('aiYear').value}`;}
reportEl('aiMonth').addEventListener('change',updateAiPeriod); reportEl('aiYear').addEventListener('input',updateAiPeriod); updateAiPeriod();
reportEl('reportFilters').addEventListener('submit',event=>{event.preventDefault();loadReport();});
loadReport();
