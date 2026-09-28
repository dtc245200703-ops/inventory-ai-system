from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from app import models, schemas
from app.auth import admin_user, require_roles
from app.database import get_db
from app.exceptions import InsufficientStockError, ProductNotFoundError, InvalidQuantityError
from app.services.catalog_service import lock_catalog
from app.services.issue_service import create_issue

portal_user = require_roles('admin', 'nhan_hang')
partner_user = require_roles('nhan_hang')
router = APIRouter(prefix='/partner-requests', tags=['Yêu cầu nhãn hàng'], dependencies=[Depends(portal_user)])


class RequestItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=1000000000, strict=True)


class RequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    note: str | None = Field(default=None, max_length=1000)
    items: list[RequestItem] = Field(min_length=1, max_length=100)


class Review(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    decision: Literal['approve', 'reject']
    note: str | None = Field(default=None, max_length=1000)


def request_query(db):
    return db.query(models.PartnerRequest).options(
        joinedload(models.PartnerRequest.requester), joinedload(models.PartnerRequest.reviewer),
        selectinload(models.PartnerRequest.items).joinedload(models.PartnerRequestItem.product),
        joinedload(models.PartnerRequest.issue).selectinload(models.Issue.items))


def describe(row):
    return {'id': row.id, 'requested_by': row.requested_by,
            'partner_name': row.requester.full_name or row.requester.username,
            'status': row.status, 'note': row.note, 'created_at': row.created_at,
            'reviewed_at': row.reviewed_at, 'review_note': row.review_note,
            'reviewed_by': row.reviewer.full_name or row.reviewer.username if row.reviewer else None,
            'items': [{'product_id': i.product_id, 'product_code': i.product.product_code,
                       'product_name': i.product.product_name, 'unit': i.product.unit, 'quantity': i.quantity}
                      for i in row.items],
            'issue': schemas.IssueResponse.model_validate(row.issue).model_dump() if row.issue else None}


@router.get('/products')
def available_products(db: Session = Depends(get_db)):
    # A selectable catalog, not the internal stock list or purchase prices.
    return [{'product_id': p.product_id, 'product_code': p.product_code,
             'product_name': p.product_name, 'unit': p.unit}
            for p in db.query(models.Product).order_by(models.Product.product_code)]


@router.get('/')
def list_requests(user=Depends(portal_user), db: Session = Depends(get_db)):
    query = request_query(db)
    if user.role == 'nhan_hang':
        query = query.filter(models.PartnerRequest.requested_by == user.id)
    return [describe(r) for r in query.order_by(models.PartnerRequest.created_at.desc(), models.PartnerRequest.id.desc())]


@router.get('/{request_id}')
def get_request(request_id: int, user=Depends(portal_user), db: Session = Depends(get_db)):
    query = request_query(db).filter(models.PartnerRequest.id == request_id)
    if user.role == 'nhan_hang':
        query = query.filter(models.PartnerRequest.requested_by == user.id)
    row = query.first()
    if row is None:
        raise HTTPException(404, 'Không tìm thấy yêu cầu.')
    return describe(row)


@router.post('/', status_code=201)
def submit_request(payload: RequestCreate, user=Depends(partner_user), db: Session = Depends(get_db)):
    totals = {}
    for item in payload.items:
        totals[item.product_id] = totals.get(item.product_id, 0) + item.quantity
    if any(q > 1000000000 for q in totals.values()):
        raise HTTPException(422, 'Số lượng yêu cầu vượt giới hạn.')
    found = {p.product_id for p in db.query(models.Product).filter(models.Product.product_id.in_(totals))}
    if found != set(totals):
        raise HTTPException(404, 'Có hàng hóa không còn trong danh mục. Vui lòng tải lại trang.')
    row = models.PartnerRequest(requested_by=user.id, note=payload.note,
        items=[models.PartnerRequestItem(product_id=pid, quantity=qty) for pid, qty in sorted(totals.items())])
    db.add(row)
    db.commit()
    return describe(request_query(db).filter_by(id=row.id).one())


@router.post('/{request_id}/review')
def review_request(request_id: int, payload: Review, actor=Depends(admin_user), db: Session = Depends(get_db)):
    actor_id = actor.id
    lock_catalog(db)  # SQLite serializes approvals before reading the pending status.
    try:
        row = db.query(models.PartnerRequest).filter_by(id=request_id).with_for_update().populate_existing().first()
        if row is None:
            raise HTTPException(404, 'Không tìm thấy yêu cầu.')
        if row.status != 'pending':
            raise HTTPException(409, 'Yêu cầu đã được xét duyệt. Vui lòng tải lại danh sách.')
        if payload.decision == 'reject' and not payload.note:
            raise HTTPException(422, 'Vui lòng nhập lý do từ chối.')
        if payload.decision == 'approve':
            requester = db.get(models.User, row.requested_by)
            if not requester.is_active or requester.role != 'nhan_hang':
                raise HTTPException(409, 'Tài khoản nhãn hàng đã khóa hoặc đổi vai trò; không thể duyệt xuất.')
            issue = create_issue(db, created_by=actor_id,
                items=[{'product_id': i.product_id, 'quantity': i.quantity} for i in row.items],
                receiver=requester.full_name or requester.username,
                reason=f'Duyệt yêu cầu nhãn hàng YC{row.id}', commit=False)
            row.issue_id = issue.id
            row.status = 'approved'
        else:
            row.status = 'rejected'
        row.reviewed_by, row.reviewed_at, row.review_note = actor_id, datetime.utcnow(), payload.note
        db.commit()
        return describe(request_query(db).filter_by(id=request_id).one())
    except (InsufficientStockError, ProductNotFoundError, InvalidQuantityError) as error:
        db.rollback()
        raise HTTPException(409, str(error)) from error
    except Exception:
        db.rollback()
        raise
