const inv = id => document.getElementById(id);
let inventoryVersion = 0;
async function loadInventoryBrands() {
    const brands = await api('/brands/'), select = inv('inventoryBrand'), previous = select.value;
    select.replaceChildren();
    for (const [value, label] of [['', 'Tất cả nhãn hàng'], ['0', 'Chưa gán nhãn'], ...brands.map(b => [b.brand_id, b.brand_name])]) {
        const option = node('option', label); option.value = value; select.append(option);
    }
    select.value = previous;
}
function inventoryAction(label, handler) { const button=node('button',label,'btn-secondary'); button.type='button'; button.addEventListener('click',handler); return button; }
function inventoryStatus(product) {
    if (product.quantity_available < product.min_stock_level) return ['⚠ Sắp hết', 'stock-critical'];
    if (product.quantity_available === product.min_stock_level) return ['⚠ Sắp hết', 'stock-warning'];
    return ['✅ Bình thường', 'stock-normal'];
}
async function loadInventory() {
    const version = ++inventoryVersion;
    try {
        const params = new URLSearchParams({q: inv('inventorySearch').value.trim()});
        if (inv('inventoryBrand').value !== '') params.set('brand_id', inv('inventoryBrand').value);
        const products=await api(`/products/?${params}`), body=inv('inventoryBody');
        if (version !== inventoryVersion) return;
        body.replaceChildren();
        for(const product of products){
            const row=node('tr'), [label,className]=inventoryStatus(product); row.classList.add(className);
            [product.product_code,product.product_name,product.brand_name || 'Chưa gán nhãn',product.quantity_available,product.min_stock_level].forEach(value=>row.append(node('td',value)));
            const status=node('td'); status.append(node('span',label,`status ${className}`)); row.append(status);
            const actions=node('td'), group=node('div',undefined,'product-actions'); group.append(inventoryAction('Kiểm kê / Điều chỉnh',()=>openAdjustment(product)),inventoryAction('Xem thẻ kho',()=>openCard(product))); actions.append(group); row.append(actions); body.append(row);
        }
        if(!products.length){const row=node('tr'),cell=node('td','Không có hàng hóa phù hợp với bộ lọc.','empty');cell.colSpan=7;row.append(cell);body.append(row);}
    } catch(error){message(error.message,true);}
}
function openAdjustment(product){const form=inv('adjustForm');form.elements.product_id.value=product.product_id;form.elements.quantity_available.value=product.quantity_available;inv('adjustProduct').textContent=`${product.product_code} · ${product.product_name} — tồn hệ thống: ${product.quantity_available}`;inv('adjustDialog').showModal();form.elements.quantity_available.focus();}
async function openCard(product){inv('cardTitle').textContent=`Thẻ kho · ${product.product_code} · ${product.product_name}`;const body=inv('cardBody');body.replaceChildren();inv('cardDialog').showModal();try{const rows=await api(`/inventory/card/${product.product_id}`);for(const item of rows){const row=node('tr'),type={import:'Nhập kho',export:'Xuất kho',adjustment:'Điều chỉnh'}[item.type]||item.type,sign=item.type==='export'?'-':item.type==='import'?'+':'±';[new Date(item.created_at+(item.created_at.endsWith('Z')?'':'Z')).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}),type,`${sign}${item.quantity}`,item.balance_after,item.ref_id||'Kiểm kê'].forEach(value=>row.append(node('td',value)));body.append(row);}if(!rows.length){const row=node('tr'),cell=node('td','Chưa có biến động kho.','empty');cell.colSpan=5;row.append(cell);body.append(row);}}catch(error){message(error.message,true);}}
inv('adjustForm').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type=submit]');button.disabled=true;try{await api(`/inventory/${form.elements.product_id.value}`,{method:'PUT',body:JSON.stringify({quantity_available:Number(form.elements.quantity_available.value)})});inv('adjustDialog').close();message('Đã lưu kiểm kê và ghi thẻ kho.');await loadInventory();}catch(error){message(error.message,true);}finally{button.disabled=false;}});
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>inv(button.dataset.close).close()));
inv('inventoryFilters').addEventListener('submit', event => { event.preventDefault(); loadInventory(); });
inv('inventoryBrand').addEventListener('change', loadInventory);
inv('clearInventoryFilters').addEventListener('click', () => { inv('inventoryFilters').reset(); loadInventory(); });
async function refreshInventory() {
    try { await loadInventoryBrands(); await loadInventory(); } catch(error) { message(error.message, true); }
}
inv('reloadInventory').addEventListener('click',refreshInventory);
refreshInventory();
