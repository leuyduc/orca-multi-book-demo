# Kiến trúc pilot thu chi — quyết định 21/11/2026

**Phạm vi PUBLIC:** chỉ dữ liệu giả; dùng DEMO_A / DEMO_B làm nhãn. Tên doanh nghiệp pilot, dữ liệu kế toán, thông tin nhân viên, đường dẫn riêng và nguồn thật phải nằm ngoài GitHub public.

## Các quyết định được chốt

- Pilot đầu tiên: một sổ thu chi, sau đó nhân rộng.
- Đồng thời 1–2 sổ; dưới 100 hồ sơ/ngày trên tất cả công ty.
- Không phát sinh phí API, không thêm máy chủ; ưu tiên chương trình offline và sau này Google Sheets/Apps Script khi có quyền.
- Chế độ xử lý: tự đọc/đối chiếu → lập đề xuất → người có thẩm quyền duyệt → (nếu có quyền riêng) ghi vào đích → đọc lại và hậu kiểm.
- Cho phép Codex tự sửa, chạy test, tạo PR trong DEMO. Không cấp quyền live.

## Hai luồng tách biệt

**Phát triển:** người giao việc → Orca điều phối → Codex phát triển trên nhánh → test → GitHub Actions → PR → QA → main. Orca không phải engine kế toán hằng ngày.

**Nghiệp vụ tương lai:** Nguồn → snapshot/manifest SHA256 → kiểm pháp nhân/sổ/kỳ/công trình → Timeline theo lượt nhận/tệp → liên kết bằng chứng theo TRANSACTION_ID → staging → READY_FOR_OWNER/NEEDS_REVIEW → duyệt → writer có phân quyền → đối chiếu hậu ghi + AUDIT.

## DEMO hiện có

- P1-SCHEMA/P1-MANIFEST kiểm tra scope, manifest, SHA256, checkpoint dữ liệu giả.
- Pilot thu chi Python (staging/demo/pilot-cash) lấy manifest/seal/checkpoint P1 đã tạo trước, xác minh nguồn trước khi lập đề xuất; không tự tạo lại manifest khi nguồn thay đổi.
- Một BILL + TRANSFER cùng TX, khớp số tiền và duy nhất mỗi loại: READY_FOR_OWNER. Đề xuất vẫn UNAPPROVED, DESTINATION_WRITE_ALLOWED=false.
- Thiếu BILL/TRANSFER, FLAGGED, nhiều bằng chứng khó xác định: NEEDS_REVIEW, không tính tiền ra để tự ghi.
- Tái chạy nguồn y nguyên: ALREADY_PREPARED. Thay dữ liệu nguồn/manifest/đầu ra: BLOCKED.
- A và B có bản kê/checkpoint riêng; code mới chưa gọi writer_sim.ps1 và **chưa ghép trực tiếp vào PowerShell workflow M3**.

## Bất biến

1. JOB phải khớp LEGAL_ENTITY_ID, BOOK_ID, PERIOD, PROJECT_ID, SOURCE_SNAPSHOT_ID.
2. Một ảnh/tệp gốc = một RECORD_ID Timeline; không cộng bill + chuyển khoản thành hai lần chi.
3. SHA256 chứng minh nội dung không đổi so với manifest, không chứng minh quyền nguồn hay nghiệp vụ đúng.
4. Sổ A bị lỗi/đổi nguồn không làm sổ B mất checkpoint.
5. Ghi thật tương lai cần single writer, version đối tượng đích, kiểm tra duplicate/idempotency, backup, đối chiếu sau ghi và audit tách biệt.
6. READY_FOR_OWNER không phải APPROVED. Không tự ghi MISA, Sheets thật, phát hành hóa đơn, thanh toán hoặc nộp hồ sơ.
7. Không công khai dữ liệu thực của các đơn vị.

## Điều phối ít quota

- Thường xuyên 1 agent Codex Medium thực hiện ticket; điều phối bằng checkpoint/GitHub, không tạo 5 agent chạy nền.
- QA High chỉ với thay đổi schema, phân quyền, idempotency, tiền, phê duyệt hoặc ghi.
- Khi dùng 2 worker, giới hạn các tệp/BOOK_ID độc lập; không cùng sửa worktree hay cùng ghi sổ.
- Chọn model theo danh sách Orca/Codex thực tế hiển thị, không giả định model nào luôn sẵn có.

## Ranh giới

ĐÃ CÓ: dữ liệu giả, validator P1, P1 → JSON đề xuất thu chi và test offline.

CHƯA CÓ: nối P1 vào workflow M3, xác thực phê duyệt, dữ liệu live, adapter Google Sheets/MISA, giao diện duyệt, bảo vệ đích trước/sau ghi.

Cổng live: G3 rà độc lập → G0-LIVE/G4 chỉ đọc theo nguồn được ủy quyền → G5 thử ghi trên bản sao → G6 cấp quyền ghi thật riêng. Không nhảy cổng.