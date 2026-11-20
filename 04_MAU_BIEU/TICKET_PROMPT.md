# Phiếu giao việc — mẫu dán vào Orca/Codex

```
JOB_ID: <JOB-...>
LOAI_VIEC: <CODE / REVIEW / DOC / READ_ONLY_RECONCILE>
LEGAL_ENTITY_ID: <ID hoặc DEMO_A>
BRANCH_ID: <ID hoặc NA>
BOOK_ID: <ID>
PERIOD: <YYYY-MM hoặc YYYY-MM-DD..YYYY-MM-DD>
SOURCE_SNAPSHOT_ID: <ID hoặc SYNTHETIC_...>
PROJECT_ID: <mã/NA>
PERMISSION_SCOPE: <OFFLINE_SYNTHETIC/READ_ONLY_CONFIRMED>
MODEL_REQUESTED: <gpt-6.2-sol / medium; chọn nếu khả dụng>
MUC_TIEU: <một kết quả cụ thể>
FILES_IN_SCOPE: <liệt kê 2-5 file của repo/được cấp phép>
KHONG_LAM: <sửa MISA, Sheets thật, gửi mail, đọc thêm nguồn ngoài scope...>
ACCEPTANCE_TESTS: <G0...G3 + idempotency...>
OUTPUT_FILES: <tệp, checkpoint, báo cáo>

Đầu tiên xác minh định danh và quyền; nếu thiếu => BLOCKED. Sau khi làm, báo file diff, test đã chạy, kiểm chứng nguồn, vấn đề còn lại. Không nói DONE nếu chưa kiểm chứng.
```
