import hashlib
import hmac
import os
import secrets
from datetime import datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User

COOKIE_NAME = "inventory_session"
ROLE_LABELS = {"admin": "Quản trị viên", "thu_kho": "Thủ kho", "ke_toan": "Kế toán", "nhan_hang": "Nhãn hàng / Đối tác"}
STAFF_ROLES = {"admin", "thu_kho", "ke_toan"}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 100000 <= int(rounds) <= 2000000:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


def optional_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    session = db.get(AuthSession, token_hash(token)) if token else None
    if session is None or session.expires_at <= datetime.utcnow():
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active or user.role not in ROLE_LABELS:
        return None
    request.state.auth_session = session
    return user


def authenticated_user(request: Request, user=Depends(optional_user)):
    if user is None:
        raise HTTPException(401, "Vui lòng đăng nhập lại.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(csrf, request.state.auth_session.csrf_token):
            raise HTTPException(403, "Phiên xác nhận không hợp lệ. Hãy tải lại trang.")
    return user


def current_user(user=Depends(authenticated_user)):
    """Existing warehouse routes are internal; partners use explicitly scoped routes."""
    if user.role not in STAFF_ROLES:
        raise HTTPException(403, "Tài khoản nhãn hàng chỉ được truy cập dữ liệu của mình.")
    return user


def require_roles(*roles):
    def dependency(user=Depends(authenticated_user)):
        if user.role not in roles:
            raise HTTPException(403, "Bạn không có quyền thực hiện thao tác này.")
        return user
    return dependency


warehouse_user = require_roles("admin", "thu_kho")
report_user = require_roles("admin", "ke_toan")
admin_user = require_roles("admin")
