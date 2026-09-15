from datetime import datetime
from typing import List, Optional, TypedDict

from sqlalchemy.orm import Session

from app import models
from app.exceptions import InvalidQuantityError, ProductNotFoundError


class ReceiptItemInput(TypedDict, total=False):
    product_id: int
    quantity: int
    unit_price: float  # giá mua - có thể None, chỉ dùng nội bộ, KHÔNG gửi cho AI


def _generate_receipt_no() -> str:
    return f"PN{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"


def create_receipt(
    db: Session,
    supplier_id: int,
    created_by: int,
    items: List[ReceiptItemInput],
    receipt_no: Optional[str] = None,
) -> models.Receipt:
    """
    UC05 - Lập phiếu nhập kho.
    Luồng chính: kiểm tra -> lưu transaction -> tăng tồn -> ghi lịch sử (BR05, BR07).
    Toàn bộ thao tác trong 1 transaction: lỗi ở bất kỳ dòng nào -> rollback toàn bộ,
    không có chuyện tăng tồn một phần rồi bỏ dở (đáp ứng TC04).
    """
    if not items:
        raise InvalidQuantityError("Phiếu nhập phải có ít nhất một dòng hàng.")

    # Validate trước khi đụng vào DB, để fail sớm và rõ ràng.
    for item in items:
        if item.get("quantity", 0) <= 0:  # BR02
            raise InvalidQuantityError(
                f"Số lượng nhập phải > 0 (product_id={item.get('product_id')})."
            )

    try:
        receipt = models.Receipt(
            receipt_no=receipt_no or _generate_receipt_no(),
            supplier_id=supplier_id,
            receipt_date=datetime.utcnow(),
            created_by=created_by,
            status=models.DocStatusEnum.CONFIRMED.value,
        )
        db.add(receipt)
        db.flush()  # có receipt.id nhưng chưa commit - vẫn trong transaction

        for item in items:
            product = db.get(models.Product, item["product_id"])
            if product is None:
                raise ProductNotFoundError(f"Không tìm thấy hàng hóa id={item['product_id']}.")

            db.add(
                models.ReceiptItem(
                    receipt_id=receipt.id,
                    product_id=product.product_id,
                    quantity=item["quantity"],
                    unit_price=item.get("unit_price") if item.get("unit_price") is not None else product.purchase_price,
                )
            )

            inventory = db.get(models.Inventory, product.product_id)
            if inventory is None:
                inventory = models.Inventory(product_id=product.product_id, quantity_available=0)
                db.add(inventory)
                db.flush()

            inventory.quantity_available += item["quantity"]
            inventory.last_updated = datetime.utcnow()

            db.add(
                models.StockMovement(
                    product_id=product.product_id,
                    type=models.MovementTypeEnum.IMPORT.value,
                    ref_id=receipt.id,
                    quantity=item["quantity"],
                    balance_after=inventory.quantity_available,
                    created_at=datetime.utcnow(),
                    created_by=created_by,
                )
            )

        db.commit()
        db.refresh(receipt)
        return receipt

    except Exception:
        db.rollback()
        raise
