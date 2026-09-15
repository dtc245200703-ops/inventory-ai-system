from calendar import monthrange
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import report_user
from app.routers.reports import build_report

from app.services.ai_service import (
    generate_inventory_report,
    generate_restock_suggestion,
    generate_anomaly_summary,
    generate_chat_reply,
)


router = APIRouter(
    prefix="/ai", dependencies=[Depends(report_user)],
    tags=["Trợ lý AI"]
)


@router.post("/chat", response_model=schemas.AIResultResponse)
def ai_chat(payload: schemas.AIChatRequest, db: Session = Depends(get_db)):
    data = build_inventory_ai_data(db)
    try:
        result = generate_chat_reply(
            data, payload.message, [item.model_dump() for item in payload.history]
        )
        return {"report_type": "chat", "result": result}
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        raise HTTPException(503, "Không thể kết nối AI lúc này. Vui lòng thử lại sau.") from error


# =========================================================
# TỔNG HỢP DỮ LIỆU KHO TRƯỚC KHI GỬI GEMINI
# =========================================================

def build_inventory_ai_data(db: Session, start=None, end=None):

    products = db.query(models.Product).all()

    result = []

    thirty_days_ago = start or datetime.now() - timedelta(days=30)

    for product in products:

        # -------------------------------------------------
        # Lấy tồn kho hiện tại
        # -------------------------------------------------

        inventory = (
            db.query(models.Inventory)
            .filter(
                models.Inventory.product_id
                == product.product_id
            )
            .first()
        )

        if inventory:
            current_stock = inventory.quantity_available
        else:
            current_stock = 0

        # -------------------------------------------------
        # Tổng số lượng xuất trong 30 ngày
        # -------------------------------------------------

        export_query = db.query(
                func.coalesce(
                    func.sum(models.StockMovement.quantity),
                    0
                )
            ).filter(
                models.StockMovement.product_id
                == product.product_id,
                models.StockMovement.type
                == models.MovementTypeEnum.EXPORT.value,
                models.StockMovement.created_at
                >= thirty_days_ago
            )
        if end is not None:
            export_query = export_query.filter(models.StockMovement.created_at < end)
        export_30_days = export_query.scalar()

        export_30_days = int(export_30_days or 0)

        # -------------------------------------------------
        # Kiểm tra dưới mức tồn tối thiểu
        # -------------------------------------------------

        below_minimum = (
            current_stock <= product.min_stock_level
        )

        shortage = max(
            product.min_stock_level - current_stock,
            0
        )

        # -------------------------------------------------
        # Dữ liệu sạch gửi AI
        # KHÔNG gửi unit_price
        # -------------------------------------------------

        result.append(
            {
                "product_id": product.product_id,
                "product_code": product.product_code,
                "product_name": product.product_name,
                "unit": product.unit,
                "quantity_available": current_stock,
                "min_stock_level": product.min_stock_level,
                "export_30_days": export_30_days,
                "below_minimum": below_minimum,
                "shortage": shortage,
            }
        )

    return result


# =========================================================
# 1. XEM DỮ LIỆU TRƯỚC KHI GỬI AI
# =========================================================

@router.get(
    "/data",
    summary="Xem dữ liệu gửi cho AI",
    description=(
        "Hiển thị dữ liệu kho đã được backend tổng hợp "
        "trước khi gửi cho Gemini. "
        "Không bao gồm giá mua."
    )
)
def get_ai_data(
    db: Session = Depends(get_db)
):

    data = build_inventory_ai_data(db)

    return {
        "total_products": len(data),
        "data": data
    }


# =========================================================
# 2. GEMINI SINH BÁO CÁO KHO
# =========================================================

@router.post(
    "/inventory-report",
    response_model=schemas.AIResultResponse,
    summary="AI sinh báo cáo nhập xuất tồn",
    description=(
        "Gemini phân tích dữ liệu kho do backend tổng hợp "
        "và sinh báo cáo ngắn. "
        "AI không được thay đổi dữ liệu kho."
    )
)
def ai_inventory_report(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db)
):
    if (month is None) != (year is None):
        raise HTTPException(422, "Tháng/năm báo cáo không hợp lệ.")
    start = datetime(year, month, 1) if month is not None else None
    end = start + timedelta(days=monthrange(year, month)[1]) if start else None
    data = build_report(db, "month", date(year, month, 1)) if start else build_inventory_ai_data(db)

    if not data:
        return {
            "report_type": "inventory_report",
            "result": "Không có dữ liệu tồn kho để tạo báo cáo."
        }

    try:

        result = generate_inventory_report(data)

        return {
            "report_type": "inventory_report",
            "result": result
        }

    except FileNotFoundError as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    except RuntimeError as e:

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi gọi Gemini: {str(e)}"
        )


# =========================================================
# 3. GEMINI GỢI Ý NHẬP HÀNG
# =========================================================

@router.post(
    "/restock-suggestion",
    response_model=schemas.AIResultResponse,
    summary="AI gợi ý nhập hàng",
    description=(
        "Gemini phân tích tồn hiện tại, tồn tối thiểu "
        "và lượng xuất 30 ngày để đưa ra khuyến nghị."
    )
)
def ai_restock_suggestion(
    db: Session = Depends(get_db)
):

    data = build_inventory_ai_data(db)

    if not data:
        return {
            "report_type": "restock_suggestion",
            "result": "Không có dữ liệu để gợi ý nhập hàng."
        }

    try:

        result = generate_restock_suggestion(data)

        return {
            "report_type": "restock_suggestion",
            "result": result
        }

    except FileNotFoundError as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    except RuntimeError as e:

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi gọi Gemini: {str(e)}"
        )


# =========================================================
# 4. GEMINI PHÂN TÍCH BẤT THƯỜNG
# =========================================================

@router.post(
    "/anomaly-summary",
    response_model=schemas.AIResultResponse,
    summary="AI phân tích biến động bất thường",
    description=(
        "Gemini phân tích các dấu hiệu như tồn thấp, "
        "hết hàng hoặc lượng xuất đáng chú ý."
    )
)
def ai_anomaly_summary(
    db: Session = Depends(get_db)
):

    today = datetime.now().date()
    start = datetime.combine(today - timedelta(days=29), datetime.min.time())
    movements = db.query(models.StockMovement).filter(
        models.StockMovement.type == models.MovementTypeEnum.EXPORT.value,
        models.StockMovement.created_at >= start).all()
    daily = {(today - timedelta(days=offset)).isoformat(): 0 for offset in range(29, -1, -1)}
    for movement in movements:
        key = movement.created_at.date().isoformat()
        if key in daily:
            daily[key] += movement.quantity
    previous = list(daily.values())[:-1]
    issues = db.query(models.Issue).filter(models.Issue.issue_date >= datetime.combine(today, datetime.min.time())).all()
    data = {"daily_exports": [{"date": key, "quantity": value} for key, value in daily.items()],
            "average_previous_29_days": sum(previous) / len(previous) if previous else 0,
            "today_export": list(daily.values())[-1],
            "today_issues": [{"issue_no": issue.issue_no,
                "total_quantity": sum(item.quantity for item in issue.items)} for issue in issues],
            "inventory": build_inventory_ai_data(db)}

    if not data:
        return {
            "report_type": "inventory_anomaly",
            "result": "Không có dữ liệu để phân tích biến động."
        }

    try:

        result = generate_anomaly_summary(data)

        return {
            "report_type": "inventory_anomaly",
            "result": result
        }

    except FileNotFoundError as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    except RuntimeError as e:

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi gọi Gemini: {str(e)}"
        )
