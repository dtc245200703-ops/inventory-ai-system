"""Extend the existing role constraint without changing account ids or passwords."""
import re
from sqlalchemy import inspect, text


def migrate_partner_role(engine):
    roles = "role IN ('admin', 'thu_kho', 'ke_toan', 'nhan_hang')"
    if engine.dialect.name == 'postgresql':
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(73421905)'))
            constraints = inspect(connection).get_check_constraints('users')
            role_check = next((c for c in constraints if c['name'] == 'ck_users_role_valid'), None)
            if role_check and 'nhan_hang' not in role_check['sqltext']:
                connection.execute(text('ALTER TABLE users DROP CONSTRAINT ck_users_role_valid'))
                connection.execute(text(f'ALTER TABLE users ADD CONSTRAINT ck_users_role_valid CHECK ({roles})'))
        return
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('Chưa hỗ trợ nâng cấp vai trò trên cơ sở dữ liệu này.')
    with engine.connect() as connection:
        enabled = connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
        connection.commit()
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        connection.commit()
        try:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            schema = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").scalar_one()
            if 'nhan_hang' not in schema:
                updated, count = re.subn(r"role\s+IN\s*\([^)]*\)", roles, schema, flags=re.I)
                if count != 1:
                    raise RuntimeError('Không xác định được ràng buộc vai trò users; chưa thay đổi dữ liệu.')
                updated = re.sub(r'CREATE TABLE\s+(?:"users"|users)', 'CREATE TABLE users_partner_upgrade', updated, count=1, flags=re.I)
                columns = ', '.join('"' + c['name'].replace('"', '""') + '"' for c in inspect(connection).get_columns('users'))
                indexes = connection.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='users' AND sql IS NOT NULL").scalars().all()
                connection.exec_driver_sql(updated)
                connection.exec_driver_sql(f'INSERT INTO users_partner_upgrade ({columns}) SELECT {columns} FROM users')
                connection.exec_driver_sql('DROP TABLE users')
                connection.exec_driver_sql('ALTER TABLE users_partner_upgrade RENAME TO users')
                for index in indexes:
                    connection.exec_driver_sql(index)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.exec_driver_sql(f'PRAGMA foreign_keys={int(enabled)}')
            connection.commit()
