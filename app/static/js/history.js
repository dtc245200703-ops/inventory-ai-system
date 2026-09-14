const historyEl = id => document.getElementById(id);
const historyOption = (value, label) => { const item=node('option',label); item.value=value; return item; };

async function loadHistoryFilters() {
    const data=await api('/history/filters');
    for(const item of data.products) historyEl('historyProduct').append(historyOption(item.id,`${item.code} · ${item.name}`));
    for(const item of data.suppliers) historyEl('historySupplier').append(historyOption(item.id,`${item.code} · ${item.name}`));
    for(const item of data.users) historyEl('historyUser').append(historyOption(item.id,item.full_name?`${item.username} · ${item.full_name}`:item.username));
}
async function loadHistory() {
    const query=new URLSearchParams();
    for(const [id,key] of [['historyFrom','from_date'],['historyTo','to_date'],['historyProduct','product_id'],['historySupplier','supplier_id'],['historyType','movement_type'],['historyUser','user_id']]) {
        const value=historyEl(id).value; if(value) query.set(key,value);
    }
    const body=historyEl('historyRows'); body.setAttribute('aria-busy','true');
    try {
        const rows=await api(`/history/?${query}`); body.replaceChildren(); historyEl('historyCount').textContent=`${rows.length.toLocaleString('vi-VN')} giao dịch`;
        for(const item of rows){const row=node('tr');const stamp=new Date(item.created_at+(item.created_at.endsWith('Z')?'':'Z')).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'});const type=item.type==='import'?'Nhập':'Xuất';[stamp,type,item.document_no,item.product_code,item.product_name,item.quantity,item.balance_after,item.supplier_name||'—',item.full_name||item.username].forEach(value=>row.append(node('td',value)));body.append(row);}
        if(!rows.length){const row=node('tr'),cell=node('td','Không có giao dịch phù hợp.','empty');cell.colSpan=9;row.append(cell);body.append(row);}
    } catch(error){message(error.message,true);} finally{body.removeAttribute('aria-busy');}
}
historyEl('historyFilters').addEventListener('submit',event=>{event.preventDefault();loadHistory();});
historyEl('clearHistory').addEventListener('click',()=>{historyEl('historyFilters').reset();loadHistory();});
historyEl('reloadHistory').addEventListener('click',loadHistory);
(async()=>{try{await loadHistoryFilters();await loadHistory();}catch(error){message(error.message,true);}})();
