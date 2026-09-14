import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db


# =========================================================
# DATABASE RIÊNG CHO TEST
# KHÔNG ĐỤNG VÀO inventory.db THẬT
# =========================================================

TEST_DATABASE_URL = "sqlite://"


test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False
    },
    poolclass=StaticPool
)


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


# =========================================================
# RESET DATABASE SAU MỖI TEST
# =========================================================

@pytest.fixture(autouse=True)
def reset_database():

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


# =========================================================
# DATABASE SESSION
# =========================================================

@pytest.fixture
def db():

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()


# =========================================================
# FASTAPI TEST CLIENT
# =========================================================

@pytest.fixture
def client(db):

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()