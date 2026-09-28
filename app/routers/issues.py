from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.auth import current_user, warehouse_user
from app.exceptions import InsufficientStockError, InvalidQuantityError, ProductNotFoundError
from app.services.issue_service import create_issue as create_issue_service
from app.services.catalog_service import lock_catalog

router = APIRouter(
    prefix="/issues", dependencies=[Depends(current_user)],
    tags=["Phiếu xuất kho"]
)


@router.get(
    "/",
    response_model=List[schemas.IssueResponse],
    summary="Lấy danh sách phiếu xuất",
    description="Truy xuất toàn bộ phiếu xuất kho đã lập."
)
def get_all_issues(db: Session = Depends(get_db)):
    return db.query(models.Issue).all()


@router.get(
    "/{issue_id}",
    response_model=schemas.IssueResponse,
    summary="Xem chi tiết phiếu xuất",
)
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.get(models.Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu xuất")
    return issue


@router.post(
    "/",
    response_model=schemas.IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lập phiếu xuất kho",
    description=(
        "UC06 - Kiểm tra đủ tồn cho TẤT CẢ dòng hàng trước khi trừ bất kỳ dòng nào. "
        "Nếu bất kỳ dòng nào vượt tồn hiện tại, từ chối toàn bộ phiếu (BR04) và trả về "
        "409 Conflict thay vì tạo phiếu xuất một phần."
    ),
)
def create_new_issue(payload: schemas.IssueCreate, db: Session = Depends(get_db), user=Depends(warehouse_user)):
    lock_catalog(db)
    try:
        issue = create_issue_service(
            db,
            created_by=user.id,
            items=[item.model_dump() for item in payload.items],
            reason=payload.reason,
            receiver=payload.receiver,
        )
        return issue
    except InsufficientStockError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvalidQuantityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProductNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
