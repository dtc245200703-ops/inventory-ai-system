# Nhãn hàng và chat AI

1. Mở **Nhãn hàng** để thêm thương hiệu, ví dụ Apple hoặc Samsung.
2. Vào **Hàng hóa → Thêm / Sửa**, chọn nhãn cho từng sản phẩm.
3. Dùng bộ lọc nhãn hàng tại **Hàng hóa** hoặc **Tồn kho**. Có lựa chọn **Chưa gán nhãn** cho hàng cũ.
4. Bấm nút tròn ở góc dưới bên trái để mở bảng chat. Ví dụ: “Apple còn hàng gì?” hoặc “Nhãn Samsung có mặt hàng nào cần nhập thêm?”.

Nhãn hàng là thương hiệu sản phẩm, khác nhà cung cấp và bên nhận. AI dùng nhãn đã gán trong dữ liệu, không tự suy đoán theo tên sản phẩm. Đổi tên nhãn sẽ cập nhật tên hiển thị trên hàng hóa; không thể xóa nhãn đang có sản phẩm.

Bảng chat có trên các trang làm việc cho người đã đăng nhập, bao gồm thủ kho. Quyền báo cáo AI chuyên biệt vẫn dành cho quản trị viên và kế toán. Đóng/mở bảng chat giữ lại hội thoại trên trang hiện tại; tải lại hoặc chuyển trang bắt đầu lại hội thoại. Bấm **＋** để tạo hội thoại mới, **✕** hoặc Esc để đóng. Dấu chấm trên nút chat báo có câu trả lời đến khi bảng đang đóng.

## Dữ liệu cũ và kiểm tra

Ứng dụng tạo bảng `brands` và tự thêm cột `products.brand_id` khi khởi động. Hàng cũ giữ nhãn `NULL`, không bị gán thương hiệu tự động. Migration chạy lại được; kiểm thử sử dụng SQLite.

API: `/brands/` hỗ trợ danh sách, tạo, sửa, xóa; `/products/?brand_id=...` lọc hàng, `brand_id=0` lọc hàng chưa gán nhãn. Admin và thủ kho quản lý nhãn; kế toán được đọc danh mục qua API.

Kiểm thử backend: `python -m pytest tests/test_brands.py tests/test_catalog.py tests/test_products.py tests/test_prices.py tests/test_auth_dashboard.py -q -p no:cacheprovider`

Kiểm tra trình duyệt cục bộ: `python tests/browser_widget_smoke.py` (Chrome trên Windows và thư viện websockets). Kiểm tra dùng dữ liệu giả lập, không gọi Gemini. Ảnh mẫu: [desktop](screenshots/ai-widget-desktop.png), [điện thoại](screenshots/ai-widget-mobile.png).
