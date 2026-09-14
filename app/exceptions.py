# =========================================================
# CUSTOM EXCEPTIONS
# Các ngoại lệ tùy chỉnh cho hệ thống quản lý kho
# =========================================================


class ProductNotFoundError(Exception):
    """
    Lỗi khi không tìm thấy sản phẩm.
    """

    def __init__(self, product_id=None):
        if product_id is not None:
            message = f"Không tìm thấy sản phẩm có ID: {product_id}"
        else:
            message = "Không tìm thấy sản phẩm"

        self.product_id = product_id
        self.message = message

        super().__init__(self.message)


class InvalidQuantityError(Exception):
    """
    Lỗi khi số lượng nhập/xuất không hợp lệ.
    """

    def __init__(self, message="Số lượng phải lớn hơn 0"):
        self.message = message
        super().__init__(self.message)


class InsufficientStockError(Exception):
    """
    Lỗi khi số lượng tồn kho không đủ để xuất.
    """

    def __init__(
        self,
        product_id=None,
        product_code=None,
        available_quantity=None,
        requested_quantity=None,
        available=None,
        requested=None,
        **kwargs
    ):
        self.product_id = product_id
        self.product_code = product_code

        # Hỗ trợ nhiều tên tham số từ service
        if available_quantity is None:
            available_quantity = available

        if requested_quantity is None:
            requested_quantity = requested

        self.available_quantity = available_quantity
        self.requested_quantity = requested_quantity

        # Tạo tên sản phẩm để hiển thị lỗi
        product_text = ""

        if product_code is not None:
            product_text = f" sản phẩm {product_code}"
        elif product_id is not None:
            product_text = f" sản phẩm ID {product_id}"

        # Tạo thông báo lỗi
        if (
            available_quantity is not None
            and requested_quantity is not None
        ):
            message = (
                f"Tồn kho không đủ cho{product_text}. "
                f"Hiện có: {available_quantity}, "
                f"yêu cầu xuất: {requested_quantity}."
            )
        else:
            message = (
                f"Số lượng tồn kho không đủ cho{product_text}."
            )

        self.message = message

        super().__init__(self.message)