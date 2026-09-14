from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import unicodedata
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import report_user
from app.database import get_db
from app.models import Inventory, Product, StockMovement

router = APIRouter(prefix="/reports", tags=["Báo cáo thống kê"], dependencies=[Depends(report_user)])
LOCAL_TZ = timezone(timedelta(hours=7))


def period_bounds(period: str, selected: date):
    if period == "day":
        start, end = selected, selected + timedelta(days=1)
    elif period == "month":
        start = selected.replace(day=1)
        end = (start + timedelta(days=monthrange(start.year, start.month)[1]))
    else:
        start, end = selected.replace(month=1, day=1), selected.replace(year=selected.year + 1, month=1, day=1)
    to_utc = lambda value: datetime.combine(value, time.min, LOCAL_TZ).astimezone(timezone.utc).replace(tzinfo=None)
    return start, end, to_utc(start), to_utc(end)


def build_report(db: Session, period: str, selected: date):
    start, end, utc_start, utc_end = period_bounds(period, selected)
    products = db.query(Product).order_by(Product.product_code).all()
    current = {row.product_id: row.quantity_available for row in db.query(Inventory)}
    movements = db.query(StockMovement).filter(StockMovement.created_at >= utc_start,
        StockMovement.created_at < utc_end).all()
    imported, exported = {}, {}
    for row in movements:
        target = imported if row.type == "import" else exported if row.type == "export" else None
        if target is not None:
            target[row.product_id] = target.get(row.product_id, 0) + row.quantity
    rows = []
    for product in products:
        last_before_end = (db.query(StockMovement).filter(
            StockMovement.product_id == product.product_id, StockMovement.created_at < utc_end)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).first())
        closing = last_before_end.balance_after if last_before_end else current.get(product.product_id, 0)
        qty_in, qty_out = imported.get(product.product_id, 0), exported.get(product.product_id, 0)
        # Reconcile to today's on-hand value. Inventory adjustments are therefore
        # included in the balancing opening figure rather than counted as receipts/issues.
        opening = closing - qty_in + qty_out
        rows.append({"product_id": product.product_id, "product_code": product.product_code,
            "product_name": product.product_name, "unit": product.unit, "opening": opening,
            "import": qty_in, "export": qty_out, "closing": closing,
            "min_stock_level": product.min_stock_level or 0,
            "below_minimum": closing <= (product.min_stock_level or 0)})
    ranked = sorted(rows, key=lambda row: (-row["export"], row["product_code"]))
    stale = []
    for row in rows:
        last = (db.query(StockMovement).filter_by(product_id=row["product_id"], type="export")
                .order_by(StockMovement.created_at.desc()).first())
        days = (selected - last.created_at.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()).days if last else None
        if row["closing"] > 0 and (days is None or days >= 90): stale.append({**row, "inactive_days": days})
    return {"period": period, "from_date": start.isoformat(), "to_date": (end-timedelta(days=1)).isoformat(),
        "summary": {"opening": sum(r["opening"] for r in rows), "import": sum(r["import"] for r in rows),
                    "export": sum(r["export"] for r in rows), "closing": sum(r["closing"] for r in rows)},
        "products": rows, "most_exported": ranked[0] if ranked and ranked[0]["export"] else None,
        "least_exported": sorted(rows, key=lambda r:(r["export"],r["product_code"]))[0] if rows else None,
        "stale_products": stale, "low_stock_products": [r for r in rows if r["below_minimum"]]}


@router.get("/")
def report(period: Literal["day", "month", "year"] = "month", selected: date | None = Query(None), db: Session = Depends(get_db)):
    return build_report(db, period, selected or date.today())


@router.get("/export.xls")
def export_excel(period: Literal["day", "month", "year"] = "month", selected: date | None = Query(None), db: Session = Depends(get_db)):
    data = build_report(db, period, selected or date.today())
    headings = ["Mã", "Sản phẩm", "Tồn đầu kỳ", "Tổng nhập", "Tổng xuất", "Tồn cuối kỳ"]
    body = "".join("<Row>"+"".join(f'<Cell><Data ss:Type="String">{escape(str(v))}</Data></Cell>' for v in
        [r["product_code"],r["product_name"],r["opening"],r["import"],r["export"],r["closing"]])+"</Row>" for r in data["products"])
    header = "<Row>"+"".join(f'<Cell><Data ss:Type="String">{h}</Data></Cell>' for h in headings)+"</Row>"
    xml = '<?xml version="1.0" encoding="utf-8"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Nhap xuat ton"><Table>'+header+body+'</Table></Worksheet></Workbook>'
    return Response(xml, media_type="application/vnd.ms-excel; charset=utf-8", headers={"Content-Disposition": "attachment; filename=bao-cao-kho.xls"})


@router.get("/export.pdf")
def export_pdf(period: Literal["day", "month", "year"] = "month", selected: date | None = Query(None), db: Session = Depends(get_db)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas

    data = build_report(db, period, selected or date.today())
    font_name = "Helvetica"
    candidates = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    font_path = next((path for path in candidates if path.exists()), None)
    if font_path:
        font_name = "InventoryUnicode"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    def printable(value):
        text_value = str(value)
        return text_value if font_path else unicodedata.normalize("NFKD", text_value).encode("ascii", "ignore").decode()
    stream = BytesIO(); page_width, page_height = landscape(A4)
    canvas = Canvas(stream, pagesize=(page_width, page_height)); y = page_height - 42
    canvas.setFont(font_name, 16); canvas.drawString(36, y, printable("BÁO CÁO NHẬP – XUẤT – TỒN")); y -= 24
    canvas.setFont(font_name, 10); canvas.drawString(36, y, printable(f"Kỳ: {data['from_date']} đến {data['to_date']}")); y -= 20
    summary = data["summary"]
    canvas.drawString(36, y, printable(f"Tồn đầu kỳ: {summary['opening']}   Tổng nhập: {summary['import']}   Tổng xuất: {summary['export']}   Tồn cuối kỳ: {summary['closing']}")); y -= 26
    widths = [36, 105, 310, 455, 535, 615]
    headers = ["Mã", "Sản phẩm", "Đầu kỳ", "Nhập", "Xuất", "Cuối kỳ"]
    for x, heading in zip(widths, headers): canvas.drawString(x, y, printable(heading))
    y -= 15; canvas.line(36, y + 5, page_width - 36, y + 5)
    for row in data["products"]:
        if y < 38:
            canvas.showPage(); canvas.setFont(font_name, 9); y = page_height - 38
        values = [row["product_code"], row["product_name"][:38], row["opening"], row["import"], row["export"], row["closing"]]
        for x, value in zip(widths, values): canvas.drawString(x, y, printable(value))
        y -= 15
    canvas.save(); content = stream.getvalue()
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=bao-cao-kho.pdf"})
