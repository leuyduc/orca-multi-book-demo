# Cổng nghiệm thu (go/no-go)

| Gate | Điều kiện PASS | Bằng chứng | Cho phép tiếp |
|---|---|---|---|
| G0-DEMO | Chủ cho tự chủ; chỉ dữ liệu giả, offline, trong staging; không chi phí hoặc kết nối ngoài | Phạm vi phiên, đường dẫn staging, lệnh và kết quả | Thiết kế và kiểm thử demo |
| G0-LIVE | Người có thẩm quyền ủy quyền cụ thể từng nguồn, hành động, pháp nhân, sổ, kỳ và phạm vi; kiểm soát quyền kỹ thuật và môi trường phù hợp | Văn bản ủy quyền và kiểm tra quyền; rà cấu hình, phiên bản và trạng thái repo | Chỉ thao tác đã được ủy quyền, theo gate tiếp theo |
| G1 | 2 BOOK giả 2 công ty được định danh độc lập, quyền riêng, thiếu trường thì BLOCKED | DM_SO giả, JOB_QUEUE mẫu | Code demo |
| G2 | Tests ngoại lệ + đa sổ đạt; lỗi 1 sổ không chặn sổ khác | Log `unittest`, báo cáo test | QA |
| G3 | Rà độc lập idempotency, quyền, dữ liệu bất biến, checkpoint, cross-book | Risk report + người duyệt | Chuẩn bị pilot chỉ đọc |
| G4 | Kiểm quyền và nguồn thật với chủ; chỉ đọc, chưa sửa | Danh mục nguồn có xác nhận | Pilot read-only |
| G5 | Đường ghi thử một sổ quản trị trên bản sao, đủ chứng từ và duyệt đúng scope | Bản sao trước/sau + audit | Trình xin bật ghi thật (riêng) |
| G6 | Chỉ khi có lệnh cụ thể, hậu kiểm và phương án phục hồi | Biên bản duyệt phạm vi | Viết vào đúng sổ được duyệt |

**Không có tự động nhảy Gate.** Không gộp G4 + G6 thành một lệnh. Trong bộ khởi tạo này chưa có G4–G6.

Full access/không sandbox không tạo cách ly dữ liệu; tự chủ demo là quyền thực hiện công việc giả, không phải ủy quyền dữ liệu thật. Trạng thái Git sạch không được giả định nếu không có Git. Các gate khác vẫn cần bằng chứng tương ứng.

## Bộ ca kiểm thử tối thiểu
1. 1 bill + 1 chuyển khoản => 1 giao dịch với 2 bằng chứng.
2. Ảnh cũ gửi lại => vẫn có dòng Timeline, nhưng không ghi thu/chi lặp.
3. Hai chuyển khoản cùng số tiền khác mã => không gộp.
4. Tạm ứng + bill quyết toán => tiền ra và chi phí đã xác nhận khác nhau.
5. Hai sổ khác công ty cùng lúc => checkpoint không chặn nhau.
6. Hai phiên dự tính ghi cùng sổ => 1 writer/phiên bản, không double-write.
7. JOB của công ty A trỏ đến sổ B => BLOCKED, không ghi.
8. Bản xuất MISA ACT sai chi nhánh/kỳ => BLOCKED.
9. Sau khi ghi thành công bị mất phản hồi => retry không append lần hai.
10. Người sửa tay đổi phiên bản nguồn => phát hiện xung đột, dừng ghi.
11. Trùng mã giao dịch xuyên sổ => không tự xóa/gộp.
12. Lỗi sổ A => sổ B còn có thể xử lý.
13. Duyệt A không cấp quyền ghi B.
14. JOB bị gián đoạn => resume checkpoint, không xử lý lại cả năm.
15. Sheet lọc/sort phải giữ toàn bộ hàng và công thức; chỉ test trên bản sao.
16. Thiếu quyền, hết quota => báo QUEUED/BLOCKED chứ không DONE.

Trạng thái có thể dùng: `QUEUED, VALIDATING, NEEDS_REVIEW, READY_FOR_OWNER, BLOCKED, ERROR, VERIFIED, DONE` (với dữ liệu thật chỉ DONE sau hậu kiểm nguồn chính thức).
