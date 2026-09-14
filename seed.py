from app.database import SessionLocal, engine
from app import models

# Tạo bảng nếu chưa tồn tại
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # 1. Khởi tạo Danh mục sản phẩm
    categories = [
        models.Category(category_id=1, category_name="Điện tử"),
        models.Category(category_id=2, category_name="Gia dụng"),
        models.Category(category_id=3, category_name="Thời trang")
    ]
    for cat in categories:
        if not db.query(models.Category).filter(models.Category.category_id == cat.category_id).first():
            db.add(cat)
    db.commit()

    # 2. Danh sách Sản phẩm và Tồn kho mẫu
    sample_products = [
        {"product_code": "LAP001", "product_name": "Laptop Dell XPS 13", "category_id": 1, "unit": "Cái", "min_stock_level": 5, "qty": 15},
        {"product_code": "PHONE01", "product_name": "iPhone 15 Pro Max", "category_id": 1, "unit": "Cái", "min_stock_level": 10, "qty": 3},  # Tồn kho dưới định mức
        {"product_code": "NOI001", "product_name": "Nồi cơm điện Cuckoo", "category_id": 2, "unit": "Cái", "min_stock_level": 8, "qty": 20},
        {"product_code": "QUAT01", "product_name": "Quạt đứng Panasonic", "category_id": 2, "unit": "Cái", "min_stock_level": 15, "qty": 6},  # Tồn kho dưới định mức
        {"product_code": "AO001", "product_name": "Áo thun Uniqlo Oversize", "category_id": 3, "unit": "Cái", "min_stock_level": 20, "qty": 50},
    ]

    for item in sample_products:
        existing = db.query(models.Product).filter(models.Product.product_code == item["product_code"]).first()
        if not existing:
            # Thêm sản phẩm
            new_prod = models.Product(
                product_code=item["product_code"],
                product_name=item["product_name"],
                category_id=item["category_id"],
                unit=item["unit"],
                min_stock_level=item["min_stock_level"]
            )
            db.add(new_prod)
            db.commit()
            db.refresh(new_prod)

            # Thêm bản ghi tồn kho tương ứng
            inv = models.Inventory(
                product_id=new_prod.product_id,
                quantity_available=item["qty"]
            )
            db.add(inv)

    db.commit()
    print("Thêm dữ liệu mẫu vào kho thành công!")

except Exception as e:
    print("Lỗi chèn dữ liệu:", e)
    db.rollback()
finally:
    db.close()