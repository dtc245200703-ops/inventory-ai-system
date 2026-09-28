"""Optional local Chrome smoke check; uses fixture data, never calls Gemini."""
from pathlib import Path
from tempfile import mkdtemp
import re
import subprocess
import base64
import json
import time
from websockets.sync.client import connect

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')

MOCK = r"""
window.fixtureRequests = [];
window.fetch = async (url, options = {}) => {
  let data;
  if (url === '/auth/me') data = {id: 1, csrf_token: 'fixture', role: 'admin'};
  else if (url.startsWith('/brands/')) data = [{brand_id: 1, brand_name: 'Apple'}, {brand_id: 2, brand_name: 'Samsung'}];
  else if (url.startsWith('/products/')) {
    data = [{product_id: 1, product_code: 'IP15', product_name: 'iPhone 15', brand_id: 1, brand_name: 'Apple', quantity_available: 24, min_stock_level: 10},
      {product_id: 2, product_code: 'SG24', product_name: 'Samsung Galaxy S24', brand_id: 2, brand_name: 'Samsung', quantity_available: 6, min_stock_level: 10}];
    const brand = new URL(url, 'http://fixture').searchParams.get('brand_id');
    if (brand) data = data.filter(p => p.brand_id === Number(brand));
  } else if (url === '/ai/chat') {
    window.fixtureRequests.push(JSON.parse(options.body));
    data = await new Promise(resolve => { window.finishChat = result => resolve({result}); });
  } else throw Error('Unexpected URL: ' + url);
  return {ok: true, status: 200, json: async () => data};
};
"""

CHECK = r"""
(async () => {
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const check = (condition, label) => { if (!condition) throw Error(label); };
  const el = id => document.getElementById(id);
  try {
    await wait(100);
    check(el('inventoryBody').children.length === 2, 'inventory loaded');
    el('inventoryBrand').value = '1'; el('inventoryBrand').dispatchEvent(new Event('change'));
    await wait(100);
    check(el('inventoryBody').children.length === 1, 'brand filter');
    check(el('ai').hidden, 'drawer starts closed');
    el('aiChatToggle').click();
    check(!el('ai').hidden && document.activeElement === el('aiChatInput'), 'open and focus');
    el('aiChatInput').value = 'Apple còn những hàng gì?'; el('aiChatForm').requestSubmit();
    await wait(100);
    check(window.fixtureRequests.length === 1 && el('aiChatSend').disabled, 'send and loading');
    check(getComputedStyle(el('aiChatSend').querySelector('.ai-chat-spinner')).display !== 'none', 'send button spinner visible');
    check(el('aiChatStatus').querySelectorAll('.ai-chat-thinking-dots span').length === 3, 'animated status dots');
    el('aiChatForm').dispatchEvent(new Event('submit', {cancelable: true}));
    check(window.fixtureRequests.length === 1, 'no duplicate send');
    el('aiChatClose').click();
    window.finishChat('**Apple**\n- iPhone 15: 24 cái\n<img src=x onerror="window.fixtureXSS=true">'.replaceAll('\\n', '\n'));
    await wait(100);
    check(el('ai').hidden && document.activeElement === el('aiChatToggle'), 'closed response does not steal focus');
    check(el('aiChatToggle').hasAttribute('data-unread'), 'unread response');
    check(!el('aiChatSend').classList.contains('is-thinking') && !el('aiChatStatus').textContent, 'loading removed after response');
    el('aiChatToggle').click();
    check(!el('aiChatMessages').querySelector('img') && !window.fixtureXSS, 'safe rendering');
    check(el('aiChatMessages').querySelector('.ai-chat-body strong'), 'bold rendered');
    el('aiChatInput').dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true}));
    check(el('ai').hidden, 'escape closes');
    el('aiChatToggle').click();
    el('aiChatClear').click();
    check(!el('aiChatWelcome').hidden && !el('aiChatMessages').querySelector('.ai-chat-message'), 'new conversation');
    el('aiChatInput').value = 'Apple còn những hàng gì?'; el('aiChatForm').requestSubmit();
    await wait(100);
    check(window.fixtureRequests[1].history.length === 0, 'history reset');
    window.finishChat('Kho hiện có **1 mặt hàng Apple**:\n- **iPhone 15** (IP15): còn **24 cái**.\n- Mức tồn tối thiểu: **10 cái**.\nSố tồn đang trên mức tối thiểu. Bạn muốn xem thêm lịch sử xuất hàng không?'.replaceAll('\\n', '\n'));
    await wait(100);
    const rect = el('ai').getBoundingClientRect();
    check(rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight, 'drawer fits viewport');
    check(el('aiChatSend').getBoundingClientRect().bottom <= rect.bottom, 'composer visible');
    document.body.dataset.smoke = 'passed';
  } catch (error) { document.body.dataset.smoke = 'failed: ' + error.message; }
})();
"""


def main():
    output = Path(mkdtemp(prefix='inventory-chat-ui-'))
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())
    html = env.get_template('inventory.html').render(user={'username': 'Quản trị viên', 'role': 'admin'},
            role_label='Quản trị viên', page='inventory', title='Tồn kho')
    def css(match):
        path = ROOT / 'app' / match[1].split('?')[0].lstrip('/')
        content = path.read_text(encoding='utf-8')
        content = content.replace("'/static/", "'" + (ROOT / 'app/static').as_uri() + '/')
        return '<style>' + content + '</style>'
    html = re.sub(r'<link rel="stylesheet" href="([^"]+)">', css, html)
    html = re.sub(r'<script src="([^"]+)"></script>',
        lambda m: '<script>' + (ROOT / 'app' / m[1].split('?')[0].lstrip('/')).read_text(encoding='utf-8') + '</script>', html)
    html = html.replace('</head>', '<script>' + MOCK + '</script></head>')
    html = html.replace('</body>', '<script>' + CHECK + '</script></body>')
    page = output / 'fixture.html'
    page.write_text(html, encoding='utf-8')
    profile = output / 'browser'
    process = subprocess.Popen([str(CHROME), '--headless', '--disable-gpu', '--no-first-run',
        '--no-default-browser-check', '--disable-background-networking', '--hide-scrollbars',
        f'--user-data-dir={profile}', '--remote-debugging-port=0', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        port_file = profile / 'DevToolsActivePort'
        deadline = time.monotonic() + 15
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        port, path = port_file.read_text().splitlines()[:2]
        with connect(f'ws://127.0.0.1:{port}{path}') as socket:
            sequence = 0
            def call(method, params=None, session=None):
                nonlocal sequence
                sequence += 1
                request = {'id': sequence, 'method': method, 'params': params or {}}
                if session:
                    request['sessionId'] = session
                socket.send(json.dumps(request))
                while True:
                    result = json.loads(socket.recv(timeout=15))
                    if result.get('id') == sequence:
                        assert 'error' not in result, result
                        return result.get('result', {})
            for label, width, height in [('desktop', 1366, 900), ('mobile', 390, 844)]:
                target = call('Target.createTarget', {'url': 'about:blank'})['targetId']
                session = call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
                call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height,
                     'deviceScaleFactor': 1, 'mobile': label == 'mobile'}, session)
                call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]}, session)
                call('Page.navigate', {'url': page.as_uri()}, session)
                deadline = time.monotonic() + 15
                status = None
                while time.monotonic() < deadline:
                    status = call('Runtime.evaluate', {'expression': 'document.body?.dataset.smoke', 'returnByValue': True}, session).get('result', {}).get('value')
                    if status:
                        break
                    time.sleep(.1)
                assert status == 'passed', status
                screenshot = output / f'{label}.png'
                shot = call('Page.captureScreenshot', {'format': 'png'}, session)
                screenshot.write_bytes(base64.b64decode(shot['data']))
                print(label, status, screenshot, flush=True)
                call('Target.closeTarget', {'targetId': target})
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
