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

    password_confirmation: str = Field(
        min_length=10,
        max_length=128
    )

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.password_confirmation:
            raise ValueError("Mật khẩu xác nhận không khớp.")
        return self


def needs_initial_admin(db: Session):
    """
    Kiểm tra hệ thống đã có tài khoản quản trị viên thật hay chưa.

    Các tài khoản seed/system_audit cũ không được tính là admin đăng nhập.
    """
    return (
        db.query(User)
        .filter(
            User.role == "admin",
            User.password_hash.startswith("pbkdf2_sha256$")
        )
        .first()
        is None
    )


@router.post("/register", status_code=201)
def register(
    payload: RegistrationInput,
    request: Request,
    db: Session = Depends(get_db)
):
    # Chỉ cho phép yêu cầu đăng ký từ giao diện của ứng dụng
    if request.headers.get("X-Requested-With") != "inventory-app":
        raise HTTPException(
            status_code=403,
            detail="Yêu cầu đăng ký không hợp lệ."
        )

    # Hỗ trợ cả SQLite và PostgreSQL
    dialect = db.get_bind().dialect.name

    try:
        # Khóa transaction để tránh trường hợp hai người cùng lúc
        # đều trở thành admin đầu tiên.
        if dialect == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))

        elif dialect == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(20260914)")
            )

        else:
            raise HTTPException(
                status_code=503,
                detail="Cơ sở dữ liệu hiện tại chưa được hỗ trợ."
            )

        # Tạo khóa giới hạn đăng ký theo IP
        client_ip = (
            request.client.host
            if request.client
            else "unknown"
        )

        key = hashlib.sha256(
            ("register:" + client_ip).encode()
        ).hexdigest()

        now = datetime.utcnow()

        throttle = db.get(LoginThrottle, key)

        # Giới hạn tối đa 10 lần đăng ký / giờ
        if (
            throttle
            and throttle.expires_at > now
            and throttle.failures >= 10
        ):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Đã đạt giới hạn đăng ký. "
                    "Vui lòng thử lại sau một giờ."
                )
            )

        # Chưa có bản ghi giới hạn
        if throttle is None:
            throttle = LoginThrottle(
                key=key,
                failures=0,
                expires_at=now + timedelta(hours=1)
            )
            db.add(throttle)

        # Hết thời gian giới hạn thì reset
        elif throttle.expires_at <= now:
            throttle.failures = 0
            throttle.expires_at = now + timedelta(hours=1)

        throttle.failures += 1

        # Kiểm tra đây có phải tài khoản đầu tiên hay không
        first = needs_initial_admin(db)

        account = AccountCreate(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            role="admin" if first else "ke_toan"
        )

        # Admin đầu tiên được kích hoạt ngay
        user = add_account(
            db,
            account,
            is_active=first
        )

        return {
            "username": user.username,
            "requires_approval": not first,
            "message": (
                "Đăng ký quản trị viên thành công. "
                "Bạn có thể đăng nhập ngay."
                if first
                else
                "Đăng ký thành công. "
                "Vui lòng chờ quản trị viên kích hoạt "
                "và phân quyền trước khi đăng nhập."
            )
        }

    except Exception:
        db.rollback()
        raise