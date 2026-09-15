from sqlalchemy import inspect, text


def migrate_prices(engine):
    """Add nullable prices without assigning today's prices to historical rows."""
    with engine.begin() as connection:
        if connection.dialect.name == 'postgresql':
            connection.execute(text('SELECT pg_advisory_xact_lock(73421902)'))
        elif connection.dialect.name == 'sqlite':
            connection.execute(text('BEGIN IMMEDIATE'))
        for table, fields in [('products', ['purchase_price', 'sale_price']),
                              ('issue_items', ['unit_price'])]:
            existing = {column['name'] for column in inspect(connection).get_columns(table)}
            for field in fields:
                if field not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {field} NUMERIC(14, 2)'))
