from sqlalchemy import create_engine, text
from test_auth_dashboard import context, sign_in
from app.services.brand_migration import migrate_brands


def test_brands_lifecycle_product_filter_and_ai(context, monkeypatch):
    from app.routers import ai
    client, factory, password = context
    assert client.get('/brands/').status_code == 401
    headers = sign_in(client, password, 'thu_kho')
    brand = client.post('/brands/', headers=headers, json={'brand_name': ' Apple '})
    assert brand.status_code == 201
    bid = brand.json()['brand_id']
    assert brand.json()['brand_name'] == 'Apple'
    assert client.post('/brands/', headers=headers, json={'brand_name': 'APPLE'}).status_code == 409
    assert client.post('/brands/', headers=headers, json={'brand_name': ' '}).status_code == 422
    assert client.post('/brands/', json={'brand_name': 'Other'}).status_code == 403
    assert len(client.get('/brands/?q=app').json()) == 1
    payload = {'product_code': 'IPHONE', 'product_name': 'iPhone', 'unit': 'Cái', 'brand_id': bid}
    product = client.post('/products/', headers=headers, json=payload)
    assert product.status_code == 201, product.text
    pid = product.json()['product_id']
    assert product.json()['brand_name'] == 'Apple'
    assert [p['product_id'] for p in client.get(f'/products/?brand_id={bid}').json()] == [pid]
    assert [p['product_id'] for p in client.get('/products/?brand_id=0').json()] == [1]
    assert client.get(f'/products/?brand_id={bid}&q=unknown').json() == []
    assert client.delete(f'/brands/{bid}', headers=headers).status_code == 409
    assert client.put(f'/brands/{bid}', headers=headers, json={'brand_name': 'Apple Inc.'}).status_code == 200
    assert client.get(f'/products/{pid}').json()['brand_name'] == 'Apple Inc.'
    captured = []
    def reply(data, *args):
        captured.append(data)
        return 'Hàng Apple hiện đã có nhãn.'
    monkeypatch.setattr(ai, 'generate_chat_reply', reply)
    assert client.post('/ai/chat', headers=headers, json={'message': 'Apple còn hàng gì?'}).status_code == 200
    assert captured[0]['brands'] == [{'brand_id': bid, 'brand_name': 'Apple Inc.'}]
    row = next(p for p in captured[0]['inventory'] if p['product_id'] == pid)
    assert row['brand_id'] == bid and row['brand_name'] == 'Apple Inc.'
    assert next(p for p in captured[0]['inventory'] if p['product_id'] == 1)['brand_name'] is None
    assert 'purchase_price' not in row
    assert client.put(f'/products/{pid}', headers=headers, json={**payload, 'brand_id': 999}).status_code == 404
    old_payload = {k: v for k, v in payload.items() if k != 'brand_id'}
    assert client.put(f'/products/{pid}', headers=headers, json=old_payload).json()['brand_id'] == bid
    assert client.put(f'/products/{pid}', headers=headers, json={**payload, 'brand_id': None}).json()['brand_id'] is None
    assert client.delete(f'/brands/{bid}', headers=headers).status_code == 204
    assert client.delete(f'/brands/{bid}', headers=headers).status_code == 404


def test_widget_shared_pages_and_brand_permissions(context):
    client, factory, password = context
    for role in ['admin', 'thu_kho', 'ke_toan']:
        headers = sign_in(client, password, role)
        pages = ['/', '/workspace/receipts', '/workspace/issues']
        if role != 'ke_toan':
            pages += ['/workspace/products', '/workspace/inventory', '/workspace/brands']
        for page in pages:
            html = client.get(page).text
            assert html.count('id="aiChatForm"') == 1
            assert html.count('id="aiChatToggle"') == 1
            assert 'aria-expanded="false"' in html
            assert 'aria-labelledby="aiChatTitle" hidden' in html
        assert client.get('/brands/').status_code == 200
        if role == 'ke_toan':
            assert client.post('/brands/', headers=headers, json={'brand_name': 'Other'}).status_code == 403
            assert client.get('/workspace/brands').status_code == 403


def test_brand_migration_keeps_existing_products(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'brands.db').as_posix())
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE brands (brand_id INTEGER PRIMARY KEY, brand_name TEXT)'))
        connection.execute(text('CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name TEXT)'))
        connection.execute(text("INSERT INTO products VALUES (1, 'iPhone')"))
    migrate_brands(engine)
    migrate_brands(engine)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT product_name, brand_id FROM products')).one() == ('iPhone', None)
    engine.dispose()
