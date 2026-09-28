import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Unit(Base):
    __tablename__ = "units"
    unit_id = Column(Integer, primary_key=True, autoincrement=True)
    unit_name = Column(String(20), nullable=False, unique=True)


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category_name = Column(String(100), nullable=False)

    products = relationship("Product", back_populates="category")

class Brand(Base):
    __tablename__ = "brands"
    brand_id = Column(Integer, primary_key=True, autoincrement=True)
    brand_name = Column(String(100), nullable=False, unique=True)


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_code = Column(String(50), unique=True, nullable=False, index=True)
    product_name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id"))
    brand_id = Column(Integer, ForeignKey("brands.brand_id"), nullable=True)
    unit = Column(String(20), nullable=False)
    min_stock_level = Column(Integer, default=10)
    purchase_price = Column(Numeric(14, 2), nullable=True)
    sale_price = Column(Numeric(14, 2), nullable=True)

    category = relationship("Category", back_populates="products")
    brand = relationship("Brand")
    inventory = relationship("Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan")

class Inventory(Base):
    __tablename__ = "inventory"

    product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
    quantity_available = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="inventory")
    import enum

# ---------------------------------------------------------------------------
# Enum dùng chung — lưu dạng String + CheckConstraint để chạy được cả SQLite
# ---------------------------------------------------------------------------
class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    THU_KHO = "thu_kho"
    KE_TOAN = "ke_toan"
    NHAN_HANG = "nhan_hang"


class DocStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class MovementTypeEnum(str, enum.Enum):
    IMPORT = "import"
    EXPORT = "export"
    ADJUSTMENT = "adjustment"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    full_name = Column(String(200), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    is_active = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            f"role IN ('{RoleEnum.ADMIN.value}', '{RoleEnum.THU_KHO.value}', '{RoleEnum.KE_TOAN.value}', '{RoleEnum.NHAN_HANG.value}')",
            name="ck_users_role_valid",
        ),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(String(255))

    receipts = relationship("Receipt", back_populates="supplier")


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_no = Column(String(50), nullable=False, unique=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=False)
    receipt_date = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default=DocStatusEnum.DRAFT.value)

    __table_args__ = (
        CheckConstraint(
            f"status IN ('{DocStatusEnum.DRAFT.value}', '{DocStatusEnum.CONFIRMED.value}', "
            f"'{DocStatusEnum.CANCELLED.value}')",
            name="ck_receipts_status_valid",
        ),
    )

    supplier = relationship("Supplier", back_populates="receipts")
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=True)  # giá mua - không gửi cho AI

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_receipt_items_qty_positive"),
    )

    receipt = relationship("Receipt", back_populates="items")
    product = relationship("Product")


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    issue_no = Column(String(50), nullable=False, unique=True)
    issue_date = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default=DocStatusEnum.DRAFT.value)
    reason = Column(String(255), nullable=True)
    receiver = Column(String(200), nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"status IN ('{DocStatusEnum.DRAFT.value}', '{DocStatusEnum.CONFIRMED.value}', "
            f"'{DocStatusEnum.CANCELLED.value}')",
            name="ck_issues_status_valid",
        ),
    )

    items = relationship("IssueItem", back_populates="issue", cascade="all, delete-orphan")


class IssueItem(Base):
    __tablename__ = "issue_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_issue_items_qty_positive"),
    )

    issue = relationship("Issue", back_populates="items")
    product = relationship("Product")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    type = Column(String(20), nullable=False)
    ref_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"type IN ('{MovementTypeEnum.IMPORT.value}', '{MovementTypeEnum.EXPORT.value}', "
            f"'{MovementTypeEnum.ADJUSTMENT.value}')",
            name="ck_stock_movements_type_valid",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movements_qty_positive"),
        CheckConstraint("balance_after >= 0", name="ck_stock_movements_balance_non_negative"),
    )

    product = relationship("Product")


class AIReport(Base):
    __tablename__ = "ai_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    report_type = Column(String(50), nullable=False)
    period = Column(String(20), nullable=False)
    input_summary = Column(Text, nullable=False)
    output_text = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class UserEmail(Base):
    """Separate table keeps existing users databases compatible without ALTER."""
    __tablename__ = "user_emails"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    email = Column(String(254), unique=True, nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    csrf_token = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key = Column(String(64), primary_key=True)
    failures = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False)


class PartnerRequest(Base):
    __tablename__ = 'partner_requests'
    id = Column(Integer, primary_key=True)
    requested_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    status = Column(String(20), nullable=False, default='pending')
    note = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    reviewed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(String(1000), nullable=True)
    issue_id = Column(Integer, ForeignKey('issues.id'), nullable=True, unique=True)
    requester = relationship('User', foreign_keys=[requested_by])
    reviewer = relationship('User', foreign_keys=[reviewed_by])
    issue = relationship('Issue')
    items = relationship('PartnerRequestItem', cascade='all, delete-orphan')
    __table_args__ = (CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='ck_partner_request_status'),)


class PartnerRequestItem(Base):
    __tablename__ = 'partner_request_items'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('partner_requests.id'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.product_id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    product = relationship('Product')
    __table_args__ = (CheckConstraint('quantity > 0', name='ck_partner_request_quantity'),)
