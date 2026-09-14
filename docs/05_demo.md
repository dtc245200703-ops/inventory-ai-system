# Kịch bản thuyết trình demo (5–7 phút)

> Phiên bản mới yêu cầu đăng nhập: tạo admin bằng `python create_admin.py`, sau đó trình diễn qua `/login` và menu nghiệp vụ. Kế toán chỉ xem; thủ kho/quản trị viên mới lập phiếu. Ví dụ API bên dưới thuộc kịch bản cũ, nay phải có cookie phiên và `X-CSRF-Token` lấy từ `/auth/me`. Frontend và `/docs` tự gắn token khi đã đăng nhập. Không cần nhập `created_by`, backend lấy từ phiên.

1. Khởi động theo README bằng database demo mới. Chạy `audit_data.py`, lưu kết quả thực tế. Không dùng dữ liệu gốc để diễn tập.
2. Mở dashboard, giới thiệu 6 sản phẩm và tổng tồn 94. Dùng `GET /products/` để lấy ID thực tế; user/supplier ID xuất hiện khi seed thành công.
3. Gọi `GET /ai/data`: giải thích 3 sản phẩm dưới ngưỡng và không có giá mua trong payload. Chụp ảnh trước khi thay đổi tồn.
4. Lập phiếu nhập 2 đơn vị cho sản phẩm đầu tiên bằng `POST /receipts/` với JSON bên dưới. Kỳ vọng HTTP 201, tồn sản phẩm tăng 2.
5. Lập phiếu xuất 1 đơn vị bằng `POST /issues/`. Kỳ vọng HTTP 201, tồn giảm 1. Đổi quantity thành 999999 để minh họa HTTP 409; đọc lại tồn để kiểm tra giữ nguyên.
6. Nếu đã cấu hình Gemini, gọi `POST /ai/restock-suggestion`. Giải thích AI chỉ khuyến nghị. Nếu chưa có khóa, trình bày payload `/ai/data` và nêu rõ chưa demo phản hồi AI trực tiếp.
7. Chạy audit lại. Với Docker, restart container rồi đọc lại tồn để minh họa lưu dữ liệu qua volume.

Payload nhập (thay ID bằng giá trị thực tế):

```json
{"supplier_id":1,"created_by":1,"items":[{"product_id":1,"quantity":2}]}
```

Payload xuất:

```json
{"created_by":1,"reason":"Demo cuối kỳ","items":[{"product_id":1,"quantity":1}]}
```

Có thể gửi API bằng Postman hoặc PowerShell `Invoke-RestMethod`; không cần sửa `/docs`.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/ai/data
Invoke-RestMethod http://127.0.0.1:8000/issues/ -Method Post -ContentType 'application/json' -Body '{"created_by":1,"items":[{"product_id":1,"quantity":1}]}'
```

Minh chứng cần bổ sung: ảnh dashboard, JSON tổng hợp AI, phiếu thành công, lỗi 409, audit, trạng thái container và phản hồi AI thật nếu có. Không đưa `.env` hoặc khóa API vào ảnh. Mỗi lần nhập/xuất thành công sẽ thay đổi dữ liệu; dùng database mới nếu cần lặp lại đúng số liệu ban đầu.
