# Inventory AI System

Đồ án quản lý kho bằng FastAPI, SQLAlchemy, SQLite và Gemini. Hệ thống quản lý sản phẩm, tồn kho, phiếu nhập/xuất và cung cấp báo cáo AI bằng tiếng Việt.

## Chạy trên máy cá nhân

Yêu cầu Python 3.12. Chạy từ thư mục gốc dự án trong PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
# Chỉ sao chép khi chưa có .env; giữ nguyên .env đang sử dụng.
Copy-Item .env.example .env
$env:DATABASE_URL = "sqlite:///./demo.db"
.venv\Scripts\python seed_demo.py
.venv\Scripts\python audit_data.py
# Tạo quản trị viên bằng nút Đăng ký trên trang /login sau khi chạy ứng dụng.
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở http://127.0.0.1:8000/login, bấm **Đăng ký tài khoản**, nhập tên, email tùy chọn, mật khẩu và xác nhận. Tài khoản đầu tiên của hệ thống là quản trị viên và được đăng nhập ngay; tài khoản đăng ký sau cần quản trị viên duyệt. Sau đăng nhập, hệ thống chuyển đến dashboard. API schema ở `/openapi.json`; `/docs` yêu cầu đăng nhập, giữ giao diện và tự gắn CSRF khi thao tác. Không bắt buộc có khóa Gemini để chạy nghiệp vụ kho; `/ai/data` dành cho quản trị viên/kế toán.

## Đăng nhập và phân quyền

Đăng ký trực tiếp ở `/register`, không cần chạy Terminal để tạo tài khoản. Backend tự quyết định quyền, không nhận trường role/is_active từ form đăng ký. Tài khoản mới sau quản trị viên đầu tiên ở trạng thái **Chờ duyệt / Đã khóa**; quản trị viên vào **Tài khoản**, chọn vai trò, đặt **Hoạt động** rồi **Lưu** để duyệt. Quản trị viên đã khóa vẫn được tính là đã thiết lập, không mở lại quyền tạo admin đầu tiên. Hai lượt đăng ký đồng thời được tuần tự hóa trong transaction SQLite. Đăng ký tối đa 10 tài khoản/IP/giờ; email chỉ là định danh đăng nhập, chưa xác minh qua thư.

`create_admin.py` vẫn là cách khởi tạo tùy chọn bằng Terminal: hỏi tên đăng nhập, email tùy chọn và mật khẩu (ít nhất 10 ký tự, không hiển thị khi gõ). Không có mật khẩu mặc định. Với database đang dùng, giữ DATABASE_URL hiện tại, không seed lại. Nếu tên tài khoản cũ đã tồn tại, chọn tên mới. Script cho phép khởi tạo khi chưa có quản trị viên hoạt động với định dạng mật khẩu mới. Người dùng demo từ seed/SQL cũ không tự trở thành tài khoản đăng nhập.

Sau khi đăng nhập quản trị viên, vào **Tài khoản** để tạo thủ kho/kế toán, đổi quyền, khóa tài khoản hoặc đặt lại mật khẩu. Đổi tài khoản sẽ hủy các phiên của tài khoản đó; không cho tự khóa/hạ quyền quản trị viên đang sử dụng.

| Chức năng | Quản trị viên | Thủ kho | Kế toán |
|---|---|---|---|
| Tổng quan, thống kê | Có | Có | Có |
| Tạo hàng hóa, sửa tồn, nhà cung cấp | Có | Có | Không |
| Xem phiếu nhập/xuất | Có | Có | Có |
| Lập phiếu nhập/xuất | Có | Có | Không |
| Báo cáo AI | Có | Không | Có |
| Quản lý tài khoản | Có | Không | Không |

Kế toán có thể đọc API sản phẩm/tồn/nhà cung cấp để đối chiếu báo cáo, nhưng menu không hiển thị trang quản lý kho. Backend kiểm tra quyền cho mọi API nghiệp vụ, không phụ thuộc menu.

Phiên lưu ở database, cookie HttpOnly/SameSite=Strict, hết hạn sau 8 giờ. Yêu cầu ghi phải có `X-CSRF-Token` lấy từ `/auth/me`; frontend tự xử lý. Đăng xuất hủy phiên ở server. Khi dùng HTTPS, đặt `SESSION_COOKIE_SECURE=true`; localhost HTTP để `false`. Đăng nhập JSON cần header `X-Requested-With: inventory-app`; không bật CORS công khai. Mật khẩu dùng PBKDF2-SHA256 với salt riêng, 600.000 vòng. Sai 20 lần/IP trong 15 phút tạm chặn đăng nhập.

Dashboard dùng giờ Việt Nam, đếm phiếu confirmed trong tháng. Biểu đồ theo ngày trong tháng hiện tại hoặc 12 tháng gần nhất; top xuất nhiều dùng cùng kỳ. Dưới tồn tối thiểu dùng `<`; AI cũ vẫn dùng `<=` (cảnh báo chạm ngưỡng). Hàng tồn lâu là tồn dương và ít nhất 90 ngày từ lần xuất cuối; chưa xuất thì dùng lịch sử đầu tiên. Hàng không có lịch sử được ghi rõ chưa đủ dữ liệu, không tự đoán tuổi tồn. Đây là chỉ báo ít luân chuyển, không phải tuổi lô.

Chi tiết và minh chứng: [đăng nhập/dashboard](docs/06_auth_dashboard.md).

Để gọi AI, điền `GEMINI_API_KEY`, `GEMINI_MODEL` phù hợp tài khoản và `GEMINI_THINKING_LEVEL` tương thích model trong `.env`, sau đó khởi động lại ứng dụng. Không đưa khóa vào báo cáo hoặc source công khai. Biến môi trường hệ điều hành được ưu tiên hơn `.env`.

## Dữ liệu demo

Trang **Hàng hóa** (`/workspace/products`) đã có danh sách đủ nhóm/tồn/trạng thái, thêm/sửa/xóa, tìm theo mã hoặc tên, lọc nhóm và xem chi tiết. Có thể tạo nhóm ngay tại trang. Hàng có tồn hoặc lịch sử bị chặn xóa; sửa thông tin không thay đổi tồn. Xem [hướng dẫn quản lý hàng hóa](docs/07_product_management.md).

`seed_demo.py` chỉ chạy trên database rỗng; chạy lại sẽ dừng, không cộng tồn lần nữa. Script tạo nhà cung cấp, người lập phiếu kỹ thuật (không phải tài khoản đăng nhập), 6 sản phẩm, một phiếu nhập và một phiếu xuất với 12 biến động kho. Toàn bộ seed nằm trong một transaction. Dùng database mới để bắt đầu lại; không xóa `inventory.db` hiện có.

| Mã | Nhập | Xuất | Tồn | Tối thiểu |
|---|---:|---:|---:|---:|
| LAP001 | 20 | 5 | 15 | 5 |
| PHONE01 | 15 | 12 | 3 | 10 |
| NOI001 | 25 | 5 | 20 | 8 |
| QUAT01 | 20 | 14 | 6 | 15 |
| AO001 | 60 | 10 | 50 | 20 |
| CAP001 | 10 | 10 | 0 | 5 |

Tồn tổng cộng 94; 3 sản phẩm chạm/dưới ngưỡng. Lượng xuất 30 ngày là 56 ngay sau seed; số liệu này thay đổi theo thời gian. `seed.py` và SQL trong `database/` là tài liệu/dữ liệu cũ; không trộn với bộ demo mới.

## API chính

| Đường dẫn | Chức năng |
|---|---|
| GET /products/, POST /products/ | Danh sách, tạo sản phẩm |
| GET /products/{id}, PUT /products/{id}, DELETE /products/{id} | Chi tiết, sửa, xóa hàng chưa sử dụng |
| GET /categories/, POST /categories/ | Xem, thêm nhóm hàng |
| GET /inventory/, GET /inventory/{id} | Xem tồn |
| PUT /inventory/{id} | Đặt lại tồn trực tiếp, hiện chưa ghi lịch sử |
| GET /receipts/, POST /receipts/ | Danh sách, lập phiếu nhập |
| GET /issues/, POST /issues/ | Danh sách, lập phiếu xuất |
| GET /ai/data | Xem dữ liệu tổng hợp gửi AI |
| POST /ai/inventory-report | Báo cáo AI |
| POST /ai/restock-suggestion | Gợi ý nhập hàng |
| POST /ai/anomaly-summary | Phân tích dấu hiệu bất thường |

## Đóng gói bằng Docker

```powershell
docker compose up -d --build
docker compose exec app python seed_demo.py
docker compose exec app python audit_data.py
# Mở /login và bấm Đăng ký để tạo quản trị viên.
docker compose ps
docker compose logs --tail 100 app
```

Container lưu SQLite trong volume `inventory_data`, chỉ mở cổng trên localhost và chạy một worker. Dừng bằng `docker compose down`; không dùng `down -v` nếu cần giữ dữ liệu. Nếu volume đã có dữ liệu, bỏ qua seed. Healthcheck kiểm tra HTTP/schema, không thay thế kiểm tra dữ liệu.

Sao lưu SQLite bằng API backup, ví dụ từ container đang chạy:

```powershell
docker compose exec app python -c "import sqlite3; s=sqlite3.connect('/data/inventory.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close(); s.close()"
docker compose cp app:/data/backup.db ./inventory-backup.db
```

Khôi phục bằng cách dừng ứng dụng, sao lưu bản hiện tại trước, chép bản backup vào đường dẫn database đang cấu hình rồi chạy audit trước khi sử dụng lại. Không chép đè database khi ứng dụng đang ghi.

## Kiểm chứng và giới hạn

Giai đoạn 3: **10 test passed theo thông tin bàn giao**, không chạy lại trong Giai đoạn 4. Thư viện kiểm thử chuyển sang `requirements-dev.txt`. Các phiên bản runtime hiện có khoảng giới hạn, chưa phải lockfile đã xác minh trên môi trường triển khai.

Giai đoạn 4 đã kiểm tra Compose bằng `docker compose config --quiet` và chạy smoke check trên Python 3.12.10 với database tạm: seed thành công, audit không có phát hiện, seed lần hai từ chối, 6 sản phẩm/tổng tồn 94/12 biến động đúng kỳ vọng; dashboard và schema trả HTTP 200, dữ liệu AI có 3 cảnh báo. Không gọi Gemini thật. Chưa build/chạy container vì Docker Engine chưa hoạt động; chưa xác minh cài mới toàn bộ dependency từ requirements.

Phần đăng ký/đăng nhập/dashboard và quản lý hàng hóa đã qua **20 test backend** (`tests/test_auth_dashboard.py`, `tests/test_products.py`). Chrome headless đã kiểm tra đăng ký/đăng nhập, thêm/sửa/xóa/chi tiết hàng hóa, tạo nhóm, tìm kiếm/lọc, chặn xóa có lịch sử và bố cục mobile; không có exception JavaScript trong các luồng kiểm tra. Không chạy lại suite Giai đoạn 3. Mã kiểm tra trình duyệt ở `tests/browser_smoke.py` dùng Chrome và module websockets, tự tạo database/profile tạm. Ảnh nằm ở `docs/screenshots/`.

Ứng dụng hiện phù hợp demo cục bộ. SQLite chưa bật kiểm tra khóa ngoại ở mọi kết nối; ghi đồng thời và lịch sử điều chỉnh tồn vẫn cần hoàn thiện. Phiếu xuất trùng sản phẩm đã được gộp và kiểm tra tổng ở backend. Xem [kết quả rà soát](docs/02_data_review.md), [báo cáo kỹ thuật](docs/03_final_report.md), [slide](docs/04_slides.html) và [kịch bản demo](docs/05_demo.md). Kết quả kiểm thử Giai đoạn 3 là kết quả lịch sử trước khi thêm xác thực; nếu chạy lại cần cập nhật fixture đăng nhập, không mở quyền API để tương thích test cũ.
