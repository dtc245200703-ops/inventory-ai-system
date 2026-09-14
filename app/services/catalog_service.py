from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.models import Unit, Product


def lock_catalog(db):
    if db.get_bind().dialect.name == 'sqlite':
        db.rollback()
        db.execute(text('BEGIN IMMEDIATE'))


def save(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Dữ liệu bị trùng hoặc đang được sử dụng.')


def resolve_unit(db, name):
    unit = next((u for u in db.query(Unit) if u.unit_name.casefold() == name.casefold()), None)
    if unit is None:
        unit = Unit(unit_name=name)
        db.add(unit)
        db.flush()
    return unit.unit_name


def import_existing_units(db):
    for (name,) in db.query(Product.unit).distinct().all():
        if db.query(Unit).filter_by(unit_name=name).first() is None:
            db.add(Unit(unit_name=name))
            db.flush()
    save(db)
