"""Seed only an empty database; repeat runs never change existing inventory."""
from app import models
from app.database import engine, SessionLocal
from app.services.receipt_service import create_receipt
from app.services.issue_service import create_issue


def main():
    models.Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if any(db.query(table).first() is not None for table in (
            models.Product, models.User, models.Supplier, models.Category,
            models.Inventory, models.Receipt, models.Issue, models.StockMovement,
        )):
            raise SystemExit("Database is not empty; seed skipped. Use a new DATABASE_URL for a fresh demo.")
        # The outer transaction also covers service-level commits.
    with engine.connect() as connection:
        transaction = connection.begin()
        from sqlalchemy.orm import Session
        try:
            with Session(bind=connection, join_transaction_mode="rollback_only") as db:
                user = models.User(username="demo_keeper", password_hash="!disabled", role="thu_kho", is_active=0)
                supplier = models.Supplier(code="DEMO-SUP", name="Nhà cung cấp demo")
                category = models.Category(category_name="Hàng demo")
                db.add_all([user, supplier, category])
                db.flush()
                rows = [
                    ("LAP001", "Laptop Dell XPS 13", 5, 20, 5),
                    ("PHONE01", "Điện thoại", 10, 15, 12),
                    ("NOI001", "Nồi cơm điện", 8, 25, 5),
                    ("QUAT01", "Quạt đứng", 15, 20, 14),
                    ("AO001", "Áo thun", 20, 60, 10),
                    ("CAP001", "Cáp sạc", 5, 10, 10),
                ]
                imports, exports = [], []
                for code, name, minimum, received, issued in rows:
                    product = models.Product(product_code=code, product_name=name,
                        category_id=category.category_id, unit="Cái", min_stock_level=minimum)
                    db.add(product)
                    db.flush()
                    imports.append({"product_id": product.product_id, "quantity": received})
                    exports.append({"product_id": product.product_id, "quantity": issued})
                create_receipt(db, supplier.supplier_id, user.id, imports, receipt_no="DEMO-PN001")
                create_issue(db, user.id, exports, reason="Xuất demo", issue_no="DEMO-PX001")
                print(f"Demo created: user={user.id}, supplier={supplier.supplier_id}, 6 products.")
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise


if __name__ == "__main__":
    main()
