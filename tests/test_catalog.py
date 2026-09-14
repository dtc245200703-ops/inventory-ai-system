import pytest
from test_auth_dashboard import context, sign_in
from app import models
from app.services.catalog_service import import_existing_units


def test_categories_crud_search_and_usage(context):
    client, factory, password = context
    headers = sign_in(client, password, 'thu_kho')
    response = client.post('/categories/', headers=headers, json={'category_name': 'Điện tử'})
    assert response.status_code == 201
    cid = response.json()['category_id']
    assert len(client.get('/categories/', params={'q': 'ĐIỆN'}).json()) == 1
    assert client.put(f'/categories/{cid}', headers=headers, json={'category_name': 'Phụ kiện'}).status_code == 200
    with factory() as db:
        db.get(models.Product, 1).category_id = cid; db.commit()
    assert client.get('/products/1').json()['category_name'] == 'Phụ kiện'
    assert client.delete(f'/categories/{cid}', headers=headers).status_code == 409
    with factory() as db:
        db.get(models.Product, 1).category_id = None; db.commit()
    assert client.delete(f'/categories/{cid}', headers=headers).status_code == 204
    assert client.put(f'/categories/{cid}', headers=headers, json={'category_name': 'Test'}).status_code == 404


def test_units_import_rename_and_delete(context):
    client, factory, password = context
    headers = sign_in(client, password)
    with factory() as db:
        import_existing_units(db)
        import_existing_units(db)
    units = client.get('/units/').json()
    assert len(units) == 1 and units[0]['unit_name'] == 'Cái'
    uid = units[0]['unit_id']
    assert client.post('/units/', headers=headers, json={'unit_name': 'CÁI'}).status_code == 409
    assert client.put(f'/units/{uid}', headers=headers, json={'unit_name': 'Chiếc'}).status_code == 200
    product = client.get('/products/1').json()
    assert product['unit'] == 'Chiếc' and product['quantity_available'] == 10
    assert client.get('/units/', params={'q': 'CHIẾC'}).json()[0]['product_count'] == 1
    assert client.delete(f'/units/{uid}', headers=headers).status_code == 409
    uid2 = client.post('/units/', headers=headers, json={'unit_name': 'Hộp'}).json()['unit_id']
    assert client.delete(f'/units/{uid2}', headers=headers).status_code == 204
    assert client.post('/units/', headers=headers, json={'unit_name': ' '}).status_code == 422


def test_supplier_contacts_history_and_delete(context):
    client, factory, password = context
    headers = sign_in(client, password)
    payload = {'code': 'NEW', 'name': 'Nhà cung cấp thử', 'phone': '0901234567',
               'email': 'CONTACT@example.test', 'address': 'Đường số 1'}
    result = client.post('/suppliers/', headers=headers, json=payload)
    assert result.status_code == 201
    sid = result.json()['supplier_id']
    assert result.json()['email'] == 'contact@example.test'
    for query in ['NEW', 'NHÀ CUNG CẤP', '090123', 'contact@', 'ĐƯỜNG']:
        assert [s['supplier_id'] for s in client.get('/suppliers/', params={'q': query}).json()] == [sid]
    assert client.post('/suppliers/', headers=headers, json={**payload, 'code': 'new'}).status_code == 409
    assert client.put(f'/suppliers/{sid}', headers=headers, json={**payload, 'phone': '0987654321'}).status_code == 200
    assert client.get(f'/suppliers/{sid}/receipts').json() == []
    with factory() as db:
        db.get(models.Inventory, 1).quantity_available = 5
        db.commit()
    receipt = client.post('/receipts/', headers=headers, json={'supplier_id': sid, 'items': [{'product_id': 1, 'quantity': 20, 'unit_price': '12500.00'}]})
    assert receipt.status_code == 201
    with factory() as db:
        assert db.get(models.Inventory, 1).quantity_available == 25
    history = client.get(f'/suppliers/{sid}/receipts').json()
    assert len(history) == 1 and history[0]['id'] == receipt.json()['id']
    assert history[0]['items'][0]['quantity'] == 20
    assert client.get('/suppliers/1/receipts').json() == []
    assert client.delete(f'/suppliers/{sid}', headers=headers).status_code == 409
    unused = client.post('/suppliers/', headers=headers, json={**payload, 'code': 'EMPTY'}).json()['supplier_id']
    assert client.delete(f'/suppliers/{unused}', headers=headers).status_code == 204
    assert client.get(f'/suppliers/{unused}/receipts').status_code == 404
    assert client.post('/suppliers/', headers=headers, json={**payload, 'code':'OTHER','email':'bad-email'}).status_code == 422


@pytest.mark.parametrize('role', ['admin', 'thu_kho', 'ke_toan'])
def test_catalog_permissions(context, role):
    client, factory, password = context
    headers = sign_in(client, password, role)
    denied = role == 'ke_toan'
    for path in ['categories', 'units', 'suppliers']:
        assert client.get(f'/{path}/').status_code == 200
    for path, payload in [('categories', {'category_name':'Test'}), ('units', {'unit_name':'Kg'}), ('suppliers', {'code':'TEST','name':'Test'})]:
        assert client.post(f'/{path}/', headers=headers, json=payload).status_code == (403 if denied else 201)
        assert client.put(f'/{path}/999', headers=headers, json=payload).status_code == (403 if denied else 404)
        assert client.delete(f'/{path}/999', headers=headers).status_code == (403 if denied else 404)
        assert client.post(f'/{path}/', json=payload).status_code == 403
    assert client.get('/workspace/suppliers').status_code == 200
    assert ('id="catalogAdd"' in client.get('/workspace/suppliers').text) == (not denied)
    assert client.get('/workspace/units').status_code == (403 if denied else 200)
