"""New authentication/dashboard acceptance tests; independent of Stage 3 suite."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import COOKIE_NAME, hash_password, token_hash
from app.database import get_db
from app.main import app
from app import models
from app.routers.dashboard import build_dashboard, LOCAL_TZ


@pytest.fixture
def context():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    password = 'Correct-password-123'
    encoded = hash_password(password)
    with factory() as db:
        for role in ('admin', 'thu_kho', 'ke_toan'):
            user = models.User(username=role, password_hash=encoded, role=role, is_active=1)
            db.add(user); db.flush()
            db.add(models.UserEmail(user_id=user.id, email=f'{role}@example.test'))
        db.add(models.Supplier(supplier_id=1, code='S1', name='Supplier'))
        db.add(models.Product(product_id=1, product_code='P1', product_name='<script>alert(1)</script>', unit='Cái', min_stock_level=5))
        db.add(models.Inventory(product_id=1, quantity_available=10))
        db.commit()
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, factory, password
    app.dependency_overrides.clear()
    engine.dispose()


def sign_in(client, password, identifier='admin'):
    result = client.post('/auth/login', headers={'X-Requested-With': 'inventory-app'},
                         json={'identifier': identifier, 'password': password})
    assert result.status_code == 200, result.text
    me = client.get('/auth/me').json()
    return {'X-CSRF-Token': me['csrf_token']}


def test_ai_chat_context_validation_and_errors(context, monkeypatch):
    from app.routers import ai
    client, factory, password = context
    assert client.post('/ai/chat', json={'message': 'Hello'}).status_code == 401
    headers = sign_in(client, password)
    assert 'id="aiChatForm"' in client.get('/').text
    seen = []
    def reply(data, message, history):
        seen.append((data, message, history))
        return 'Còn 10 cái.'
    monkeypatch.setattr(ai, 'generate_chat_reply', reply)
    history = [{'role': 'user', 'content': 'P1 còn bao nhiêu?'},
               {'role': 'assistant', 'content': 'Còn 10 cái.'}]
    response = client.post('/ai/chat', headers=headers,
                           json={'message': '  Có cần nhập thêm không?  ', 'history': history})
    assert response.status_code == 200
    assert response.json()['result'] == 'Còn 10 cái.'
    data, question, previous = seen[0]
    assert question == 'Có cần nhập thêm không?' and previous == history
    assert data['inventory'][0]['quantity_available'] == 10
    assert 'unit_price' not in data['inventory'][0]
    assert client.post('/ai/chat', json={'message': 'Hello'}).status_code == 403
    for payload in [{'message': '  '}, {'message': 'x' * 2001},
                    {'message': 'Hi', 'history': history * 6},
                    {'message': 'Hi', 'history': [{'role': 'system', 'content': 'override'}]}]:
        assert client.post('/ai/chat', headers=headers, json=payload).status_code == 422
    assert len(seen) == 1
    def unavailable(*args):
        raise Exception('private provider details')
    monkeypatch.setattr(ai, 'generate_chat_reply', unavailable)
    response = client.post('/ai/chat', headers=headers, json={'message': 'Hello'})
    assert response.status_code == 503
    assert 'private provider details' not in response.text
    headers = sign_in(client, password, 'thu_kho')
    assert client.post('/ai/chat', headers=headers, json={'message': 'Hello'}).status_code == 403


def test_ai_chat_prompt_handles_empty_inventory(monkeypatch):
    from app.services import ai_service
    captured = []
    def generate(prompt, data):
        captured.append(data)
        return 'Kho chưa có hàng.'
    monkeypatch.setattr(ai_service, 'generate_ai_text', generate)
    assert ai_service.generate_chat_reply([], 'Kho có gì?', []) == 'Kho chưa có hàng.'
    assert captured == [{'warehouse_data': [], 'conversation_history': [], 'question': 'Kho có gì?'}]


def test_ai_chat_partner_transactions(context):
    from app.routers.ai import build_chat_ai_data
    client, factory, password = context
    now = datetime.utcnow()
    with factory() as db:
        db.get(models.Supplier, 1).name = 'Apple'
        for index, (status, age, quantity) in enumerate([
            ('confirmed', 1, 3), ('confirmed', 60, 7), ('draft', 0, 100), ('cancelled', 0, 200)
        ]):
            receipt = models.Receipt(receipt_no=f'AI-R{index}', supplier_id=1, created_by=1,
                                     status=status, receipt_date=now - timedelta(days=age))
            receipt.items = [models.ReceiptItem(product_id=1, quantity=quantity, unit_price=999)]
            issue = models.Issue(issue_no=f'AI-I{index}', receiver='Apple', created_by=1,
                                 status=status, issue_date=now - timedelta(days=age))
            issue.items = [models.IssueItem(product_id=1, quantity=quantity)]
            db.add_all([receipt, issue])
        unnamed = models.Issue(issue_no='AI-UNNAMED', created_by=1, status='confirmed')
        unnamed.items = [models.IssueItem(product_id=1, quantity=2)]
        db.add(unnamed)
        db.commit()
        data = build_chat_ai_data(db)
    assert data['suppliers'] == [{'supplier_id': 1, 'code': 'S1', 'name': 'Apple'}]
    incoming = data['received_from_suppliers']
    assert len(incoming) == 1
    assert incoming[0]['total_quantity'] == 10
    assert incoming[0]['quantity_last_30_days'] == 3
    outgoing = next(row for row in data['issued_to_receivers'] if row['receiver'] == 'Apple')
    assert outgoing['total_quantity'] == 10
    assert outgoing['quantity_last_30_days'] == 3
    assert outgoing['product_id'] == 1
    assert any(row['receiver'] is None for row in data['issued_to_receivers'])
    assert 'unit_price' not in str(data) and 'password' not in str(data)


def test_anonymous_and_login_logout(context):
    client, factory, password = context
    assert client.get('/', follow_redirects=False).headers['location'] == '/login'
    for path in ['/products/', '/inventory/', '/receipts/', '/issues/', '/ai/data', '/dashboard/summary', '/users/', '/suppliers/']:
        assert client.get(path).status_code == 401
    assert client.post('/auth/login', json={'identifier': 'admin', 'password': password}).status_code == 403
    assert client.post('/auth/login', headers={'X-Requested-With': 'inventory-app'}, json={'identifier': 'admin', 'password': 'wrong'}).status_code == 401
    headers = sign_in(client, password, 'ADMIN@example.test')
    token = client.cookies.get(COOKIE_NAME)
    assert client.get('/').status_code == 200
    assert 'requestInterceptor' in client.get('/docs').text
    assert client.post('/auth/logout').status_code == 403
    assert client.post('/auth/logout', headers=headers).status_code == 204
    client.cookies.set(COOKIE_NAME, token)
    assert client.get('/auth/me').status_code == 401


@pytest.mark.parametrize('role', ['admin', 'thu_kho', 'ke_toan'])
def test_permissions_menu_and_actor(context, role):
    client, factory, password = context
    headers = sign_in(client, password, role)
    can_write = role != 'ke_toan'
    assert client.get('/dashboard/summary').status_code == 200
    html = client.get('/').text
    assert ('href="/workspace/users"' in html) == (role == 'admin')
    assert ('href="/workspace/products"' in html) == can_write
    assert ('href="/workspace/reports"' in html) == (role != 'thu_kho')
    assert client.get('/users/').status_code == (200 if role == 'admin' else 403)
    assert client.get('/workspace/users').status_code == (200 if role == 'admin' else 403)
    assert client.get('/ai/data').status_code == (403 if role == 'thu_kho' else 200)
    for path in ['/receipts/', '/issues/']:
        assert client.get(path).status_code == 200
    assert client.put('/inventory/1', headers=headers, json={'quantity_available': 10}).status_code == (200 if can_write else 403)
    assert client.post('/products/', headers=headers, json={'product_code': 'NEW', 'product_name': 'New', 'unit': 'Cái'}).status_code == (201 if can_write else 403)
    response = client.post('/receipts/', headers=headers, json={'supplier_id': 1, 'created_by': 999, 'items': [{'product_id': 1, 'quantity': 2}]})
    assert response.status_code == (201 if can_write else 403)
    if can_write:
        assert response.json()['created_by'] == client.get('/auth/me').json()['id']
    response = client.post('/issues/', headers=headers, json={'created_by': 999, 'items': [{'product_id': 1, 'quantity': 1}]})
    assert response.status_code == (201 if can_write else 403)
    if can_write:
        assert response.json()['created_by'] == client.get('/auth/me').json()['id']


def test_csrf_expiry_disable_and_password_storage(context):
    client, factory, password = context
    headers = sign_in(client, password)
    assert client.post('/users/', headers=headers, json={'username': 'newuser', 'email': 'new@example.test', 'password': password, 'role': 'ke_toan'}).status_code == 201
    assert client.post('/users/', headers=headers, json={'username': 'another', 'email': 'NEW@example.test', 'password': password, 'role': 'admin'}).status_code == 409
    assert client.post('/users/', json={'username': 'attacker', 'password': password, 'role': 'admin'}).status_code == 403
    assert client.patch('/users/1', headers=headers, json={'role': 'ke_toan', 'is_active': True}).status_code == 400
    token = client.cookies.get(COOKIE_NAME)
    with factory() as db:
        assert db.query(models.User).filter_by(username='newuser').one().password_hash != password
        db.get(models.AuthSession, token_hash(token)).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get('/auth/me').status_code == 401
    headers = sign_in(client, password, 'thu_kho')
    with factory() as db:
        db.get(models.User, 2).is_active = 0; db.commit()
    assert client.get('/inventory/').status_code == 401
    assert client.post('/auth/login', headers={'X-Requested-With': 'inventory-app'}, json={'identifier': 'thu_kho', 'password': password}).status_code == 401


def test_duplicate_issue_rolls_back(context):
    client, factory, password = context
    headers = sign_in(client, password, 'thu_kho')
    result = client.post('/issues/', headers=headers, json={'items': [{'product_id': 1, 'quantity': 6}, {'product_id': 1, 'quantity': 6}]})
    assert result.status_code == 409
    with factory() as db:
        assert db.get(models.Inventory, 1).quantity_available == 10
        assert db.query(models.Issue).count() == 0


def test_issue_receiver_and_inventory_adjustment_card(context):
    client, factory, password = context
    headers = sign_in(client, password, 'thu_kho')
    response = client.post('/issues/', headers=headers, json={
        'receiver': 'Phòng kỹ thuật', 'reason': 'Cấp thiết bị',
        'items': [{'product_id': 1, 'quantity': 2}],
    })
    assert response.status_code == 201
    assert response.json()['receiver'] == 'Phòng kỹ thuật'
    assert client.get('/products/1').json()['quantity_available'] == 8

    adjusted = client.put('/inventory/1', headers=headers, json={'quantity_available': 5})
    assert adjusted.status_code == 200
    card = client.get('/inventory/card/1').json()
    assert card[0]['type'] == 'adjustment'
    assert card[0]['quantity'] == 3
    assert card[0]['balance_after'] == 5


def test_report_period_and_user_full_name(context):
    from app.routers.reports import build_report
    client, factory, password = context
    headers = sign_in(client, password)
    created = client.post('/users/', headers=headers, json={
        'username': 'reporter', 'full_name': 'Nguyễn Văn A',
        'email': 'reporter@example.test', 'password': password, 'role': 'ke_toan',
    })
    assert created.status_code == 201
    assert created.json()['full_name'] == 'Nguyễn Văn A'
    with factory() as db:
        data = build_report(db, 'month', date(2026, 9, 7))
    assert data['summary']['closing'] == data['summary']['opening'] + data['summary']['import'] - data['summary']['export']
    response = client.get('/reports/', params={'period': 'year', 'selected': '2026-09-07'})
    assert response.status_code == 200
    assert response.json()['from_date'] == '2026-01-01'
    excel = client.get('/reports/export.xls', params={'period': 'month', 'selected': '2026-09-07'})
    assert excel.status_code == 200
    assert 'application/vnd.ms-excel' in excel.headers['content-type']
    pdf = client.get('/reports/export.pdf', params={'period': 'month', 'selected': '2026-09-07'})
    assert pdf.status_code == 200
    assert pdf.content.startswith(b'%PDF')


def test_transaction_history_filters(context):
    client, factory, password = context
    headers = sign_in(client, password, 'thu_kho')
    receipt = client.post('/receipts/', headers=headers, json={
        'supplier_id': 1, 'items': [{'product_id': 1, 'quantity': 4}]})
    assert receipt.status_code == 201
    issue = client.post('/issues/', headers=headers, json={
        'receiver': 'Bộ phận IT', 'reason': 'Sử dụng',
        'items': [{'product_id': 1, 'quantity': 2}]})
    assert issue.status_code == 201
    all_rows = client.get('/history/').json()
    assert {row['type'] for row in all_rows} == {'import', 'export'}
    imported = client.get('/history/', params={'movement_type': 'import', 'supplier_id': 1}).json()
    assert len(imported) == 1 and imported[0]['document_no'] == receipt.json()['receipt_no']
    assert imported[0]['supplier_name'] == 'Supplier'
    exported = client.get('/history/', params={'movement_type': 'export', 'product_id': 1}).json()
    assert len(exported) == 1 and exported[0]['document_no'] == issue.json()['issue_no']
    assert client.get('/history/', params={'from_date': '2026-09-10', 'to_date': '2026-09-01'}).status_code == 422


def test_admin_update_revokes_sessions_and_login_throttle(context):
    client, factory, password = context
    headers = sign_in(client, password)
    with TestClient(app) as keeper:
        sign_in(keeper, password, 'thu_kho')
        result = client.patch('/users/2', headers=headers,
                              json={'role': 'ke_toan', 'is_active': True, 'password': 'New-password-123'})
        assert result.status_code == 200
        assert keeper.get('/auth/me').status_code == 401
        assert keeper.post('/auth/login', headers={'X-Requested-With': 'inventory-app'},
                           json={'identifier': 'thu_kho', 'password': password}).status_code == 401
        sign_in(keeper, 'New-password-123', 'thu_kho')
        assert keeper.get('/auth/me').json()['role'] == 'ke_toan'
    import hashlib
    with factory() as db:
        db.add(models.LoginThrottle(key=hashlib.sha256(b'testclient').hexdigest(), failures=20,
                                    expires_at=datetime.utcnow() + timedelta(minutes=15)))
        db.commit()
    assert client.post('/auth/login', headers={'X-Requested-With': 'inventory-app'},
                       json={'identifier': 'admin', 'password': password}).status_code == 429


def test_dashboard_dates_stale_and_empty(context):
    client, factory, password = context
    now = datetime(2026, 9, 7, 12, tzinfo=LOCAL_TZ)
    with factory() as db:
        # UTC August 31 18:00 is September 1 01:00 in Vietnam.
        db.add(models.Receipt(receipt_no='MONTH', supplier_id=1, created_by=1, status='confirmed', receipt_date=datetime(2026, 8, 31, 18)))
        db.add(models.Receipt(receipt_no='DRAFT', supplier_id=1, created_by=1, status='draft', receipt_date=datetime(2026, 9, 1)))
        db.add(models.StockMovement(product_id=1, type='import', ref_id=1, quantity=10, balance_after=10, created_by=1, created_at=datetime(2026, 1, 1)))
        db.add(models.Product(product_id=2, product_code='P2', product_name='Low', unit='Cái', min_stock_level=5))
        db.add(models.Inventory(product_id=2, quantity_available=2))
        db.add(models.StockMovement(product_id=2, type='export', ref_id=1, quantity=3, balance_after=2, created_by=1, created_at=datetime(2026, 8, 31, 18)))
        db.add(models.Product(product_id=3, product_code='P3', product_name='Equal', unit='Cái', min_stock_level=5))
        db.add(models.Inventory(product_id=3, quantity_available=5))
        db.commit()
        data = build_dashboard(db, 'day', 90, now)
        assert data['summary'] == {'total_products': 3, 'total_stock': 17, 'low_stock': 1, 'stale_stock': 1, 'receipts_this_month': 1, 'issues_this_month': 0}
        assert data['unknown_age_products'] == 1
        assert len(data['series']) == 30
        assert data['series'][0]['export'] == 3
        assert data['top_products'][0]['product_id'] == 2
        monthly = build_dashboard(db, 'month', 90, now)
        assert len(monthly['series']) == 12
        assert monthly['series'][-1]['export'] == 3
        for table in reversed(models.Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        empty = build_dashboard(db, 'day', 90, now)
        assert all(value == 0 for value in empty['summary'].values())
        assert empty['top_products'] == []


def test_registration_first_admin_pending_approval_and_validation(context):
    client, factory, password = context
    with factory() as db:
        # An internal legacy admin must not prevent initial setup.
        db.get(models.User, 1).password_hash = '!disabled'
        db.commit()
    headers = {'X-Requested-With': 'inventory-app'}
    payload = {'username': 'founder', 'email': 'founder@example.test',
               'password': password, 'password_confirmation': password}
    assert 'href="/register"' in client.get('/login').text
    assert client.get('/register').status_code == 200
    assert client.post('/auth/register', json=payload).status_code == 403
    assert client.post('/auth/register', headers=headers, json={**payload, 'role': 'admin'}).status_code == 422
    assert client.post('/auth/register', headers=headers, json={**payload, 'password_confirmation': 'different-password'}).status_code == 422
    first = client.post('/auth/register', headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()['requires_approval'] is False
    admin_headers = sign_in(client, password, 'founder')
    assert client.get('/auth/me').json()['role'] == 'admin'
    assert client.post('/auth/register', headers=headers, json=payload).status_code == 409
    pending = client.post('/auth/register', headers=headers,
                          json={**payload, 'username': 'pending', 'email': 'pending@example.test'})
    assert pending.status_code == 201
    assert pending.json()['requires_approval'] is True
    with factory() as db:
        user = db.query(models.User).filter_by(username='pending').one()
        pending_id = user.id
        assert user.is_active == 0 and user.role == 'ke_toan'
    with TestClient(app) as other:
        assert other.post('/auth/login', headers=headers,
                          json={'identifier': 'pending', 'password': password}).status_code == 401
        assert client.patch(f'/users/{pending_id}', headers=admin_headers,
                            json={'role': 'thu_kho', 'is_active': True}).status_code == 200
        sign_in(other, password, 'pending@example.test')
        assert other.get('/auth/me').json()['role'] == 'thu_kho'
    with factory() as db:
        db.query(models.User).filter_by(username='founder').one().is_active = 0
        db.commit()
    third = client.post('/auth/register', headers=headers,
                        json={**payload, 'username': 'third', 'email': None})
    assert third.status_code == 201
    assert third.json()['requires_approval'] is True


def test_registration_rate_limit(context):
    import hashlib
    client, factory, password = context
    with factory() as db:
        db.add(models.LoginThrottle(key=hashlib.sha256(b'register:testclient').hexdigest(),
               failures=10, expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.commit()
    response = client.post('/auth/register', headers={'X-Requested-With': 'inventory-app'},
        json={'username': 'pending', 'password': password, 'password_confirmation': password})
    assert response.status_code == 429


def test_concurrent_registration_has_only_one_admin(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    engine = create_engine('sqlite:///' + (tmp_path / 'concurrent.db').as_posix(),
                           connect_args={'check_same_thread': False})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    def signup(name):
        with TestClient(app) as client:
            return client.post('/auth/register', headers={'X-Requested-With': 'inventory-app'},
                json={'username': name, 'password': 'Concurrent-password-123',
                      'password_confirmation': 'Concurrent-password-123'})
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(signup, ['first_user', 'second_user']))
        assert [r.status_code for r in responses] == [201, 201]
        assert sorted(r.json()['requires_approval'] for r in responses) == [False, True]
        with factory() as db:
            assert db.query(models.User).filter_by(role='admin', is_active=1).count() == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
