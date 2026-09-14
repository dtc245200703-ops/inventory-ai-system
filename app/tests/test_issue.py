from app import models


# =========================================================
# TẠO USER TEST
# =========================================================

def create_user(db):

    user = models.User(
        username="test_user",
        password_hash="test_hash",
        role="thu_kho",
        is_active=1
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# =========================================================
# TẠO PRODUCT + INVENTORY
# =========================================================

def create_product(
    db,
    code,
    name,
    quantity
):

    product = models.Product(
        product_code=code,
        product_name=name,
        unit="cái",
        min_stock_level=5
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    inventory = models.Inventory(
        product_id=product.product_id,
        quantity_available=quantity
    )

    db.add(inventory)
    db.commit()

    return product


# =========================================================
# TEST XUẤT VƯỢT TỒN
# =========================================================

def test_issue_more_than_stock(client, db):

    user = create_user(db)

    product = create_product(
        db,
        "HH001",
        "Bàn phím",
        5
    )

    response = client.post(
        "/issues/",
        json={
            "created_by": user.id,
            "reason": "Xuất bán",
            "items": [
                {
                    "product_id": product.product_id,
                    "quantity": 10
                }
            ]
        }
    )

    assert response.status_code == 409

    inventory = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.product_id
            == product.product_id
        )
        .first()
    )

    # Tồn vẫn phải là 5
    assert inventory.quantity_available == 5


# =========================================================
# TEST ROLLBACK TOÀN BỘ PHIẾU
# =========================================================

def test_issue_transaction_rollback(client, db):

    user = create_user(db)

    product1 = create_product(
        db,
        "HH001",
        "Bàn phím",
        10
    )

    product2 = create_product(
        db,
        "HH002",
        "Chuột",
        2
    )

    response = client.post(
        "/issues/",
        json={
            "created_by": user.id,
            "reason": "Xuất kho test",
            "items": [
                {
                    "product_id":
                        product1.product_id,

                    "quantity": 3
                },
                {
                    "product_id":
                        product2.product_id,

                    "quantity": 5
                }
            ]
        }
    )

    # Product 2 không đủ
    assert response.status_code == 409

    inventory1 = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.product_id
            == product1.product_id
        )
        .first()
    )

    inventory2 = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.product_id
            == product2.product_id
        )
        .first()
    )

    # QUAN TRỌNG:
    # Product 1 cũng không được bị trừ
    assert inventory1.quantity_available == 10

    assert inventory2.quantity_available == 2


# =========================================================
# TEST QUANTITY <= 0
# =========================================================

def test_issue_invalid_quantity(client, db):

    user = create_user(db)

    product = create_product(
        db,
        "HH001",
        "Bàn phím",
        10
    )

    response = client.post(
        "/issues/",
        json={
            "created_by": user.id,
            "reason": "Test",
            "items": [
                {
                    "product_id":
                        product.product_id,

                    "quantity": 0
                }
            ]
        }
    )

    assert response.status_code == 400