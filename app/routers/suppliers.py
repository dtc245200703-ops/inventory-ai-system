import re
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import current_user, warehouse_user
from app.database import get_db
from app.models import Supplier, Receipt
from app.schemas import SupplierResponse, ReceiptResponse
from app.services.catalog_service import lock_catalog, save

router = APIRouter(prefix="/suppliers", tags=["Nhà cung cấp"], dependencies=[Depends(current_user)])


class SupplierInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        if not value:
            return None
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Email không hợp lệ.')
        return value.lower()


@router.get("/", response_model=list[SupplierResponse])
def list_suppliers(q: str = Query('', max_length=200), db: Session = Depends(get_db)):
    term = q.strip().casefold()
    return [s for s in db.query(Supplier).order_by(Supplier.code)
            if any(term in (value or '').casefold() for value in [s.code, s.name, s.phone, s.email, s.address])]


@router.post("/", response_model=SupplierResponse, status_code=201, dependencies=[Depends(warehouse_user)])
def create_supplier(payload: SupplierInput, db: Session = Depends(get_db)):
    lock_catalog(db)
    check_code(db, payload.code)
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Mã nhà cung cấp đã tồn tại.")
    db.refresh(supplier)
    return supplier


def check_code(db, code, exclude=None):
    if any(s.supplier_id != exclude and s.code.casefold() == code.casefold() for s in db.query(Supplier)):
        raise HTTPException(409, 'Mã nhà cung cấp đã tồn tại.')


def find_supplier(db, supplier_id):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, 'Không tìm thấy nhà cung cấp.')
    return supplier


@router.get('/{supplier_id}/receipts', response_model=list[ReceiptResponse])
def supplier_history(supplier_id: int, db: Session = Depends(get_db)):
    find_supplier(db, supplier_id)
    return db.query(Receipt).filter_by(supplier_id=supplier_id).order_by(Receipt.receipt_date.desc(), Receipt.id.desc()).all()


@router.put('/{supplier_id}', response_model=SupplierResponse, dependencies=[Depends(warehouse_user)])
def update_supplier(supplier_id: int, payload: SupplierInput, db: Session = Depends(get_db)):
    lock_catalog(db); supplier = find_supplier(db, supplier_id); check_code(db, payload.code, supplier_id)
    for key, value in payload.model_dump().items():
        setattr(supplier, key, value)
    save(db)
    return supplier


@router.delete('/{supplier_id}', status_code=204, dependencies=[Depends(warehouse_user)])
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    lock_catalog(db); supplier = find_supplier(db, supplier_id)
    if db.query(Receipt).filter_by(supplier_id=supplier_id).first():
        raise HTTPException(409, 'Nhà cung cấp đã có phiếu nhập, không thể xóa.')
    db.delete(supplier); save(db)
    return Response(status_code=204)
