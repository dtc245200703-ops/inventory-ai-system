from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.auth import current_user, warehouse_user
from app.services.catalog_service import resolve_unit, lock_catalog

router = APIRouter(prefix="/products", tags=["Quản lý Sản phẩm"], dependencies=[Depends(current_user)])


def product_query(db):
    return db.query(models.Product).options(joinedload(models.Product.category), joinedload(models.Product.inventory))


def used_product_ids(db, product_id=None):
    used = set()
    for model in (models.ReceiptItem, models.IssueItem, models.StockMovement):
        query = db.query(model.product_id)
        if product_id is not None:
            query = query.filter(model.product_id == product_id)
        used.update(row[0] for row in query.distinct())
    return used


def describe(product, used):
    quantity = product.inventory.quantity_available if product.inventory else 0
    reason = None
    if product.product_id in used:
        reason = "Hàng hóa đã có chứng từ hoặc lịch sử kho, không thể xóa."
    elif quantity != 0:
        reason = "Chỉ có thể xóa hàng hóa có số lượng tồn bằng 0."
    stock_status = "out_of_stock" if quantity <= 0 else "low_stock" if quantity < (product.min_stock_level or 0) else "in_stock"
    return {"product_id": product.product_id, "product_code": product.product_code,
            "product_name": product.product_name, "category_id": product.category_id,
            "category_name": product.category.category_name if product.category else None,
            "unit": product.unit, "min_stock_level": product.min_stock_level or 0,
            "purchase_price": product.purchase_price, "sale_price": product.sale_price,
            "quantity_available": quantity, "stock_status": stock_status,
            "last_updated": product.inventory.last_updated if product.inventory else None,
            "can_delete": reason is None, "deletion_reason": reason}


def find_product(db, product_id):
    product = product_query(db).filter(models.Product.product_id == product_id).first()
    if product is None:
        raise HTTPException(404, "Không tìm thấy hàng hóa.")
    return product


def validate_product(db, payload, exclude_id=None):
    duplicates = db.query(models.Product.product_id).filter(
        func.lower(models.Product.product_code) == payload.product_code.lower())
    if exclude_id is not None:
        duplicates = duplicates.filter(models.Product.product_id != exclude_id)
    if duplicates.first():
        raise HTTPException(409, "Mã hàng đã tồn tại.")
    if payload.category_id is not None and db.get(models.Category, payload.category_id) is None:
        raise HTTPException(404, "Không tìm thấy nhóm hàng.")


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dữ liệu bị trùng hoặc đang được sử dụng. Vui lòng tải lại danh sách.")


@router.get("/", response_model=list[schemas.ProductDetail], summary="Tìm kiếm và lọc hàng hóa")
def get_all_products(q: str = Query("", max_length=200), category_id: int | None = Query(None, ge=0),
                     db: Session = Depends(get_db)):
    query = product_query(db).order_by(models.Product.product_code, models.Product.product_id)
    if category_id is not None:
        query = query.filter(models.Product.category_id == (category_id or None))
    products = query.all()
    # Python casefold supports Vietnamese upper/lowercase unlike SQLite lower().
    term = q.strip().casefold()
    if term:
        products = [p for p in products if term in p.product_code.casefold() or term in p.product_name.casefold()]
    used = used_product_ids(db)
    return [describe(product, used) for product in products]


@router.get("/{product_id}", response_model=schemas.ProductDetail, summary="Chi tiết hàng hóa")
def get_product(product_id: int, db: Session = Depends(get_db)):
    return describe(find_product(db, product_id), used_product_ids(db, product_id))


@router.post("/", response_model=schemas.ProductDetail, status_code=201,
             dependencies=[Depends(warehouse_user)], summary="Thêm hàng hóa")
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    lock_catalog(db)
    validate_product(db, product)
    product.unit = resolve_unit(db, product.unit)
    new_product = models.Product(**product.model_dump())
    new_product.inventory = models.Inventory(quantity_available=0)
    db.add(new_product)
    commit(db)
    return describe(find_product(db, new_product.product_id), set())


@router.put("/{product_id}", response_model=schemas.ProductDetail,
            dependencies=[Depends(warehouse_user)], summary="Sửa hàng hóa")
def update_product(product_id: int, payload: schemas.ProductCreate, db: Session = Depends(get_db)):
    lock_catalog(db)
    product = find_product(db, product_id)
    validate_product(db, payload, product_id)
    payload.unit = resolve_unit(db, payload.unit)
    for key, value in payload.model_dump().items():
        if key in {'purchase_price', 'sale_price'} and key not in payload.model_fields_set:
            continue
        setattr(product, key, value)
    commit(db)
    return describe(find_product(db, product_id), used_product_ids(db, product_id))


@router.delete("/{product_id}", status_code=204, dependencies=[Depends(warehouse_user)], summary="Xóa hàng hóa chưa sử dụng")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    # Take SQLite's write lock before checking stock/history and deleting.
    if db.get_bind().dialect.name == "sqlite":
        db.rollback()
        db.execute(text("BEGIN IMMEDIATE"))
    product = find_product(db, product_id)
    info = describe(product, used_product_ids(db, product_id))
    if not info["can_delete"]:
        raise HTTPException(409, info["deletion_reason"])
    db.delete(product)
    commit(db)
    return Response(status_code=204)
