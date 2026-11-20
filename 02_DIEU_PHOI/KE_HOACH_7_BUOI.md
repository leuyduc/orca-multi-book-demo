# Kế hoạch triển khai 7 buổi (có gate, không làm nền)

| Buổi | Mục tiêu | Agent/model | Kết quả trước khi qua buổi kế |
|---|---|---|---|
| 1 | Cấu hình Orca/Codex/permissions, đọc hồ sơ, chạy demo | Coordinator Sol Medium | G0 PASS + kiểm tra nguồn chưa được cấp |
| 2 | Cấu hình `DM_SO`/`LEGAL_ENTITY_ID`/`JOB_QUEUE` giả | Builder Sol Medium | G1 PASS, 2 sổ giả độc lập |
| 3 | Prototype tiếp nhận Timeline/Staging giả | Builder Sol Medium | 1 record/ảnh; ghép bằng chứng đúng; test |
| 4 | Kiểm đọc hai sổ đồng thời và checkpoint | Builder Sol Medium | Không trộn pháp nhân/kỳ, lỗi sổ A không chặn sổ B |
| 5 | Rà idempotency, lịch sử, quyền, lỗi tranh chấp | Reviewer Astra High | G2/G3 PASS + risk report |
| 6 | Làm bảng điều hành chỉ metadata, không số riêng tư | Builder Sol Medium | Số JOB / trạng thái / book id chính xác |
| 7 | Người có quyền xem kết quả, duyệt pilot read-only | Người chủ duyệt; Codex chỉ chuẩn bị | Danh mục nguồn được cấp quyền hoặc danh sách thiếu quyền |

**Để tiết kiệm quota:** không nhất thiết 7 ngày liên tục. Nếu chưa có việc cần viết code, không mở Codex. Không chạy Orca automations 24/7. Khi một buổi chưa qua gate, không tự chuyển bước vì lịch.
