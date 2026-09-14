from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import current_user, warehouse_user

router = APIRouter(
    prefix="/inventory", dependencies=[Depends(current_user)],
    tags=["Quản lý Tồn kho"]
)

@router.get(
    "/",
    response_model=List[schemas.InventoryResponse],
    summary="Lấy danh sách tồn kho",
    description="Truy xuất số lượng tồn kho của tất cả sản phẩm trong hệ thống."
)
def get_all_inventory(db: Session = Depends(get_db)):
    inventory_list = db.query(models.Inventory).all()
    return inventory_list


@router.get("/card/{product_id}")
def get_stock_card(product_id: int, db: Session = Depends(get_db)):
    if db.get(models.Product, product_id) is None:
        raise HTTPException(404, "Không tìm thấy sản phẩm")
    movements = (db.query(models.StockMovement).filter_by(product_id=product_id)
                 .order_by(models.StockMovement.created_at.desc(), models.StockMovement.id.desc()).all())
    return [{"id": row.id, "type": row.type, "ref_id": row.ref_id, "quantity": row.quantity,
             "balance_after": row.balance_after, "created_at": row.created_at, "created_by": row.created_by}
            for row in movements]

@router.get(
    "/{product_id}",
    response_model=schemas.InventoryResponse,
    summary="Xem tồn kho theo ID sản phẩm",
    description="Truy xuất số lượng tồn kho hiện tại của một sản phẩm cụ thể."
)
def get_inventory_by_product_id(product_id: int, db: Session = Depends(get_db)):
    # Kiểm tra sản phẩm có tồn tại không
    product = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

    inventory = db.query(models.Inventory).filter(models.Inventory.product_id == product_id).first()
    if not inventory:
        # Nếu chưa có bản ghi tồn kho, mặc định trả về số lượng là 0
        return models.Inventory(product_id=product_id, quantity_available=0)
    
    return inventory

@router.put(
    "/{product_id}",
    dependencies=[Depends(warehouse_user)],
    response_model=schemas.InventoryResponse,
    summary="Cập nhật số lượng tồn kho",
    description="Cập nhật lại số lượng tồn kho mới cho một sản phẩm."
)
def update_inventory(
    product_id: int, 
    inventory_data: schemas.InventoryUpdate, 
    db: Session = Depends(get_db),
    user=Depends(warehouse_user),
):
    # 1. Kiểm tra sản phẩm có tồn tại trong hệ thống không
    product = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

    # 2. Tìm bản ghi tồn kho tương ứng
    db_inventory = db.query(models.Inventory).filter(models.Inventory.product_id == product_id).first()

    old_quantity = db_inventory.quantity_available if db_inventory else 0
    if db_inventory:
        # Nếu đã có bản ghi -> Cập nhật số lượng mới
        db_inventory.quantity_available = inventory_data.quantity_available
    else:
        # Nếu chưa có bản ghi -> Tạo mới bản ghi tồn kho
        db_inventory = models.Inventory(
            product_id=product_id,
            quantity_available=inventory_data.quantity_available
        )
        db.add(db_inventory)
    difference = inventory_data.quantity_available - old_quantity
    if difference:
        db.add(models.StockMovement(product_id=product_id, type=models.MovementTypeEnum.ADJUSTMENT.value,
            ref_id=0, quantity=abs(difference), balance_after=inventory_data.quantity_available,
            created_at=datetime.utcnow(), created_by=user.id))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(db_inventory)
    return db_inventory
