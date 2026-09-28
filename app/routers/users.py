import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import admin_user, hash_password
from app.database import get_db
from app.models import AuthSession, User, UserEmail
from app.routers.auth import public_user

router = APIRouter(prefix="/users", tags=["Tài khoản"], dependencies=[Depends(admin_user)])


class AccountIdentity(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str | None = Field(default=None, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        return value.lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        if not value:
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Email không hợp lệ")
        return value


class AccountCreate(AccountIdentity):
    role: Literal["admin", "thu_kho", "ke_toan", "nhan_hang"]


class AccountUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Literal["admin", "thu_kho", "ke_toan", "nhan_hang"]
    is_active: bool
    password: str | None = Field(default=None, min_length=10, max_length=128)


def add_account(db, payload, *, is_active=True):
    identifiers = [payload.username] + ([payload.email] if payload.email else [])
    duplicate = db.query(User).outerjoin(UserEmail, User.id == UserEmail.user_id).filter(
        func.lower(User.username).in_(identifiers) | UserEmail.email.in_(identifiers)).first()
    if duplicate:
        raise HTTPException(409, "Tên đăng nhập hoặc email đã được sử dụng.")
    user = User(username=payload.username, full_name=payload.full_name, password_hash=hash_password(payload.password),
                role=payload.role, is_active=int(is_active))
    try:
        db.add(user)
        db.flush()
        if payload.email:
            db.add(UserEmail(user_id=user.id, email=payload.email))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tên đăng nhập hoặc email đã được sử dụng.")
    return user


@router.get("/")
def list_users(db: Session = Depends(get_db)):
    return [public_user(user, db) for user in db.query(User).order_by(User.id)]


@router.post("/", status_code=201)
def create_user(payload: AccountCreate, db: Session = Depends(get_db)):
    return public_user(add_account(db, payload), db)


@router.patch("/{user_id}")
def update_user(user_id: int, payload: AccountUpdate, actor=Depends(admin_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Không tìm thấy tài khoản.")
    if actor.id == user_id and (payload.role != "admin" or not payload.is_active):
        raise HTTPException(400, "Không thể tự khóa hoặc hạ quyền tài khoản đang sử dụng.")
    if payload.full_name is not None:
        user.full_name = payload.full_name
    user.role, user.is_active = payload.role, int(payload.is_active)
    if payload.password:
        user.password_hash = hash_password(payload.password)
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()
    db.commit()
    return public_user(user, db)
