import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LoginThrottle, User
from app.routers.users import AccountIdentity, AccountCreate, add_account

router = APIRouter(prefix="/auth", tags=["Đăng ký"])


class RegistrationInput(AccountIdentity):
    model_config = ConfigDict(extra="forbid")
    password_confirmation: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.password_confirmation:
            raise ValueError("Mật khẩu xác nhận không khớp.")
        return self


def needs_initial_admin(db):
    # Legacy system_audit/seed users cannot log in. Disabled real admins still
    # count, so locking an admin never reopens public admin registration.
    return db.query(User).filter(User.role == "admin",
        User.password_hash.startswith("pbkdf2_sha256$")).first() is None


@router.post("/register", status_code=201)
def register(payload: RegistrationInput, request: Request, db: Session = Depends(get_db)):
    if request.headers.get("X-Requested-With") != "inventory-app":
        raise HTTPException(403, "Yêu cầu đăng ký không hợp lệ.")
    if db.get_bind().dialect.name != "sqlite":
        raise HTTPException(503, "Đăng ký hiện hỗ trợ cơ sở dữ liệu SQLite.")
    # Serialize first-admin election and insert in the same transaction.
    # Two simultaneous submissions must not both become administrators.
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        key = hashlib.sha256(('register:' + (request.client.host if request.client else 'unknown')).encode()).hexdigest()
        now = datetime.utcnow()
        throttle = db.get(LoginThrottle, key)
        if throttle and throttle.expires_at > now and throttle.failures >= 10:
            raise HTTPException(429, "Đã đạt giới hạn đăng ký. Vui lòng thử lại sau một giờ.")
        if throttle is None:
            throttle = LoginThrottle(key=key, failures=0, expires_at=now + timedelta(hours=1))
            db.add(throttle)
        elif throttle.expires_at <= now:
            throttle.failures = 0
            throttle.expires_at = now + timedelta(hours=1)
        throttle.failures += 1
        first = needs_initial_admin(db)
        account = AccountCreate(username=payload.username, email=payload.email,
                                password=payload.password, role="admin" if first else "ke_toan")
        user = add_account(db, account, is_active=first)
        return {"username": user.username, "requires_approval": not first,
                "message": "Đăng ký quản trị viên thành công. Bạn có thể đăng nhập ngay."
                if first else "Đăng ký thành công. Vui lòng chờ quản trị viên kích hoạt và phân quyền trước khi đăng nhập."}
    except Exception:
        db.rollback()
        raise
