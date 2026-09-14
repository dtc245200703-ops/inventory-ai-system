from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.auth import current_user, warehouse_user
from app.services.catalog_service import lock_catalog
from app.exceptions import InvalidQuantityError, ProductNotFoundError
from app.services.receipt_service import create_receipt as create_receipt_service

router = APIRouter(
    prefix="/receipts", dependencies=[Depends(current_user)],
    tags=["Phiếu nhập kho"]
)


@router.get(
    "/",
    response_model=List[schemas.ReceiptResponse],
    summary="Lấy danh sách phiếu nhập",
    description="Truy xuất toàn bộ phiếu nhập kho đã lập."
)
def get_all_receipts(db: Session = Depends(get_db)):
    return db.query(models.Receipt).all()


@router.get(
    "/{receipt_id}",
    response_model=schemas.ReceiptResponse,
    summary="Xem chi tiết phiếu nhập",
    description="Xem thông tin phiếu nhập cùng danh sách hàng hóa trong phiếu."
)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập")
    return receipt


@router.post(
    "/",
    response_model=schemas.ReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lập phiếu nhập kho",
    description=(
        "UC05 - Tạo phiếu nhập, tăng tồn kho và ghi lịch sử biến động (stock_movements) "
        "trong cùng 1 transaction. Nếu có lỗi ở bất kỳ dòng hàng nào, toàn bộ phiếu bị "
        "rollback, không tăng tồn một phần (BR02, BR05, BR07)."
    ),
)
def create_new_receipt(payload: schemas.ReceiptCreate, db: Session = Depends(get_db), user=Depends(warehouse_user)):
    lock_catalog(db)
    if db.get(models.Supplier, payload.supplier_id) is None:
        raise HTTPException(404, "Không tìm thấy nhà cung cấp.")
    try:
        receipt = create_receipt_service(
            db,
            supplier_id=payload.supplier_id,
            created_by=user.id,
            items=[item.model_dump() for item in payload.items],
        )
        return receipt
    except InvalidQuantityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProductNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
