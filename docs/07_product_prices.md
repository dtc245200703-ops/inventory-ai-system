# Giá nhập và giá xuất

- Vào **Hàng hóa → Thêm / Sửa** để đặt giá nhập và giá xuất mặc định theo một đơn vị hàng, bằng VNĐ.
- Chọn hàng trên phiếu nhập hoặc phiếu xuất để tự điền đơn giá tương ứng. Có thể sửa giá riêng cho từng dòng; thành tiền và tổng tiền cập nhật ngay.
- Giá trên phiếu được lưu tại thời điểm lập. Thay đổi giá mặt hàng không làm đổi phiếu cũ.
- Để trống đơn giá khi gửi phiếu: sử dụng giá mặc định nếu có. Giá `0` là miễn phí; chưa biết giá là `null`, khác với `0`.
- Phiếu có dòng chưa biết giá sẽ hiển thị tổng tiền chưa đủ giá. Không tự gán giá hiện tại cho phiếu lịch sử.
- Chấp nhận giá không âm, tối đa 12 chữ số phần nguyên và 2 chữ số thập phân. Giá lưu bằng `NUMERIC(14, 2)` và tính tổng bằng Decimal.

## Cập nhật cơ sở dữ liệu

Ứng dụng tự thêm các cột còn thiếu khi khởi động: `products.purchase_price`, `products.sale_price`, `issue_items.unit_price`. `receipt_items.unit_price` đã có từ trước. Dữ liệu cũ giữ nguyên; các cột mới nhận `NULL`. Quy trình có thể chạy lại và hỗ trợ SQLite/PostgreSQL; kiểm thử tự động sử dụng SQLite.

API hàng hóa trả thêm `purchase_price`, `sale_price`. API phiếu trả `unit_price`, `line_total` cho mỗi dòng và `total_amount` cho cả phiếu. Các số tiền trong JSON được biểu diễn dưới dạng chuỗi thập phân để giữ độ chính xác.

Kiểm tra: `python -m pytest tests/test_prices.py tests/test_products.py tests/test_auth_dashboard.py -q -p no:cacheprovider`
