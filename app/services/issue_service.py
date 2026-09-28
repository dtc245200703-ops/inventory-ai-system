from datetime import datetime
from typing import List, Optional, TypedDict

from sqlalchemy.orm import Session

from app import models
from app.exceptions import InsufficientStockError, InvalidQuantityError, ProductNotFoundError


class IssueItemInput(TypedDict, total=False):
    product_id: int
    quantity: int
    unit_price: Optional[float]


def _generate_issue_no() -> str:
    return f"PX{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"


def create_issue(
    db: Session,
    created_by: int,
    items: List[IssueItemInput],
    reason: Optional[str] = None,
    receiver: Optional[str] = None,
    issue_no: Optional[str] = None,
    commit: bool = True,
) -> models.Issue:
    """
    UC06 - Lập phiếu xuất kho.
    Luồng chính: kiểm tra tồn -> lưu phiếu -> trừ tồn -> ghi lịch sử -> commit (BR04, BR05, BR07).
    Ngoại lệ: nếu BẤT KỲ dòng nào vượt tồn hiện tại -> từ chối toàn bộ phiếu, không xuất
    một phần (đáp ứng TC03: tồn phải giữ nguyên, không tạo phiếu chốt).
    """
    if not items:
        raise InvalidQuantityError("Phiếu xuất phải có ít nhất một dòng hàng.")

    for item in items:
        if item.get("quantity", 0) <= 0:  # BR02
            raise InvalidQuantityError(
                f"Số lượng xuất phải > 0 (product_id={item.get('product_id')})."
            )

    # Validate the total for duplicate product lines, including direct API calls.
    totals = {}
    for item in items:
        product_id = item["product_id"]
        totals[product_id] = totals.get(product_id, 0) + item["quantity"]

    try:
        # Bước 1: kiểm tra đủ tồn cho TẤT CẢ dòng hàng trước khi ghi bất kỳ thay đổi nào.
        # Trong Postgres, .with_for_update() khóa các dòng inventory liên quan để tránh
        # race condition khi có 2 phiếu xuất cùng lúc trừ vào cùng 1 sản phẩm.
        # SQLite (dùng cho demo/test) không hỗ trợ khóa dòng thật sự - with_for_update()
        # sẽ bị bỏ qua, chấp nhận được cho môi trường single-writer của demo này.
        inventories = {}
        prices = {}
        for item in [{"product_id": pid, "quantity": qty} for pid, qty in sorted(totals.items())]:
            product = db.get(models.Product, item["product_id"])
            if product is None:
                raise ProductNotFoundError(f"Không tìm thấy hàng hóa id={item['product_id']}.")

            inventory = (
                db.query(models.Inventory)
                .filter(models.Inventory.product_id == product.product_id)
                .with_for_update()
                .one_or_none()
            )
            if inventory is None:
                inventory = models.Inventory(product_id=product.product_id, quantity_available=0)
                db.add(inventory)  # đăng ký vào session ngay, tránh add trùng ở bước 2

            if inventory.quantity_available < item["quantity"]:  # BR04
                raise InsufficientStockError(
                    product_code=product.product_code,
                    requested=item["quantity"],
                    available=inventory.quantity_available,
                )
            inventories[product.product_id] = inventory
            prices[product.product_id] = product.sale_price

        # Bước 2: mọi dòng đều đủ tồn -> tiến hành ghi phiếu và trừ kho.
        issue = models.Issue(
            issue_no=issue_no or _generate_issue_no(),
            issue_date=datetime.utcnow(),
            created_by=created_by,
            status=models.DocStatusEnum.CONFIRMED.value,
            reason=reason,
            receiver=receiver,
        )
        db.add(issue)
        db.flush()

        for item in items:
            db.add(
                models.IssueItem(
                    issue_id=issue.id,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    unit_price=item.get("unit_price") if item.get("unit_price") is not None else prices[item["product_id"]],
                )
            )

            inventory = inventories[item["product_id"]]
            inventory.quantity_available -= item["quantity"]
            inventory.last_updated = datetime.utcnow()

            db.add(
                models.StockMovement(
                    product_id=item["product_id"],
                    type=models.MovementTypeEnum.EXPORT.value,
                    ref_id=issue.id,
                    quantity=item["quantity"],
                    balance_after=inventory.quantity_available,
                    created_at=datetime.utcnow(),
                    created_by=created_by,
                )
            )

        if commit:
            db.commit()
            db.refresh(issue)
        else:
            db.flush()
        return issue

    except Exception:
        db.rollback()
        raise
