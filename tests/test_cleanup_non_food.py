import json

import pytest
from sqlalchemy import create_engine, text

from cleanup_non_food import cleanup


@pytest.fixture
def engine():
    engine = create_engine('sqlite://')
    with engine.begin() as db:
        db.exec_driver_sql('PRAGMA foreign_keys=ON')
        for sql in [
            'CREATE TABLE categories (category_id INTEGER PRIMARY KEY, category_name TEXT)',
            'CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name TEXT, category_id INTEGER REFERENCES categories)',
            'CREATE TABLE inventory (product_id INTEGER REFERENCES products, quantity_available INTEGER)',
            'CREATE TABLE receipts (id INTEGER PRIMARY KEY)',
            'CREATE TABLE receipt_items (id INTEGER PRIMARY KEY, receipt_id INTEGER REFERENCES receipts, product_id INTEGER REFERENCES products, quantity INTEGER)',
            "INSERT INTO categories VALUES (1, 'Thực phẩm'), (2, 'Điện tử')",
            "INSERT INTO products VALUES (1, 'Gạo', 1), (2, 'TV', 2), (3, 'iPhone', 2)",
            'INSERT INTO inventory VALUES (1, 62), (2, 9600), (3, 1790)',
            'INSERT INTO receipts VALUES (1), (2)',
            'INSERT INTO receipt_items VALUES (1, 1, 1, 62), (2, 1, 2, 9600), (3, 2, 3, 1790)',
        ]:
            db.exec_driver_sql(sql)
    yield engine
    engine.dispose()


def test_preview_then_cleanup_preserves_food_and_mixed_receipt(engine, tmp_path):
    assert cleanup(engine) == {'keep': ['Gạo'], 'remove': ['TV', 'iPhone'], 'applied': False}
    with engine.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM products')).scalar() == 3
    backup = tmp_path / 'snapshot.json'
    assert cleanup(engine, backup)['applied']
    assert len(json.loads(backup.read_text(encoding='utf-8'))['products']) == 3
    with engine.connect() as db:
        assert db.execute(text('SELECT product_name FROM products')).scalars().all() == ['Gạo']
        assert db.execute(text('SELECT quantity_available FROM inventory')).scalars().all() == [62]
        assert db.execute(text('SELECT id FROM receipts')).scalars().all() == [1]
        assert db.execute(text('SELECT quantity FROM receipt_items')).scalars().all() == [62]


def test_refuses_database_without_food(engine, tmp_path):
    with engine.begin() as db:
        db.execute(text('UPDATE products SET category_id=2'))
    with pytest.raises(ValueError):
        cleanup(engine, tmp_path / 'backup.json')
    with engine.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM products')).scalar() == 3


def test_existing_backup_blocks_deletion(engine, tmp_path):
    backup = tmp_path / 'backup.json'
    backup.write_text('existing backup')
    with pytest.raises(FileExistsError):
        cleanup(engine, backup)
    with engine.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM products')).scalar() == 3
