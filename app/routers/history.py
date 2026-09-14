from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import current_user
from app.database import get_db
from app import models

router = APIRouter(prefix="/history", tags=["Lịch sử nhập xuất"], dependencies=[Depends(current_user)])
LOCAL_TZ = timezone(timedelta(hours=7))


def utc_boundary(value: date, end=False):
    local = datetime.combine(value + (timedelta(days=1) if end else timedelta()), time.min, LOCAL_TZ)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/")
def transaction_history(
    from_date: date | None = None,
    to_date: date | None = None,
    product_id: int | None = Query(None, ge=1),
    supplier_id: int | None = Query(None, ge=1),
    movement_type: Literal["import", "export"] | None = None,
    user_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Từ ngày không được lớn hơn đến ngày.")
    query = (db.query(models.StockMovement, models.Product, models.User)
             .join(models.Product, models.Product.product_id == models.StockMovement.product_id)
             .join(models.User, models.User.id == models.StockMovement.created_by)
             .filter(models.StockMovement.type.in_(["import", "export"])))
    if from_date:
        query = query.filter(models.StockMovement.created_at >= utc_boundary(from_date))
    if to_date:
        query = query.filter(models.StockMovement.created_at < utc_boundary(to_date, True))
    if product_id:
        query = query.filter(models.StockMovement.product_id == product_id)
    if movement_type:
        query = query.filter(models.StockMovement.type == movement_type)
    if user_id:
        query = query.filter(models.StockMovement.created_by == user_id)
    rows = query.order_by(models.StockMovement.created_at.desc(), models.StockMovement.id.desc()).all()
    receipt_ids = {movement.ref_id for movement, _, _ in rows if movement.type == "import"}
    issue_ids = {movement.ref_id for movement, _, _ in rows if movement.type == "export"}
    receipts = {row.id: row for row in db.query(models.Receipt).filter(models.Receipt.id.in_(receipt_ids)).all()} if receipt_ids else {}
    issues = {row.id: row for row in db.query(models.Issue).filter(models.Issue.id.in_(issue_ids)).all()} if issue_ids else {}
    result = []
    for movement, product, user in rows:
        receipt = receipts.get(movement.ref_id) if movement.type == "import" else None
        issue = issues.get(movement.ref_id) if movement.type == "export" else None
        if supplier_id and (not receipt or receipt.supplier_id != supplier_id):
            continue
        supplier = db.get(models.Supplier, receipt.supplier_id) if receipt else None
        result.append({"id": movement.id, "created_at": movement.created_at, "type": movement.type,
            "document_no": receipt.receipt_no if receipt else issue.issue_no if issue else str(movement.ref_id),
            "product_id": product.product_id, "product_code": product.product_code,
            "product_name": product.product_name, "quantity": movement.quantity,
            "balance_after": movement.balance_after, "supplier_id": supplier.supplier_id if supplier else None,
            "supplier_name": supplier.name if supplier else None, "user_id": user.id,
            "username": user.username, "full_name": user.full_name})
    return result


@router.get("/filters")
def history_filters(db: Session = Depends(get_db)):
    return {"products": [{"id": row.product_id, "code": row.product_code, "name": row.product_name}
                         for row in db.query(models.Product).order_by(models.Product.product_code)],
            "suppliers": [{"id": row.supplier_id, "code": row.code, "name": row.name}
                          for row in db.query(models.Supplier).order_by(models.Supplier.code)],
            "users": [{"id": row.id, "username": row.username, "full_name": row.full_name}
                      for row in db.query(models.User).order_by(models.User.username)]}
