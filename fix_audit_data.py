from app.database import SessionLocal
from app import models


def fix_database():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("BAT DAU SUA DU LIEU DEMO")
        print("=" * 60)

        # =================================================
        # 1. TÌM USER ĐỂ GHI STOCK MOVEMENT
        # =================================================

        user = db.query(models.User).first()

        if user is None:
            user = models.User(
                username="system_audit",
                password_hash="demo",
                role="admin",
                is_active=1
            )

            db.add(user)
            db.flush()

            print("Da tao user system_audit.")


        # =================================================
        # 2. SỬA PRODUCT CÓ CATEGORY KHÔNG HỢP LỆ
        # =================================================

        products = db.query(models.Product).all()

        first_category = (
            db.query(models.Category)
            .order_by(models.Category.category_id)
            .first()
        )

        for product in products:

            if product.category_id is not None:

                category = db.get(
                    models.Category,
                    product.category_id
                )

                if category is None:

                    if first_category is not None:
                        print(
                            f"Sua Product {product.product_id}: "
                            f"category_id {product.category_id} "
                            f"-> {first_category.category_id}"
                        )

                        product.category_id = (
                            first_category.category_id
                        )

                    else:
                        # Nếu chưa có category nào thì tạo mới
                        new_category = models.Category(
                            category_name="Chưa phân loại"
                        )

                        db.add(new_category)
                        db.flush()

                        first_category = new_category

                        product.category_id = (
                            new_category.category_id
                        )

                        print(
                            "Da tao category "
                            "'Chua phan loai'."
                        )


        # =================================================
        # 3. TẠO INVENTORY CHO PRODUCT CHƯA CÓ
        # =================================================

        for product in products:

            inventory = db.get(
                models.Inventory,
                product.product_id
            )

            if inventory is None:

                inventory = models.Inventory(
                    product_id=product.product_id,
                    quantity_available=0
                )

                db.add(inventory)

                print(
                    f"Da tao Inventory cho "
                    f"Product {product.product_id}, "
                    f"quantity = 0."
                )


        db.flush()


        # =================================================
        # 4. TẠO LỊCH SỬ CHO INVENTORY ĐANG CÓ TỒN
        # =================================================

        inventories = db.query(
            models.Inventory
        ).all()

        for inventory in inventories:

            movement = (
                db.query(models.StockMovement)
                .filter(
                    models.StockMovement.product_id
                    == inventory.product_id
                )
                .first()
            )

            if movement is None:

                # StockMovement đang yêu cầu quantity > 0
                # nên chỉ tạo adjustment khi tồn hiện tại > 0
                if inventory.quantity_available > 0:

                    movement = models.StockMovement(
                        product_id=inventory.product_id,
                        type=models.MovementTypeEnum.ADJUSTMENT.value,
                        ref_id=0,
                        quantity=inventory.quantity_available,
                        balance_after=inventory.quantity_available,
                        created_by=user.id
                    )

                    db.add(movement)

                    print(
                        f"Da tao lich su ton dau ky "
                        f"cho Product {inventory.product_id}: "
                        f"{inventory.quantity_available}"
                    )


        # =================================================
        # COMMIT
        # =================================================

        db.commit()

        print("=" * 60)
        print("SUA DU LIEU HOAN TAT")
        print("=" * 60)

    except Exception as error:

        db.rollback()

        print("Co loi:")
        print(error)

    finally:

        db.close()


if __name__ == "__main__":
    fix_database()