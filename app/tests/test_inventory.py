from app import models


def create_product(db):

    product = models.Product(
        product_code="HH001",
        product_name="Bàn phím cơ",
        unit="cái",
        min_stock_level=10
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


# =========================================================
# TỒN KHO BÌNH THƯỜNG
# =========================================================

def test_update_inventory(client, db):

    product = create_product(db)

    response = client.put(
        f"/inventory/{product.product_id}",
        json={
            "quantity_available": 20
        }
    )

    assert response.status_code == 200

    result = response.json()

    assert result["quantity_available"] == 20


# =========================================================
# KHÔNG CHO TỒN KHO ÂM
# =========================================================

def test_inventory_cannot_be_negative(client, db):

    product = create_product(db)

    response = client.put(
        f"/inventory/{product.product_id}",
        json={
            "quantity_available": -10
        }
    )

    assert response.status_code == 422