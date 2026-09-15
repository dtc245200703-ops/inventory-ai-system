from decimal import Decimal

from sqlalchemy import create_engine, text
from test_auth_dashboard import context, sign_in
from app.services.price_migration import migrate_prices


def test_default_prices_overrides_and_historical_snapshot(context):
    client, factory, password = context
    headers = sign_in(client, password)
    product = client.get('/products/1').json()
    payload = {key: product[key] for key in ['product_code', 'product_name', 'unit', 'min_stock_level', 'category_id']}
    updated = client.put('/products/1', headers=headers, json={**payload, 'purchase_price': '123.45', 'sale_price': '200.25'})
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()['purchase_price']) == Decimal('123.45')
    receipt = client.post('/receipts/', headers=headers, json={'supplier_id': 1, 'items': [
        {'product_id': 1, 'quantity': 2}, {'product_id': 1, 'quantity': 1, 'unit_price': '0'}]})
    assert receipt.status_code == 201, receipt.text
    assert Decimal(receipt.json()['total_amount']) == Decimal('246.90')
    issue = client.post('/issues/', headers=headers, json={'items': [
        {'product_id': 1, 'quantity': 2}, {'product_id': 1, 'quantity': 1, 'unit_price': '99.99'},
        {'product_id': 1, 'quantity': 1, 'unit_price': '0'}]})
    assert issue.status_code == 201, issue.text
    assert len(issue.json()['items']) == 3
    assert Decimal(issue.json()['total_amount']) == Decimal('500.49')
    assert client.get('/products/1').json()['quantity_available'] == 9
    assert client.put('/products/1', headers=headers, json={**payload, 'purchase_price': '999', 'sale_price': '888'}).status_code == 200
    assert Decimal(client.get(f"/receipts/{receipt.json()['id']}").json()['total_amount']) == Decimal('246.90')
    assert Decimal(client.get(f"/issues/{issue.json()['id']}").json()['total_amount']) == Decimal('500.49')
    # Older clients that omit new fields must not clear configured prices.
    assert client.put('/products/1', headers=headers, json=payload).json()['sale_price'] == '888.00'
    # Duplicate lines at different prices still share the same stock limit.
    rejected = client.post('/issues/', headers=headers, json={'items': [
        {'product_id': 1, 'quantity': 5, 'unit_price': '1'}, {'product_id': 1, 'quantity': 5, 'unit_price': '2'}]})
    assert rejected.status_code == 409
    assert client.get('/products/1').json()['quantity_available'] == 9


def test_missing_prices_are_unknown_and_validation(context):
    client, factory, password = context
    headers = sign_in(client, password)
    for endpoint, extra in [('receipts', {'supplier_id': 1}), ('issues', {})]:
        result = client.post(f'/{endpoint}/', headers=headers,
                             json={**extra, 'items': [{'product_id': 1, 'quantity': 1}]})
        assert result.status_code == 201
        assert result.json()['total_amount'] is None
        assert result.json()['items'][0]['unit_price'] is None
        for invalid in ['-1', '1.001', '1000000000000', 'NaN', 'Infinity']:
            response = client.post(f'/{endpoint}/', headers=headers,
                json={**extra, 'items': [{'product_id': 1, 'quantity': 1, 'unit_price': invalid}]})
            assert response.status_code == 422, response.text
    for field in ['purchase_price', 'sale_price']:
        for invalid in ['-1', '1.001', '1000000000000', 'NaN']:
            response = client.post('/products/', headers=headers,
                json={'product_code': 'PRICE', 'product_name': 'Price test', 'unit': 'Cái', field: invalid})
            assert response.status_code == 422
    headers = sign_in(client, password, 'ke_toan')
    assert client.post('/products/', headers=headers, json={'product_code': 'X', 'product_name': 'X', 'unit': 'Cái', 'sale_price': '1'}).status_code == 403


def test_price_migration_preserves_old_data_and_is_repeatable(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'legacy.db').as_posix())
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name TEXT)'))
        connection.execute(text("INSERT INTO products VALUES (1, 'Old product')"))
        connection.execute(text('CREATE TABLE issue_items (id INTEGER PRIMARY KEY, quantity INTEGER)'))
        connection.execute(text('INSERT INTO issue_items VALUES (1, 3)'))
    migrate_prices(engine)
    migrate_prices(engine)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT product_name, purchase_price, sale_price FROM products')).one() == ('Old product', None, None)
        assert connection.execute(text('SELECT quantity, unit_price FROM issue_items')).one() == (3, None)
    engine.dispose()
