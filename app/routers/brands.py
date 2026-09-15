from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import current_user, warehouse_user
from app.database import get_db
from app.services.catalog_service import lock_catalog, save

router = APIRouter(prefix='/brands', tags=['Nhãn hàng'], dependencies=[Depends(current_user)])


def lock_brands(db):
    lock_catalog(db)
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(73421904)'))


def check_name(db, name, exclude_id=None):
    if any(b.brand_id != exclude_id and b.brand_name.casefold() == name.casefold()
           for b in db.query(models.Brand)):
        raise HTTPException(409, 'Tên nhãn hàng đã tồn tại.')


@router.get('/', response_model=list[schemas.BrandResponse])
def list_brands(q: str = Query('', max_length=200), db: Session = Depends(get_db)):
    return [b for b in db.query(models.Brand).order_by(models.Brand.brand_name)
            if q.strip().casefold() in b.brand_name.casefold()]


@router.post('/', response_model=schemas.BrandResponse, status_code=201, dependencies=[Depends(warehouse_user)])
def create_brand(payload: schemas.BrandCreate, db: Session = Depends(get_db)):
    lock_brands(db)
    check_name(db, payload.brand_name)
    brand = models.Brand(**payload.model_dump())
    db.add(brand)
    save(db)
    db.refresh(brand)
    return brand


@router.put('/{brand_id}', response_model=schemas.BrandResponse, dependencies=[Depends(warehouse_user)])
def update_brand(brand_id: int, payload: schemas.BrandCreate, db: Session = Depends(get_db)):
    lock_brands(db)
    brand = db.get(models.Brand, brand_id)
    if brand is None:
        raise HTTPException(404, 'Không tìm thấy nhãn hàng.')
    check_name(db, payload.brand_name, brand_id)
    brand.brand_name = payload.brand_name
    save(db)
    return brand


@router.delete('/{brand_id}', status_code=204, dependencies=[Depends(warehouse_user)])
def delete_brand(brand_id: int, db: Session = Depends(get_db)):
    lock_brands(db)
    brand = db.get(models.Brand, brand_id)
    if brand is None:
        raise HTTPException(404, 'Không tìm thấy nhãn hàng.')
    if db.query(models.Product).filter_by(brand_id=brand_id).first():
        raise HTTPException(409, 'Nhãn hàng đang có sản phẩm, không thể xóa.')
    db.delete(brand)
    save(db)
    return Response(status_code=204)
