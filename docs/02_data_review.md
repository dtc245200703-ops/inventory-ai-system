# Rà soát Giai đoạn 4

> Cập nhật sau đợt đóng gói: đã bổ sung đăng nhập/RBAC, chống giả mạo người lập, gộp dòng xuất trùng, tạo Inventory khi thêm hàng và kiểm tra ngưỡng không âm lúc tạo. Các phát hiện bên dưới là bản rà soát ban đầu. Xem trạng thái và kiểm chứng mới tại [đăng nhập/dashboard](06_auth_dashboard.md).

## Đã bổ sung

- Danh sách thư viện runtime và tách thư viện kiểm thử.
- Cấu hình DATABASE_URL để chạy database demo riêng và lưu dữ liệu Docker qua volume.
- Seed demo có lịch sử nhập/xuất, không ghi đè database có dữ liệu.
- Audit SQLite chỉ đọc: integrity, khóa ngoại, thiếu tồn kho, tồn âm, mức tối thiểu không hợp lệ, tồn không có lịch sử và sai lệch với số dư biến động cuối.
- Đóng gói, README, báo cáo và slide. Không sửa giao diện `/docs` hoặc logic AI.

## Phát hiện qua đọc mã nguồn

| Mức độ | Phát hiện | Ảnh hưởng / hướng xử lý |
|---|---|---|
| Cao | Chưa xác thực và phân quyền ở API | Chỉ demo localhost; bổ sung authentication và kiểm tra quyền trước khi công khai |
| Cao | Kết nối SQLite chưa bật foreign_keys | Người lập phiếu/nhà cung cấp không tồn tại có thể được lưu; cần kiểm tra dữ liệu cũ trước khi bật ràng buộc |
| Cao | Xuất kho kiểm tra riêng từng dòng trùng product_id | Tổng xuất có thể vượt tồn dù từng dòng hợp lệ; gộp số lượng theo sản phẩm trước khi kiểm tra, trả 409 và kiểm thử hồi quy riêng |
| Trung bình | PUT tồn kho không ghi StockMovement | Không thể đối chiếu đầy đủ lịch sử; cần thiết kế điều chỉnh tăng/giảm và người thực hiện |
| Trung bình | Tạo sản phẩm chưa tạo Inventory | Danh sách tồn và danh sách sản phẩm có thể khác số dòng |
| Trung bình | min_stock_level chưa có giới hạn không âm trong schema | Cần validation và rà soát dữ liệu đã lưu |
| Trung bình | with_for_update không khóa dòng trên SQLite | Chưa chứng minh an toàn ghi đồng thời; triển khai demo một worker không thay thế cơ chế đồng bộ |
| Trung bình | AI trả chi tiết exception cho client | Nên log nội bộ và dùng thông báo lỗi chung trước khi triển khai rộng |

Các phát hiện trên chưa được sửa trong đợt đóng gói này, không được xem là đã nghiệm thu. Audit không tự sửa dữ liệu, không chứng minh đầy đủ tính đúng đắn của mọi phiếu và không suy ra được số dư đầu kỳ của dữ liệu cũ. Nếu thiếu bảng, script dừng với lỗi thay vì tự tạo bảng.

## Bằng chứng hiện có

- `docker compose config --quiet`: thành công.
- Docker Engine: chưa chạy, chưa build image hoặc xác minh volume qua restart.
- Python 3.12.10: các import runtime thành công; smoke check trên database tạm xác minh seed, audit `count: 0`, từ chối seed lần hai, 6 sản phẩm, tổng tồn 94 và 12 biến động. Dashboard/schema trả 200, `/ai/data` có 3 cảnh báo. Không gọi Gemini thật hoặc chạy lại bộ test Giai đoạn 3.
- Kết quả 10 test của Giai đoạn 3 là thông tin người dùng bàn giao, không phải kết quả chạy mới.
- Chưa chạy audit trên `inventory.db` gốc; chưa kết luận dữ liệu đó sạch.

## Điều kiện nghiệm thu tiếp theo

Chạy seed trên database rỗng, audit phải trả `count: 0`; chạy seed lần hai phải từ chối và giữ nguyên dữ liệu. Kiểm tra dashboard, danh sách 6 sản phẩm, tồn tổng 94, 3 cảnh báo. Xác minh phiếu xuất vượt tồn trả 409 và không đổi tồn. Khởi động lại container và kiểm tra dữ liệu còn nguyên. Các lỗi cao cần xử lý trước triển khai công khai.
