from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.auth import current_user, warehouse_user
from app.database import get_db
from app.models import Unit, Product
from app.services.catalog_service import lock_catalog, save

router = APIRouter(prefix='/units', tags=['Đơn vị tính'], dependencies=[Depends(current_user)])


class UnitInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    unit_name: str = Field(min_length=1, max_length=20)


def find(db, unit_id):
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(404, 'Không tìm thấy đơn vị tính.')
    return unit


def duplicate(db, name, exclude=None):
    if any(u.unit_id != exclude and u.unit_name.casefold() == name.casefold() for u in db.query(Unit)):
        raise HTTPException(409, 'Tên đơn vị tính đã tồn tại.')


@router.get('/')
def list_units(q: str = Query('', max_length=200), db: Session = Depends(get_db)):
    return [{'unit_id': u.unit_id, 'unit_name': u.unit_name,
             'product_count': db.query(Product).filter(Product.unit == u.unit_name).count()}
            for u in db.query(Unit).order_by(Unit.unit_name) if q.strip().casefold() in u.unit_name.casefold()]


@router.post('/', status_code=201, dependencies=[Depends(warehouse_user)])
def create_unit(payload: UnitInput, db: Session = Depends(get_db)):
    lock_catalog(db); duplicate(db, payload.unit_name)
    unit = Unit(**payload.model_dump()); db.add(unit); save(db)
    return {'unit_id': unit.unit_id, 'unit_name': unit.unit_name}


@router.put('/{unit_id}', dependencies=[Depends(warehouse_user)])
def update_unit(unit_id: int, payload: UnitInput, db: Session = Depends(get_db)):
    lock_catalog(db); unit = find(db, unit_id); duplicate(db, payload.unit_name, unit_id)
    db.query(Product).filter(Product.unit == unit.unit_name).update({'unit': payload.unit_name})
    unit.unit_name = payload.unit_name; save(db)
    return {'unit_id': unit.unit_id, 'unit_name': unit.unit_name}


@router.delete('/{unit_id}', status_code=204, dependencies=[Depends(warehouse_user)])
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    lock_catalog(db); unit = find(db, unit_id)
    if db.query(Product).filter(Product.unit == unit.unit_name).first():
        raise HTTPException(409, 'Đơn vị tính đang được hàng hóa sử dụng, không thể xóa.')
    db.delete(unit); save(db)
    return Response(status_code=204)
