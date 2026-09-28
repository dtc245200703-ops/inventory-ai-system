from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from test_auth_dashboard import context, sign_in
from app import models
from app.auth import COOKIE_NAME, token_hash
from app.database import get_db
from app.main import app
from app.services.partner_migration import migrate_partner_role


def create_partners(client, password):
    headers = sign_in(client, password)
    ids = []
    for name in ['partner_a', 'partner_b']:
        response = client.post('/users/', headers=headers, json={
            'username': name, 'full_name': name, 'password': password, 'role': 'nhan_hang'})
        assert response.status_code == 201, response.text
        ids.append(response.json()['id'])
    return ids


def submit(client, headers, quantity=3):
    response = client.post('/partner-requests/', headers=headers,
        json={'note': 'Giao trong tuần', 'items': [{'product_id': 1, 'quantity': quantity}]})
    assert response.status_code == 201, response.text
    return response.json()


def test_partner_isolation_and_approval(context):
    client, factory, password = context
    ids = create_partners(client, password)
    headers = sign_in(client, password, 'partner_a')
    assert client.get('/', follow_redirects=False).headers['location'] == '/workspace/partner'
    html = client.get('/workspace/partner').text
    assert 'id="partnerRequestForm"' in html and 'id="aiChatToggle"' not in html
    assert 'href="/workspace/users"' not in html and 'href="/workspace/issues"' not in html
    for path in ['/products/', '/products/1', '/inventory/', '/inventory/card/1', '/issues/', '/receipts/',
                 '/suppliers/', '/brands/', '/categories/', '/units/', '/users/', '/history/',
                 '/reports/', '/ai/data', '/dashboard/summary', '/workspace/issues', '/workspace/requests', '/docs']:
        assert client.get(path).status_code == 403, path
    assert client.post('/ai/chat', headers=headers, json={'message': 'All warehouse data'}).status_code == 403
    catalog = client.get('/partner-requests/products').json()
    assert set(catalog[0]) == {'product_id', 'product_code', 'product_name', 'unit'}
    assert client.post('/partner-requests/', json={'items': [{'product_id': 1, 'quantity': 1}]}).status_code == 403
    assert client.post('/partner-requests/', headers=headers, json={'requested_by': ids[1], 'items': [{'product_id': 1, 'quantity': 1}]}).status_code == 422
    request = submit(client, headers)
    rid = request['id']
    assert request['requested_by'] == ids[0] and request['status'] == 'pending' and request['issue'] is None
    with factory() as db:
        assert db.get(models.Inventory, 1).quantity_available == 10
        assert db.query(models.Issue).count() == 0
    assert client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'approve'}).status_code == 403
    headers = sign_in(client, password, 'partner_b')
    assert client.get('/partner-requests/').json() == []
    assert client.get(f'/partner-requests/{rid}').status_code == 404
    headers = sign_in(client, password, 'thu_kho')
    assert client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'approve'}).status_code == 403
    headers = sign_in(client, password)
    assert len(client.get('/partner-requests/').json()) == 1
    response = client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'approve', 'note': 'Đồng ý'})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'approved'
    assert response.json()['issue']['created_by'] == 1
    assert response.json()['issue']['items'][0]['quantity'] == 3
    assert client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'approve'}).status_code == 409
    assert client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'reject', 'note': 'Again'}).status_code == 409
    with factory() as db:
        assert db.get(models.Inventory, 1).quantity_available == 7
        assert db.query(models.Issue).count() == 1
        assert db.query(models.StockMovement).count() == 1
    sign_in(client, password, 'partner_a')
    own = client.get('/partner-requests/').json()
    assert own[0]['issue']['items'][0]['quantity'] == 3 and own[0]['review_note'] == 'Đồng ý'


def test_shortage_rejection_validation_and_disabled_partner(context):
    client, factory, password = context
    ids = create_partners(client, password)
    headers = sign_in(client, password, 'partner_a')
    for items in [[], [{'product_id': 1, 'quantity': 0}], [{'product_id': 1, 'quantity': -2}], [{'product_id': 1, 'quantity': 1.5}]]:
        assert client.post('/partner-requests/', headers=headers, json={'items': items}).status_code == 422
    assert client.post('/partner-requests/', headers=headers, json={'items': [{'product_id': 999, 'quantity': 1}]}).status_code == 404
    rid = submit(client, headers, quantity=20)['id']
    second = submit(client, headers)['id']
    headers = sign_in(client, password)
    assert client.delete('/products/1', headers=headers).status_code == 409
    response = client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'approve'})
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.get(models.Inventory, 1).quantity_available == 10
        assert db.get(models.PartnerRequest, rid).status == 'pending'
        assert db.query(models.Issue).count() == 0
        assert db.query(models.StockMovement).count() == 0
    assert client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'reject', 'note': '  '}).status_code == 422
    rejected = client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'reject', 'note': 'Chưa đủ hàng'})
    assert rejected.status_code == 200 and rejected.json()['issue'] is None
    assert client.patch(f'/users/{ids[0]}', headers=headers, json={'role': 'nhan_hang', 'is_active': False}).status_code == 200
    assert client.post(f'/partner-requests/{second}/review', headers=headers, json={'decision': 'approve'}).status_code == 409


def test_approval_failure_rolls_back_entire_transaction(context, monkeypatch):
    from app.routers import partner_requests
    client, factory, password = context
    create_partners(client, password)
    headers = sign_in(client, password, 'partner_a')
    rid = submit(client, headers)['id']
    headers = sign_in(client, password)
    original = partner_requests.create_issue
    def fail_after_issue(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('injected after stock update')
    monkeypatch.setattr(partner_requests, 'create_issue', fail_after_issue)
    with pytest.raises(RuntimeError, match='injected'):
        client.post(f'/partner-requests/{rid}/review', headers=headers, json={'decision': 'approve'})
    with factory() as db:
        assert db.get(models.Inventory, 1).quantity_available == 10
        assert db.query(models.Issue).count() == 0
        assert db.query(models.StockMovement).count() == 0
        row = db.get(models.PartnerRequest, rid)
        assert row.status == 'pending' and row.reviewed_at is None and row.issue_id is None


def test_role_migration_keeps_accounts_and_references(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'legacy.db').as_posix())
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT CHECK (role IN ('admin', 'thu_kho', 'ke_toan')))"))
        connection.execute(text("INSERT INTO users VALUES (7, 'owner', 'keep-password', 'admin')"))
        connection.execute(text('CREATE INDEX ix_users_username ON users(username)'))
        connection.execute(text('CREATE TABLE refs (user_id INTEGER REFERENCES users(id))'))
        connection.execute(text('INSERT INTO refs VALUES (7)'))
    migrate_partner_role(engine)
    migrate_partner_role(engine)
    with engine.begin() as connection:
        assert connection.execute(text('SELECT * FROM users')).one() == (7, 'owner', 'keep-password', 'admin')
        assert connection.execute(text('SELECT user_id FROM refs')).scalar_one() == 7
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        connection.execute(text("INSERT INTO users VALUES (8, 'partner', 'hash', 'nhan_hang')"))
        assert connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE name='ix_users_username'").scalar_one()
    engine.dispose()


def test_concurrent_approval_only_exports_once(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'concurrent.db').as_posix(), connect_args={'check_same_thread': False})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([models.User(id=1, username='admin', role='admin', password_hash='unused'),
                    models.User(id=2, username='partner', role='nhan_hang', password_hash='unused')])
        db.add(models.Product(product_id=1, product_code='P', product_name='Product', unit='Cái'))
        db.add(models.Inventory(product_id=1, quantity_available=10))
        db.add(models.AuthSession(token_hash=token_hash('test-token'), user_id=1, csrf_token='csrf', expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.add(models.PartnerRequest(id=1, requested_by=2, items=[models.PartnerRequestItem(product_id=1, quantity=4)]))
        db.commit()
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    def approve(_):
        with TestClient(app) as client:
            client.cookies.set(COOKIE_NAME, 'test-token')
            return client.post('/partner-requests/1/review', headers={'X-CSRF-Token': 'csrf'}, json={'decision': 'approve'}).status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(approve, [1, 2])) == [200, 409]
        with factory() as db:
            assert db.get(models.Inventory, 1).quantity_available == 6
            assert db.query(models.Issue).count() == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
