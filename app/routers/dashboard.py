from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import current_user
from app.database import get_db
from app.models import Inventory, Product, StockMovement, Receipt, Issue

router = APIRouter(prefix="/dashboard", tags=["Thống kê"], dependencies=[Depends(current_user)])
LOCAL_TZ = timezone(timedelta(hours=7))


def local_date(value):
    # Stored document/movement timestamps use naive UTC.
    return value.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)


def build_dashboard(db, period, stale_days, now=None):
    now = now or datetime.now(LOCAL_TZ)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start + timedelta(days=32)).replace(day=1)
    utc_start = month_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = month_end.astimezone(timezone.utc).replace(tzinfo=None)
    if period == "day":
        labels = [(month_start + timedelta(days=i)).strftime("%Y-%m-%d")
                  for i in range(monthrange(now.year, now.month)[1])]
        start = month_start
    else:
        index = now.year * 12 + now.month - 1
        labels = [f"{i // 12:04d}-{i % 12 + 1:02d}" for i in range(index - 11, index + 1)]
        start = datetime.strptime(labels[0], "%Y-%m").replace(tzinfo=LOCAL_TZ)
    series = {label: {"label": label, "import": 0, "export": 0} for label in labels}
    top = {}
    movements = db.query(StockMovement).filter(
        StockMovement.created_at >= start.astimezone(timezone.utc).replace(tzinfo=None),
        StockMovement.created_at <= now.astimezone(timezone.utc).replace(tzinfo=None),
        StockMovement.type.in_(["import", "export"])).all()
    for movement in movements:
        date = local_date(movement.created_at)
        key = date.strftime("%Y-%m-%d" if period == "day" else "%Y-%m")
        if key in series:
            series[key][movement.type] += movement.quantity
            if movement.type == "export":
                top[movement.product_id] = top.get(movement.product_id, 0) + movement.quantity
    history = {row.product_id: row for row in db.query(
        StockMovement.product_id, func.min(StockMovement.created_at).label("first_seen")
    ).group_by(StockMovement.product_id)}
    exports = dict(db.query(StockMovement.product_id, func.max(StockMovement.created_at))
                   .filter(StockMovement.type == "export").group_by(StockMovement.product_id).all())
    products = db.query(Product).order_by(Product.product_code).all()
    inventories = {row.product_id: row for row in db.query(Inventory)}
    rows, low, stale = [], [], []
    unknown_age = 0
    for product in products:
        inventory = inventories.get(product.product_id)
        quantity = inventory.quantity_available if inventory else 0
        first_seen = history.get(product.product_id)
        basis = exports.get(product.product_id) or (first_seen.first_seen if first_seen else None)
        age = max(0, (now.date() - local_date(basis).date()).days) if basis else None
        if quantity > 0 and age is None:
            unknown_age += 1
        row = {"product_id": product.product_id, "product_code": product.product_code,
               "product_name": product.product_name, "unit": product.unit,
               "quantity_available": quantity, "min_stock_level": product.min_stock_level or 0,
               "inactive_days": age, "last_export": exports.get(product.product_id),
               "below_minimum": quantity < (product.min_stock_level or 0)}
        rows.append(row)
        if row["below_minimum"]:
            low.append(row)
        if quantity > 0 and age is not None and age >= stale_days:
            stale.append(row)
    product_map = {row["product_id"]: row for row in rows}
    ranking = [{**product_map[pid], "export_quantity": qty} for pid, qty in
               sorted(top.items(), key=lambda item: (-item[1], item[0]))[:5] if pid in product_map]
    def count_documents(model, date_column):
        return db.query(model).filter(model.status == "confirmed", date_column >= utc_start,
                                      date_column < utc_end).count()
    return {"summary": {"total_products": len(rows), "total_stock": sum(r["quantity_available"] for r in rows),
                        "low_stock": len(low), "stale_stock": len(stale),
                        "receipts_this_month": count_documents(Receipt, Receipt.receipt_date),
                        "issues_this_month": count_documents(Issue, Issue.issue_date)},
            "period": period, "series": list(series.values()), "top_products": ranking,
            "low_stock_products": low, "stale_products": sorted(stale, key=lambda r: -r["inactive_days"]),
            "inventory": rows, "stale_days": stale_days, "unknown_age_products": unknown_age,
            "timezone": "UTC+07:00", "generated_at": now.isoformat()}


@router.get("/summary")
def summary(period: Literal["day", "month"] = "day", stale_days: int = Query(90, ge=1, le=3650),
            db: Session = Depends(get_db)):
    return build_dashboard(db, period, stale_days)
