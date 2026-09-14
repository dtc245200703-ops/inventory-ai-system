"""Interactive initial admin creation; no built-in or command-line password."""
from getpass import getpass

from app.database import engine, SessionLocal
from app.models import Base, User
from app.routers.users import AccountCreate, add_account


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(User).filter(User.role == "admin", User.is_active == 1,
                                 User.password_hash.like("pbkdf2_sha256$%" )).first():
            raise SystemExit("An active admin already exists. Manage accounts after signing in.")
        username = input("Admin username: ").strip()
        email = input("Email (optional): ").strip() or None
        password = getpass("Password (at least 10 characters): ")
        if password != getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")
        payload = AccountCreate(username=username, email=email, password=password, role="admin")
        user = add_account(db, payload)
        print(f"Admin created: {user.username}. Open /login to sign in.")


if __name__ == "__main__":
    main()
