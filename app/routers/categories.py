from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app import models, schemas
from app.auth import current_user, warehouse_user
from app.database import get_db
from app.services.catalog_service import lock_catalog, save

router = APIRouter(prefix="/categories", tags=["Nhóm hàng"], dependencies=[Depends(current_user)])


@router.get("/", response_model=list[schemas.CategoryResponse])
def list_categories(q: str = Query('', max_length=200), db: Session = Depends(get_db)):
    return [c for c in db.query(models.Category).order_by(models.Category.category_name)
            if q.strip().casefold() in c.category_name.casefold()]


@router.post("/", response_model=schemas.CategoryResponse, status_code=201, dependencies=[Depends(warehouse_user)])
def create_category(payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    lock_catalog(db)
    if any(category.category_name.casefold() == payload.category_name.casefold() for category in db.query(models.Category)):
        raise HTTPException(409, "Tên nhóm hàng đã tồn tại.")
    category = models.Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put('/{category_id}', response_model=schemas.CategoryResponse, dependencies=[Depends(warehouse_user)])
def update_category(category_id: int, payload: schemas.CategoryCreate, db: Session = Depends(get_db)):
    lock_catalog(db)
    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(404, 'Không tìm thấy nhóm hàng.')
    if any(c.category_id != category_id and c.category_name.casefold() == payload.category_name.casefold() for c in db.query(models.Category)):
        raise HTTPException(409, 'Tên nhóm hàng đã tồn tại.')
    category.category_name = payload.category_name; save(db)
    return category


@router.delete('/{category_id}', status_code=204, dependencies=[Depends(warehouse_user)])
def delete_category(category_id: int, db: Session = Depends(get_db)):
    lock_catalog(db)
    category = db.get(models.Category, category_id)
    if category is None:
        raise HTTPException(404, 'Không tìm thấy nhóm hàng.')
    if db.query(models.Product).filter_by(category_id=category_id).first():
        raise HTTPException(409, 'Nhóm hàng đang được sử dụng, không thể xóa.')
    db.delete(category); save(db)
    return Response(status_code=204)
