from sqlalchemy import inspect, text


def migrate_brands(engine):
    """Run after create_all: old products keep an unknown brand."""
    with engine.begin() as connection:
        if connection.dialect.name == 'postgresql':
            connection.execute(text('SELECT pg_advisory_xact_lock(73421903)'))
        elif connection.dialect.name == 'sqlite':
            connection.execute(text('BEGIN IMMEDIATE'))
        if 'brand_id' not in {c['name'] for c in inspect(connection).get_columns('products')}:
            connection.execute(text('ALTER TABLE products ADD COLUMN brand_id INTEGER REFERENCES brands(brand_id)'))
