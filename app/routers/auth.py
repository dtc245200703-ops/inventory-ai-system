import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import (COOKIE_NAME, cookie_secure, current_user, hash_password,
                      token_hash, verify_password)
from app.database import get_db
from app.models import AuthSession, LoginThrottle, User, UserEmail

router = APIRouter(prefix="/auth", tags=["Đăng nhập"])
DUMMY_PASSWORD = hash_password(secrets.token_urlsafe(24))


class LoginInput(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


def public_user(user, db):
    email = db.get(UserEmail, user.id)
    return {"id": user.id, "username": user.username, "full_name": user.full_name,
            "email": email.email if email else None,
            "role": user.role, "is_active": bool(user.is_active)}


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    # A cross-origin HTML form cannot send this header; no permissive CORS is enabled.
    if request.headers.get("X-Requested-With") != "inventory-app":
        raise HTTPException(403, "Yêu cầu đăng nhập không hợp lệ.")
    now = datetime.utcnow()
    ip = request.client.host if request.client else "unknown"
    key = hashlib.sha256(ip.encode()).hexdigest()
    throttle = db.get(LoginThrottle, key)
    if throttle and throttle.expires_at > now and throttle.failures >= 20:
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Thử lại sau 15 phút.")
    identifier = payload.identifier.strip().lower()
    users = db.query(User).outerjoin(UserEmail, UserEmail.user_id == User.id).filter(
        (func.lower(User.username) == identifier) | (UserEmail.email == identifier)).all()
    user = users[0] if len(users) == 1 else None
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD)
    if not valid or not user or not user.is_active:
        if throttle is None:
            throttle = LoginThrottle(key=key, failures=0, expires_at=now + timedelta(minutes=15))
            db.add(throttle)
        elif throttle.expires_at <= now:
            throttle.failures = 0
            throttle.expires_at = now + timedelta(minutes=15)
        throttle.failures += 1
        db.commit()
        raise HTTPException(401, "Email/tên đăng nhập hoặc mật khẩu không đúng.")
    db.query(AuthSession).filter(AuthSession.expires_at <= now).delete()
    old = request.cookies.get(COOKIE_NAME)
    if old:
        db.query(AuthSession).filter(AuthSession.token_hash == token_hash(old)).delete()
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=token_hash(token), user_id=user.id,
                       csrf_token=secrets.token_hex(32), expires_at=now + timedelta(hours=8)))
    if throttle:
        db.delete(throttle)
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=cookie_secure(),
                        samesite="strict", max_age=8 * 3600, path="/")
    response.headers["Cache-Control"] = "no-store"
    return public_user(user, db)


@router.get("/me")
def me(request: Request, response: Response, user=Depends(current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return {**public_user(user, db), "csrf_token": request.state.auth_session.csrf_token}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user), db: Session = Depends(get_db)):
    db.delete(request.state.auth_session)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=cookie_secure(), httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
