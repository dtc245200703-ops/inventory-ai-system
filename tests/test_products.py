"""Product management acceptance checks, isolated from Stage 3 tests."""
import pytest
from test_auth_dashboard import context, sign_in
from app import models


def product_payload(**changes):
    return {'product_code': 'NEW-01', 'product_name': 'Nồi cơm điện', 'unit': 'Cái',
            'min_stock_level': 5, 'category_id': None, **changes}


def test_product_lifecycle_and_inventory_preserved(context):
    client, factory, password = context
    headers = sign_in(client, password, 'thu_kho')
    category = client.post('/categories/', headers=headers, json={'category_name': ' Gia dụng '})
    assert category.status_code == 201
    category_id = category.json()['category_id']
    response = client.post('/products/', headers=headers, json=product_payload(category_id=category_id))
    assert response.status_code == 201, response.text
    product = response.json(); pid = product['product_id']
    assert product['quantity_available'] == 0 and product['can_delete']
    assert product['category_name'] == 'Gia dụng' and product['stock_status'] == 'out_of_stock'
    assert client.get(f'/products/{pid}').json()['product_code'] == 'NEW-01'
    with factory() as db:
        db.get(models.Inventory, pid).quantity_available = 3; db.commit()
    updated = client.put(f'/products/{pid}', headers=headers,
                         json=product_payload(product_name='Tên mới', category_id=None))
    assert updated.status_code == 200
    assert updated.json()['quantity_available'] == 3
    assert updated.json()['stock_status'] == 'low_stock'
    assert updated.json()['category_name'] is None
    assert client.delete(f'/products/{pid}', headers=headers).status_code == 409
    with factory() as db:
        db.get(models.Inventory, pid).quantity_available = 0; db.commit()
    assert client.delete(f'/products/{pid}', headers=headers).status_code == 204
    assert client.get(f'/products/{pid}').status_code == 404
    with factory() as db:
        assert db.get(models.Inventory, pid) is None
        assert db.get(models.Product, pid) is None


def test_search_category_and_status(context):
    client, factory, password = context
    headers = sign_in(client, password)
    category_id = client.post('/categories/', headers=headers, json={'category_name': 'Gia dụng'}).json()['category_id']
    pid = client.post('/products/', headers=headers, json=product_payload(category_id=category_id)).json()['product_id']
    matches = client.get('/products/', params={'q': 'NỒI CƠM', 'category_id': category_id}).json()
    assert len(matches) == 1 and matches[0]['product_id'] == pid
    assert len(client.get('/products/', params={'q': 'new-01'}).json()) == 1
    assert client.get('/products/', params={'q': 'NỒI', 'category_id': 0}).json() == []
    assert [p['product_id'] for p in client.get('/products/', params={'category_id': 0}).json()] == [1]
    with factory() as db:
        db.get(models.Inventory, pid).quantity_available = 5; db.commit()
    assert client.get(f'/products/{pid}').json()['stock_status'] == 'in_stock'


def test_product_validation_and_duplicate_codes(context):
    client, factory, password = context
    headers = sign_in(client, password)
    for field, value in [('product_code', '   '), ('product_name', ''), ('unit', ' '), ('min_stock_level', -1)]:
        assert client.post('/products/', headers=headers, json=product_payload(**{field: value})).status_code == 422
    assert client.post('/products/', headers=headers, json=product_payload(product_code='p1')).status_code == 409
    assert client.post('/products/', headers=headers, json=product_payload(category_id=999)).status_code == 404
    assert client.put('/products/1', headers=headers, json=product_payload(quantity_available=999)).status_code == 422
    assert client.put('/products/999', headers=headers, json=product_payload()).status_code == 404
    assert client.delete('/products/999', headers=headers).status_code == 404
    assert client.post('/categories/', headers=headers, json={'category_name': ' '}).status_code == 422
    client.post('/categories/', headers=headers, json={'category_name': 'Gia dụng'})
    assert client.post('/categories/', headers=headers, json={'category_name': 'GIA DỤNG'}).status_code == 409


@pytest.mark.parametrize('reference', ['receipt', 'issue', 'movement'])
def test_cannot_delete_history_even_at_zero_stock(context, reference):
    client, factory, password = context
    headers = sign_in(client, password)
    with factory() as db:
        db.get(models.Inventory, 1).quantity_available = 0
        if reference == 'receipt':
            doc = models.Receipt(receipt_no='DRAFT', supplier_id=1, created_by=1, status='draft')
            db.add(doc); db.flush()
            db.add(models.ReceiptItem(receipt_id=doc.id, product_id=1, quantity=1))
        elif reference == 'issue':
            doc = models.Issue(issue_no='DRAFT', created_by=1, status='draft')
            db.add(doc); db.flush()
            db.add(models.IssueItem(issue_id=doc.id, product_id=1, quantity=1))
        else:
            db.add(models.StockMovement(product_id=1, type='adjustment', ref_id=0,
                                       quantity=1, balance_after=0, created_by=1))
        db.commit()
    assert client.get('/products/1').json()['can_delete'] is False
    assert client.delete('/products/1', headers=headers).status_code == 409
    with factory() as db:
        assert db.get(models.Product, 1) is not None
        assert db.get(models.Inventory, 1).quantity_available == 0


@pytest.mark.parametrize('role', ['admin', 'thu_kho', 'ke_toan'])
def test_product_write_permissions(context, role):
    client, factory, password = context
    headers = sign_in(client, password, role)
    assert client.get('/products/1').status_code == 200
    assert client.get('/categories/').status_code == 200
    assert client.put('/products/1', headers=headers, json=product_payload()).status_code == (403 if role == 'ke_toan' else 200)
    assert client.delete('/products/1', headers=headers).status_code == (403 if role == 'ke_toan' else 409)
    assert client.post('/categories/', headers=headers, json={'category_name': 'Test'}).status_code == (403 if role == 'ke_toan' else 201)
    assert client.put('/products/1', json=product_payload()).status_code == 403
    assert client.delete('/products/1').status_code == 403
