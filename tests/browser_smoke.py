"""Optional Chrome/CDP smoke check with a temporary database and browser profile."""
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_http(url):
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.load(response)
        except Exception:
            time.sleep(.1)
    raise RuntimeError(f'Server not ready: {url}')


def main():
    browser = os.environ.get('CHROME_PATH', r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    with tempfile.TemporaryDirectory(prefix='inventory-ui-') as temp:
        os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(temp) / 'demo.db').as_posix()
        os.environ['SESSION_COOKIE_SECURE'] = 'false'
        from seed_demo import main as seed
        from app.database import engine, SessionLocal
        from app.routers.users import AccountCreate, add_account
        seed()
        password = secrets.token_urlsafe(18)
        with SessionLocal() as db:
            for role in ('thu_kho', 'ke_toan'):
                add_account(db, AccountCreate(username=role, password=password, role=role))
        engine.dispose()
        server_port, debug_port = port(), port()
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(server_port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        chrome = None
        try:
            base = f'http://127.0.0.1:{server_port}'
            wait_http(base + '/openapi.json')
            chrome = subprocess.Popen([browser, '--headless=new', '--disable-gpu', '--no-first-run',
                '--no-default-browser-check', f'--user-data-dir={temp}/profile',
                f'--remote-debugging-port={debug_port}', '--window-size=1440,1100', 'about:blank'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pages = wait_http(f'http://127.0.0.1:{debug_port}/json')
            target = next(page for page in pages if page['type'] == 'page')
            with connect(target['webSocketDebuggerUrl'], max_size=16 * 1024 * 1024) as ws:
                sequence = 0
                exceptions = []
                def command(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    ws.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
                    while True:
                        result = json.loads(ws.recv(timeout=15))
                        if result.get('method') == 'Runtime.exceptionThrown':
                            exceptions.append(result['params'])
                        if result.get('id') == sequence:
                            if 'error' in result:
                                raise RuntimeError(result['error'])
                            return result.get('result', {})
                def evaluate(expression):
                    result = command('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
                    if 'exceptionDetails' in result:
                        raise AssertionError(result['exceptionDetails'])
                    return result.get('result', {}).get('value')
                def wait(expression):
                    for _ in range(100):
                        if evaluate(expression):
                            return
                        time.sleep(.1)
                    raise AssertionError(expression)
                command('Runtime.enable')
                command('Page.enable')
                command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
                command('Page.navigate', {'url': base})
                wait("!!document.querySelector('#loginForm')")
                screenshot_dir = ROOT / 'docs' / 'screenshots'
                screenshot_dir.mkdir(exist_ok=True)
                def screenshot(name):
                    wait("document.readyState === 'complete' && document.documentElement.clientWidth > 0")
                    size = evaluate('({width: window.innerWidth, height: window.innerHeight})')
                    data = command('Page.captureScreenshot', {'format': 'png', 'clip': {'x': 0, 'y': 0, **size, 'scale': 1}})
                    (screenshot_dir / name).write_bytes(base64.b64decode(data['data']))
                screenshot('login.png')
                evaluate("document.querySelector('a[href=\"/register\"]').click()")
                wait("!!document.querySelector('#registerForm')")
                screenshot('register.png')
                evaluate(f"document.querySelector('[name=username]').value='admin'; document.querySelector('[name=password]').value={json.dumps(password)}; document.querySelector('[name=password_confirmation]').value={json.dumps(password)}; document.querySelector('#registerForm').requestSubmit();")
                wait("!document.querySelector('#registerForm') && document.querySelector('#registerMessage')?.className === 'success-message'")
                evaluate("document.querySelector('#loginLink').click()")
                wait("!!document.querySelector('#loginForm')")
                for role in ('admin', 'thu_kho', 'ke_toan'):
                    evaluate(f"document.querySelector('[name=identifier]').value={json.dumps(role)}; document.querySelector('[name=password]').value={json.dumps(password)}; document.querySelector('#loginForm').requestSubmit();")
                    wait("document.querySelector('#total_products')?.textContent === '6'")
                    assert evaluate("document.querySelectorAll('.stat-card').length") == 6
                    assert evaluate("document.querySelector('#total_stock').textContent") == '94'
                    assert evaluate("!!document.querySelector('a[href=\"/workspace/users\"]')") == (role == 'admin')
                    evaluate("document.querySelector('#period').value='month'; document.querySelector('#period').dispatchEvent(new Event('change'))")
                    wait("document.querySelectorAll('.chart-group').length === 12 && !document.querySelector('#period').disabled")
                    if role == 'admin':
                        screenshot('dashboard.png')
                        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
                        assert evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                        screenshot('dashboard-mobile.png')
                        command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
                        command('Page.navigate', {'url': base + '/workspace/products'})
                        wait("document.querySelectorAll('#productsBody tr[data-id]').length === 6")
                        screenshot('products.png')
                        evaluate("document.querySelector('#newCategory').click(); document.querySelector('#categoryForm [name=category_name]').value='Nhóm kiểm tra'; document.querySelector('#categoryForm').requestSubmit()")
                        wait("!document.querySelector('#categoryEditor').open && [...document.querySelector('#editorCategory').options].some(o => o.textContent === 'Nhóm kiểm tra')")
                        evaluate("document.querySelector('#newProduct').click()")
                        wait("document.querySelector('#productEditor').open")
                        evaluate("const f = document.querySelector('#productEditorForm'); f.elements.product_code.value='UI-TEST'; f.elements.product_name.value='<img src=x onerror=alert(1)>'; f.elements.category_id.value=[...f.elements.category_id.options].find(o=>o.textContent==='Nhóm kiểm tra').value; f.requestSubmit()")
                        wait("!document.querySelector('#productEditor').open && document.querySelector('#productsBody').textContent.includes('UI-TEST')")
                        assert evaluate("document.querySelectorAll('#productsBody img').length") == 0
                        evaluate("document.querySelector('#categoryFilter').value=[...document.querySelector('#categoryFilter').options].find(o=>o.textContent==='Nhóm kiểm tra').value; document.querySelector('#categoryFilter').dispatchEvent(new Event('change'))")
                        wait("document.querySelectorAll('#productsBody tr[data-id]').length === 1")
                        evaluate("document.querySelector('#productSearch').value='ui-test'; document.querySelector('#productFilters').requestSubmit()")
                        wait("document.querySelector('#productsBody').getAttribute('aria-busy') !== 'true'")
                        evaluate("document.querySelector('[data-action=details]').click()")
                        wait("document.querySelector('#productDetails').open")
                        assert evaluate("document.querySelector('#detailsContent').textContent.includes('UI-TEST')")
                        evaluate("document.querySelector('#editFromDetails').click()")
                        wait("document.querySelector('#productEditor').open")
                        evaluate("document.querySelector('#productEditorForm [name=product_name]').value='Đã sửa qua giao diện'; document.querySelector('#productEditorForm').requestSubmit()")
                        wait("!document.querySelector('#productEditor').open && document.querySelector('#productsBody').textContent.includes('Đã sửa qua giao diện')")
                        evaluate("document.querySelector('[data-action=delete]').click()")
                        wait("document.querySelector('#deleteProductDialog').open")
                        evaluate("document.querySelector('[data-close=deleteProductDialog]').click()")
                        assert evaluate("document.querySelector('#productsBody').textContent.includes('UI-TEST')")
                        evaluate("document.querySelector('[data-action=delete]').click(); document.querySelector('#confirmDelete').click()")
                        wait("!document.querySelector('#deleteProductDialog').open && document.querySelectorAll('#productsBody tr[data-id]').length === 0")
                        evaluate("document.querySelector('#clearFilters').click()")
                        wait("document.querySelectorAll('#productsBody tr[data-id]').length === 6")
                        evaluate("document.querySelector('[data-action=delete]').click()")
                        wait("document.querySelector('#pageMessage').textContent.includes('không thể xóa')")
                        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
                        assert evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                        screenshot('products-mobile.png')
                        command('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
                    if role == 'admin':
                        for catalog, field in [('categories', 'category_name'), ('units', 'unit_name'), ('suppliers', 'name')]:
                            command('Page.navigate', {'url': base + '/workspace/' + catalog})
                            wait("document.querySelector('#catalogCount')?.textContent.includes('kết quả')")
                            if catalog == 'suppliers':
                                screenshot('suppliers.png')
                                evaluate("document.querySelector('#catalogBody button').click()")
                                wait("document.querySelector('#historyContent')?.textContent.includes('DEMO-PN001')")
                                evaluate("document.querySelector('#historyContent summary').click()")
                                screenshot('supplier-history.png')
                                evaluate("document.querySelector('[data-close=historyDialog]').click()")
                            evaluate("document.querySelector('#catalogAdd').click()")
                            fields = {field: 'UI danh mục'}
                            if catalog == 'suppliers':
                                fields.update(code='UI-SUP', phone='0901234567', email='ui@example.test', address='Địa chỉ thử')
                            evaluate(f"Object.entries({json.dumps(fields)}).forEach(([key,value])=>document.querySelector('#catalogForm').elements[key].value=value); document.querySelector('#catalogForm').requestSubmit()")
                            wait("!document.querySelector('#catalogDialog').open && document.querySelector('#catalogBody').textContent.includes('UI danh mục')")
                            evaluate("document.querySelector('#searchText').value='UI danh mục'; document.querySelector('#catalogSearch').requestSubmit()")
                            wait("document.querySelectorAll('#catalogBody tr[data-id]').length === 1")
                            evaluate("[...document.querySelectorAll('#catalogBody button')].find(b=>b.textContent==='Sửa').click()")
                            evaluate(f"document.querySelector('#catalogForm').elements[{json.dumps(field)}].value='UI danh mục sửa'; document.querySelector('#catalogForm').requestSubmit()")
                            wait("!document.querySelector('#catalogDialog').open && document.querySelector('#catalogBody').textContent.includes('UI danh mục sửa')")
                            evaluate("[...document.querySelectorAll('#catalogBody button')].find(b=>b.textContent==='Xóa').click(); document.querySelector('#catalogConfirmDelete').click()")
                            wait("!document.querySelector('#catalogDelete').open && document.querySelectorAll('#catalogBody tr[data-id]').length === 0")
                    command('Page.navigate', {'url': base + '/workspace/receipts'})
                    wait("document.querySelector('#listBody')?.textContent.includes('DEMO-PN001')")
                    assert evaluate("!!document.querySelector('#documentForm')") == (role != 'ke_toan')
                    evaluate("document.querySelector('#logout').click()")
                    wait("!!document.querySelector('#loginForm')")
                assert not exceptions, exceptions
                print('Browser smoke passed: registration, roles, dashboard, product/catalog/supplier CRUD, supplier history, filters, mobile layout and logout; no JS exceptions.')
                command('Browser.close')
            chrome.wait(timeout=10)
        finally:
            if chrome and chrome.poll() is None:
                chrome.terminate(); chrome.wait(timeout=10)
            server.terminate(); server.wait(timeout=10)


if __name__ == '__main__':
    main()
