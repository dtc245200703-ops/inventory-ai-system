"""Run partner and administrator UI workflows in Chrome with isolated fixtures."""
import browser_widget_smoke as runner
from jinja2 import Environment as JinjaEnvironment

MOCK = r"""
window.calls = [];
const fixtureItem = {product_id:1, product_code:'IP15', product_name:'iPhone 15', unit:'Cái', quantity:3};
let fixtureRows = [{id:1, partner_name:'Đối tác An Phát', status:'pending', note:'Giao trong tuần', created_at:'2026-09-15T08:00:00', items:[fixtureItem], issue:null}];
window.fetch = async (url, options = {}) => {
  let data;
  if (url === '/auth/me') data = {id:2, role:document.body.dataset.role, csrf_token:'fixture'};
  else if (url === '/partner-requests/products') data = [fixtureItem];
  else if (url === '/products/') data = [{...fixtureItem, quantity_available:10, sale_price:'100000.00'}];
  else if (url === '/partner-requests/' && options.method === 'POST') {
    const body = JSON.parse(options.body); window.calls.push(body);
    data = {id:2, partner_name:'Đối tác An Phát', status:'pending', created_at:'2026-09-15T09:00:00', note:body.note, items:[{...fixtureItem, quantity:body.items[0].quantity}], issue:null}; fixtureRows.unshift(data);
  } else if (url === '/partner-requests/') data = fixtureRows;
  else if (url === '/partner-requests/1') data = fixtureRows.find(r=>r.id===1);
  else if (url === '/partner-requests/1/review') {
    const body = JSON.parse(options.body); window.calls.push(body);
    const r = fixtureRows.find(r=>r.id===1); r.status = body.decision === 'approve' ? 'approved' : 'rejected'; r.review_note = body.note; r.reviewed_by='Quản trị viên'; r.reviewed_at='2026-09-15T10:00:00';
    if (body.decision === 'approve') r.issue = {issue_no:'PX0001', total_amount:'300000.00', items:[{product_id:1, quantity:3, unit_price:'100000.00', line_total:'300000.00'}]};
    data = r;
  } else throw Error('Unexpected fetch: ' + url);
  return {ok:true, status:200, json:async()=>data};
};
"""

CHECK = r"""
(async () => {
 const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)), el=id=>document.getElementById(id);
 const check=(ok,label)=>{if(!ok)throw Error(label);};
 try {
   await wait(120); check(el('pendingCount').textContent==='1','initial pending count');
   if(document.body.dataset.role==='nhan_hang') {
     check(!el('aiChatToggle'),'no internal AI exposure');
     check(!el('reviewForm'),'no review controls');
     const row=el('requestLines').firstElementChild;
     row.querySelector('select').value='1'; row.querySelector('input').value='5';
     el('requestNote').value='Xin thêm hàng'; el('partnerRequestForm').requestSubmit();
     await wait(120); check(window.calls.length===1 && window.calls[0].items[0].quantity===5,'submitted requested quantity');
     check(el('pendingCount').textContent==='2','new pending request');
     check(el('requestLines').children.length===1 && !el('requestNote').value,'form reset');
     check(el('receivedBody').textContent.includes('Chưa có hàng'),'pending has no received stock');
   } else {
     el('requestsList').querySelector('button').click(); await wait(120);
     check(el('reviewDialog').open,'review modal opened');
     check(el('reviewItems').textContent.includes('Tồn 10'),'stock review');
     el('rejectRequest').click(); await wait(30);
     check(window.calls.length===0 && el('reviewError').textContent,'rejection requires note');
     el('reviewNote').value='Đồng ý xuất'; el('approveRequest').click(); await wait(120);
     check(window.calls.length===1 && window.calls[0].decision==='approve','admin approval');
     check(el('approvedCount').textContent==='1' && !el('reviewDialog').open,'approved state refreshed');
     check(el('requestsList').textContent.includes('PX0001'),'issue visible');
   }
   check(document.documentElement.scrollWidth<=innerWidth,'no horizontal overflow');
   document.body.dataset.smoke='passed';
 } catch(error) {document.body.dataset.smoke='failed: '+error.message;}
})();
"""


def run(role):
    class Environment:
        def __init__(self, *args, **kwargs):
            self.env = JinjaEnvironment(*args, **kwargs)

        def get_template(self, _):
            template = self.env.get_template('partner.html')
            class Template:
                def render(self, **kwargs):
                    return template.render(user={'username': 'Đối tác An Phát' if role == 'nhan_hang' else 'Quản trị viên', 'role': role},
                        role_label='Nhãn hàng / Đối tác' if role == 'nhan_hang' else 'Quản trị viên',
                        page='partner' if role == 'nhan_hang' else 'requests',
                        title='Hàng đã nhận và yêu cầu' if role == 'nhan_hang' else 'Duyệt yêu cầu nhãn hàng')
            return Template()
    runner.Environment = Environment
    runner.MOCK, runner.CHECK = MOCK, CHECK
    print(role, flush=True)
    runner.main()


if __name__ == '__main__':
    run('nhan_hang')
    run('admin')
