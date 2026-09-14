const catalogPage = document.body.dataset.page;
const canManage = ['admin','thu_kho'].includes(document.body.dataset.role);
const idField = {categories:'category_id', units:'unit_id', suppliers:'supplier_id'}[catalogPage];
const nameField = {categories:'category_name', units:'unit_name', suppliers:'name'}[catalogPage];
const el = id => document.getElementById(id);
let editing = null, deleting = null, loadVersion = 0, searchTimer;
function catalogButton(label, handler) { const b=node('button',label,'btn-secondary'); b.type='button'; b.addEventListener('click',handler); return b; }
async function loadCatalog() {
    const version=++loadVersion;
    try {
        const rows=await api(`/${catalogPage}/?${new URLSearchParams({q:el('searchText').value})}`);
        if(version!==loadVersion)return;
        const headings=catalogPage==='suppliers'?['Mã nhà cung cấp','Tên nhà cung cấp','Điện thoại','Email','Địa chỉ','Thao tác']:['Tên', ...(catalogPage==='units'?['Số mặt hàng sử dụng']:[]),'Thao tác'];
        const tr=node('tr'); headings.forEach(h=>tr.append(node('th',h))); el('catalogHead').replaceChildren(tr); el('catalogBody').replaceChildren();
        el('catalogCount').textContent=`${rows.length} kết quả`;
        for(const row of rows) {
            const tr=node('tr'); tr.dataset.id=row[idField];
            const values=catalogPage==='suppliers'?[row.code,row.name,row.phone,row.email,row.address]:[row[nameField],...(catalogPage==='units'?[row.product_count]:[])];
            values.forEach(value=>tr.append(node('td',value??'—')));
            const td=node('td'), actions=node('div',undefined,'product-actions');
            if(catalogPage==='suppliers')actions.append(catalogButton('Lịch sử nhập',()=>showHistory(row)));
            if(canManage){actions.append(catalogButton('Sửa',()=>editCatalog(row)),catalogButton('Xóa',()=>{
                deleting=row; el('catalogDeleteText').textContent=`Xóa ${row[nameField]}? Dữ liệu đang được sử dụng sẽ không thể xóa.`;
                el('catalogDeleteError').textContent=''; el('catalogDelete').showModal();
            }));}
            td.append(actions);tr.append(td);el('catalogBody').append(tr);
        }
        if(!rows.length){const tr=node('tr'),td=node('td','Chưa có dữ liệu phù hợp.','empty');td.colSpan=headings.length;tr.append(td);el('catalogBody').append(tr);}
    }catch(error){if(version===loadVersion)message(error.message,true);}
}
function editCatalog(row=null){
    editing=row;const form=el('catalogForm');form.reset();
    if(row)for(const input of form.querySelectorAll('input[name]'))input.value=row[input.name]??'';
    el('catalogTitle').textContent=row?'Sửa thông tin':'Thêm mới';el('catalogError').textContent='';el('catalogDialog').showModal();form.querySelector('input').focus();
}
el('catalogAdd')?.addEventListener('click',()=>editCatalog());
el('catalogForm')?.addEventListener('submit',async event=>{
    event.preventDefault();const button=event.currentTarget.querySelector('[type=submit]');button.disabled=true;
    try{
        const payload=Object.fromEntries(new FormData(event.currentTarget));
        await api(editing?`/${catalogPage}/${editing[idField]}`:`/${catalogPage}/`,{method:editing?'PUT':'POST',body:JSON.stringify(payload)});
        el('catalogDialog').close();message('Đã lưu thành công.');await loadCatalog();
    }catch(error){el('catalogError').textContent=error.message;}finally{button.disabled=false;}
});
el('catalogConfirmDelete')?.addEventListener('click',async()=>{
    const button=el('catalogConfirmDelete');button.disabled=true;
    try{await api(`/${catalogPage}/${deleting[idField]}`,{method:'DELETE'});el('catalogDelete').close();message('Đã xóa.');await loadCatalog();}
    catch(error){el('catalogDeleteError').textContent=error.message;}finally{button.disabled=false;}
});
async function showHistory(supplier){
    el('historyTitle').textContent=`Lịch sử nhập · ${supplier.name}`;el('historyContent').replaceChildren();el('historySummary').textContent='Đang tải…';el('historyDialog').showModal();
    try{
        const [receipts,products]=await Promise.all([api(`/suppliers/${supplier.supplier_id}/receipts`),api('/products/')]);
        const names=new Map(products.map(p=>[p.product_id,`${p.product_code} · ${p.product_name}`]));
        el('historySummary').textContent=receipts.length?`${receipts.length} phiếu nhập. Mở từng phiếu để xem hàng hóa.`:'Nhà cung cấp chưa có phiếu nhập.';
        for(const receipt of receipts){
            const details=node('details',undefined,'panel section-gap');
            const date=receipt.receipt_date?new Date(receipt.receipt_date+'Z').toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'Chưa có ngày';
            const statuses={confirmed:'Đã xác nhận',draft:'Nháp',cancelled:'Đã hủy'};
            details.append(node('summary',`${receipt.receipt_no} · ${date} · ${statuses[receipt.status]||receipt.status}`));
            const table=node('table');const header=node('tr');['Hàng hóa','Số lượng','Đơn giá'].forEach(label=>header.append(node('th',label)));const thead=node('thead');thead.append(header);table.append(thead);
            const body=node('tbody');for(const item of receipt.items){const tr=node('tr');[names.get(item.product_id)||item.product_id,item.quantity,item.unit_price===null?'Chưa nhập':Number(item.unit_price).toLocaleString('vi-VN')].forEach(value=>tr.append(node('td',value)));body.append(tr);}table.append(body);
            const wrapper=node('div',undefined,'table-wrapper');wrapper.append(table);details.append(wrapper);el('historyContent').append(details);
        }
    }catch(error){el('historySummary').textContent=error.message;}
}
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>el(button.dataset.close).close()));
el('catalogSearch').addEventListener('submit',event=>{event.preventDefault();clearTimeout(searchTimer);loadCatalog();});
el('searchText').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(loadCatalog,250);});
el('catalogReset').addEventListener('click',()=>{clearTimeout(searchTimer);el('searchText').value='';loadCatalog();});
loadCatalog();
