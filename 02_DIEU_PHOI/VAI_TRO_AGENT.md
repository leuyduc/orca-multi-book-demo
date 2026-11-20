# Tổ chức agent thực tế (ít quota, rõ trách nhiệm)

## Sơ đồ mặc định
`YẾN/người có quyền DUYỆT` → `C0 COORDINATOR (Sol Medium)` → `W1 BUILDER (Sol Medium)` → `QA độc lập khi tới gate (Astra High)`.

**W2 Reviewer có thể thay cho QA bằng Sol/Medium** nếu việc chỉ là unit test thường, không mang tác động tài chính/pháp lý. **Terra** chỉ khi đọc ảnh UI; **Luna** chỉ ở bước hẹp. Tổng số agent cần duy trì thường xuyên: **1–2**, không 5–10.

### C0: Coordinator / điều phối
- Nhận và định danh JOB, công ty, sổ, kỳ, quyền, nguồn; tạo ticket không nhập dữ liệu sống vào mã nguồn.
- Chọn model theo độ khó; giữ bảng công việc; quyết định song song/tuyến tính và checkpoint.
- Không đồng thời là người thực hiện lẫn người tự ký kết quả nghiệm thu tài chính.
- Mở gate cho người có quyền duyệt nếu sắp thao tác vượt quyền.

### W1: Builder / kỹ thuật
- Thực hiện **một JOB code có phạm vi rõ**, viết unit tests trên nguồn giả, sửa code, xuất diff, báo trạng thái.
- Không mở MISA, Zalo hay Drive thật khi ticket là `OFFLINE`.
- Thông báo thay đổi bảng dữ liệu, cách phục hồi và test.

### W2: Reviewer / QA
- Đọc diff và test, cố tìm lỗi sai pháp nhân/chi nhánh, ghi trùng, chạy lại, trạng thái sai, mất nguồn.
- Chỉ nhận bản sửa và test; không sửa chung worktree của Builder. Nếu cần patch, tạo ticket mới.

### A1: Architect (theo yêu cầu)
- Astra/High để rà `BOOK_ID`, song song ghi, idempotency, quyền, mức độ riêng tư, bảo toàn chứng từ.
- Đầu ra: risk register + acceptance criteria; không triển khai trực tiếp lên hệ thống.

### Khi nào xử lý song song?
**Cho phép:** W1 viết validator trên dữ liệu giả công ty A; W2 rà lược đồ dữ liệu độc lập; một agent khác viết hướng dẫn test nếu trong worktree riêng.
**Không:** Hai agent ghi cùng file Excel/Sheet; hai script cùng append sổ; một agent duyệt bút toán mà agent khác ghi tức thì; hai agent sửa cùng branch/worktree.

### Cổng quyết định theo từng mốc
`DESIGN_PASS` → `OFFLINE_TEST_PASS` → `REVIEW_PASS` → `OWNER_APPROVED` → `READ_ONLY_PILOT` → `OWNER_APPROVED_WRITE_PILOT` (nếu có) → `POST_WRITE_VERIFIED`.
Không nhảy từ `DESIGN_PASS` sang `DONE` hoặc `WRITE_PILOT`.
