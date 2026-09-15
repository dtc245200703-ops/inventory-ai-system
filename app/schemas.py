from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal, Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]


class PricedItemResponse(BaseModel):
    quantity: int
    unit_price: Optional[Decimal] = None

    @computed_field
    @property
    def line_total(self) -> Optional[Decimal]:
        return None if self.unit_price is None else self.unit_price * self.quantity


class PricedDocumentResponse(BaseModel):
    @computed_field
    @property
    def total_amount(self) -> Optional[Decimal]:
        if any(item.line_total is None for item in self.items):
            return None
        return sum((item.line_total for item in self.items), Decimal('0'))


# =========================================================
# CẤU HÌNH CHUNG
# =========================================================

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =========================================================
# CATEGORY - DANH MỤC
# =========================================================

class CategoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    category_name: str = Field(min_length=1, max_length=100)


class CategoryResponse(ORMBase):
    category_id: int
    category_name: str


# =========================================================
# PRODUCT - SẢN PHẨM
# =========================================================

class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    product_code: str = Field(min_length=1, max_length=50)
    product_name: str = Field(min_length=1, max_length=200)
    category_id: Optional[int] = None
    unit: str = Field(min_length=1, max_length=20)
    min_stock_level: int = Field(default=10, ge=0)
    purchase_price: Optional[Money] = None
    sale_price: Optional[Money] = None


class ProductUpdate(BaseModel):
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    category_id: Optional[int] = None
    unit: Optional[str] = None
    min_stock_level: Optional[int] = None


class Product(ORMBase):
    product_id: int
    product_code: str
    product_name: str
    category_id: Optional[int] = None
    unit: str
    min_stock_level: int
    purchase_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None


class ProductDetail(Product):
    category_name: Optional[str] = None
    quantity_available: int
    stock_status: str
    last_updated: Optional[datetime] = None
    can_delete: bool
    deletion_reason: Optional[str] = None


# =========================================================
# INVENTORY - TỒN KHO
# =========================================================

class InventoryUpdate(BaseModel):
    quantity_available: int = Field(
        ge=0,
        description="Số lượng tồn kho không được âm"
    )


class InventoryResponse(ORMBase):
    product_id: int
    quantity_available: int
    last_updated: Optional[datetime] = None


# =========================================================
# USER - NGƯỜI DÙNG
# =========================================================

class UserCreate(BaseModel):
    username: str
    password_hash: str
    role: str
    is_active: int = 1


class UserResponse(ORMBase):
    id: int
    username: str
    role: str
    is_active: int


# =========================================================
# SUPPLIER - NHÀ CUNG CẤP
# =========================================================

class SupplierCreate(BaseModel):
    code: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class SupplierResponse(ORMBase):
    supplier_id: int
    code: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


# =========================================================
# RECEIPT ITEM - CHI TIẾT PHIẾU NHẬP
# =========================================================

class ReceiptItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: Optional[Money] = None


class ReceiptItemResponse(ORMBase, PricedItemResponse):
    id: int
    product_id: int
    quantity: int
    unit_price: Optional[Decimal] = None


# =========================================================
# RECEIPT - PHIẾU NHẬP
# =========================================================

class ReceiptCreate(BaseModel):
    supplier_id: int
    created_by: Optional[int] = Field(default=None, description="Bỏ qua: backend lấy người lập từ phiên đăng nhập")
    items: List[ReceiptItemCreate]


class ReceiptResponse(ORMBase, PricedDocumentResponse):
    id: int
    receipt_no: str
    supplier_id: int
    receipt_date: Optional[datetime] = None
    created_by: int
    status: str
    items: List[ReceiptItemResponse] = Field(default_factory=list)


# =========================================================
# ISSUE ITEM - CHI TIẾT PHIẾU XUẤT
# =========================================================

class IssueItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: Optional[Money] = None


class IssueItemResponse(ORMBase, PricedItemResponse):
    id: int
    product_id: int
    quantity: int


# =========================================================
# ISSUE - PHIẾU XUẤT
# =========================================================

class IssueCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    created_by: Optional[int] = Field(default=None, description="Bỏ qua: backend lấy người lập từ phiên đăng nhập")
    receiver: Optional[str] = Field(default=None, min_length=1, max_length=200)
    reason: Optional[str] = Field(default=None, min_length=1, max_length=255)
    items: List[IssueItemCreate]


class IssueResponse(ORMBase, PricedDocumentResponse):
    id: int
    issue_no: str
    issue_date: Optional[datetime] = None
    created_by: int
    status: str
    receiver: Optional[str] = None
    reason: Optional[str] = None
    items: List[IssueItemResponse] = Field(default_factory=list)


# =========================================================
# STOCK MOVEMENT - LỊCH SỬ BIẾN ĐỘNG KHO
# =========================================================

class StockMovementResponse(ORMBase):
    id: int
    product_id: int
    type: str
    ref_id: int
    quantity: int
    balance_after: int
    created_at: Optional[datetime] = None
    created_by: int


# =========================================================
# AI REPORT - BÁO CÁO AI
# =========================================================

class AIReportCreate(BaseModel):
    report_type: str
    period: str
    input_summary: str
    created_by: int


class AIReportResponse(ORMBase):
    id: int
    report_type: str
    period: str
    input_summary: str
    output_text: Optional[str] = None
    created_by: int
    created_at: Optional[datetime] = None
    # =========================================================
# AI - KẾT QUẢ PHÂN TÍCH
# =========================================================

class AIResultResponse(BaseModel):
    report_type: str
    result: str


class AIChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class AIChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    history: List[AIChatMessage] = Field(default_factory=list, max_length=10)
