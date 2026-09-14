from app import models
import app.routers.ai as ai_router
import app.services.ai_service as ai_service


# =========================================================
# TẠO SẢN PHẨM TEST
# =========================================================

def create_test_product(db):

    product = models.Product(
        product_code="HH001",
        product_name="Bàn phím cơ",
        unit="cái",
        min_stock_level=10
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    inventory = models.Inventory(
        product_id=product.product_id,
        quantity_available=5
    )

    db.add(inventory)
    db.commit()

    return product


# =========================================================
# TEST DỮ LIỆU GỬI AI
# =========================================================

def test_ai_data(client, db):

    create_test_product(db)

    response = client.get("/ai/data")

    assert response.status_code == 200

    result = response.json()

    assert result["total_products"] == 1

    item = result["data"][0]

    assert item["product_code"] == "HH001"
    assert item["product_name"] == "Bàn phím cơ"

    assert item["quantity_available"] == 5
    assert item["min_stock_level"] == 10

    assert item["below_minimum"] is True
    assert item["shortage"] == 5


# =========================================================
# ĐẢM BẢO KHÔNG GỬI GIÁ MUA CHO AI
# =========================================================

def test_ai_data_does_not_include_price(client, db):

    create_test_product(db)

    response = client.get("/ai/data")

    item = response.json()["data"][0]

    assert "unit_price" not in item
    assert "price" not in item


# =========================================================
# TEST BÁO CÁO AI
# MOCK GEMINI - KHÔNG GỌI API THẬT
# =========================================================

def test_inventory_ai_report(client, db, monkeypatch):

    create_test_product(db)

    def fake_ai(data):
        return "Kho có sản phẩm đang dưới mức tồn tối thiểu."

    monkeypatch.setattr(
        ai_router,
        "generate_inventory_report",
        fake_ai
    )

    response = client.post(
        "/ai/inventory-report"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["report_type"] == "inventory_report"

    assert (
        result["result"]
        == "Kho có sản phẩm đang dưới mức tồn tối thiểu."
    )


# =========================================================
# TEST KHI KHÔNG CÓ DỮ LIỆU
# =========================================================

def test_ai_empty_database(client):

    response = client.post(
        "/ai/inventory-report"
    )

    assert response.status_code == 200

    result = response.json()

    assert (
        "Không có dữ liệu"
        in result["result"]
    )


# =========================================================
# TEST THIẾU GEMINI API KEY
# =========================================================

def test_missing_gemini_api_key(monkeypatch):

    monkeypatch.setattr(
        ai_service,
        "GEMINI_API_KEY",
        None
    )

    try:
        ai_service.get_client()

        assert False

    except RuntimeError as error:

        assert "GEMINI_API_KEY" in str(error)