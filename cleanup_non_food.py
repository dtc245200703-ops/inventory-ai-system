"""One-off sample-data cleanup. Defaults to preview; never runs at app startup."""
import argparse
import json
import os
from pathlib import Path
import unicodedata

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, delete, select, text, update


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value or '')
                   if unicodedata.category(c) != 'Mn').casefold().strip()


def cleanup(engine, backup=None):
    with engine.begin() as connection:
        if engine.dialect.name == 'sqlite':
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        metadata = MetaData()
        metadata.reflect(bind=connection)
        tables = metadata.tables
        if engine.dialect.name == 'postgresql' and backup:
            names = ', '.join(connection.dialect.identifier_preparer.quote(t.name)
                              for t in metadata.sorted_tables)
            connection.execute(text(f'LOCK TABLE {names} IN ACCESS EXCLUSIVE MODE'))
        products, categories = tables['products'], tables['categories']
        food_ids = [r.category_id for r in connection.execute(select(categories))
                    if normalized(r.category_name) == 'thuc pham']
        kept = list(connection.execute(select(products).where(products.c.category_id.in_(food_ids))).mappings())
        if not kept:
            raise ValueError('Không có sản phẩm thuộc nhóm thực phẩm; dừng để tránh xóa nhầm database.')
        keep_ids = {r['product_id'] for r in kept}
        removed = list(connection.execute(select(products).where(products.c.product_id.not_in(keep_ids))).mappings())
        ids = [r['product_id'] for r in removed]
        result = {'keep': [r['product_name'] for r in kept],
                  'remove': [r['product_name'] for r in removed], 'applied': False}
        if backup is None or not ids:
            return result
        # Preserve a complete logical snapshot before any mutation. Never overwrite a backup.
        snapshot = {t.name: [dict(r) for r in connection.execute(select(t)).mappings()]
                    for t in metadata.sorted_tables}
        with Path(backup).open('x', encoding='utf-8') as output:
            json.dump(snapshot, output, ensure_ascii=False, default=str, indent=2)
            output.flush()
            os.fsync(output.fileno())
        documents = [('receipt_items', 'receipt_id', 'receipts'),
                     ('issue_items', 'issue_id', 'issues'),
                     ('partner_request_items', 'request_id', 'partner_requests')]
        empty = {}
        for item_name, parent_key, parent_name in documents:
            if item_name not in tables:
                continue
            items = tables[item_name]
            affected = set(connection.execute(select(items.c[parent_key]).where(items.c.product_id.in_(ids))).scalars())
            surviving = set(connection.execute(select(items.c[parent_key]).where(items.c.product_id.not_in(ids))).scalars())
            empty[parent_name] = affected - surviving
        # Only remove lines for discarded products; mixed documents retain food lines.
        for name in ('receipt_items', 'issue_items', 'partner_request_items', 'stock_movements', 'inventory'):
            if name in tables:
                table = tables[name]
                connection.execute(delete(table).where(table.c.product_id.in_(ids)))
        if 'partner_requests' in tables:
            requests = tables['partner_requests']
            connection.execute(delete(requests).where(requests.c.id.in_(empty.get('partner_requests', set()))))
            connection.execute(update(requests).where(requests.c.issue_id.in_(empty.get('issues', set()))).values(issue_id=None))
        for name in ('receipts', 'issues'):
            if name in tables:
                connection.execute(delete(tables[name]).where(tables[name].c.id.in_(empty.get(name, set()))))
        connection.execute(delete(products).where(products.c.product_id.in_(ids)))
        result['applied'] = True
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Giữ hàng thực phẩm; xóa hàng khác cùng dữ liệu kho liên quan.')
    parser.add_argument('--apply', action='store_true', help='Thực hiện xóa, mặc định chỉ xem trước')
    parser.add_argument('--backup', help='Đường dẫn JSON mới để sao lưu; bắt buộc khi --apply')
    args = parser.parse_args()
    if args.apply and not args.backup:
        parser.error('--apply cần --backup để sao lưu trước khi xóa')
    load_dotenv()
    if not os.getenv('DATABASE_URL'):
        parser.error('Cần cấu hình DATABASE_URL của đúng database; không tự chọn database mặc định')
    engine = create_engine(os.environ['DATABASE_URL'])
    try:
        print(json.dumps(cleanup(engine, args.backup if args.apply else None), ensure_ascii=True, indent=2))
    finally:
        engine.dispose()
