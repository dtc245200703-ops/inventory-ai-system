# Tài liệu Thiết kế Hệ thống Quản lý Kho

## 1. Phân quyền Người dùng (RBAC)
- **Admin**: Quản lý tài khoản, cấu hình tham số hệ thống.
- **Thủ kho**: Lập phiếu nhập/xuất kho, thực hiện kiểm kê.
- **Kế toán**: Tra cứu thẻ kho, xuất báo cáo định kỳ.

## 2. Quy trình Tránh Tồn Kho Âm
- **Nhập kho**: Tăng lượng tồn khả dụng trong bảng `inventory`.
- **Xuất kho**: Kiểm tra số lượng tồn hiện tại. Nếu không đủ hàng, hệ thống thực hiện Rollback giao dịch và trả về thông báo lỗi.