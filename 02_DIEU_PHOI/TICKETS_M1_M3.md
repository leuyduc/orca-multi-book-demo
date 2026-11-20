# Ticket M1–M3 — bản đề xuất 20/11/2026

Trạng thái chung: NHÁP, CHỜ CHỦ DUYỆT. Có kết quả demo từ trước tại `staging/demo`; mỗi ticket phải bắt đầu bằng rà checkpoint hiện có, không làm lại mù quáng. Mọi ID, kỳ, snapshot và reviewer dưới đây là giả; không sử dụng nguồn thật. Mỗi JOB chỉ xử lý một sổ. Không chạy ticket trong lượt M0 này.

## M1 — danh mục hai pháp nhân giả

**Đề xuất duyệt đầu tiên: `M1-REG-A-001`.** LEGAL_ENTITY_ID `DEMO_A`; BRANCH_ID `NA`; BOOK_ID `DEMO-A-CASH-2026`; PERIOD `2026-11`; PROJECT_ID `DEMO_PROJECT_A` (nhãn giả cần đối chiếu fixture); SOURCE_SNAPSHOT_ID `SYN_A_001`; ACTION `REVIEW_DEMO_REGISTRY`; PERMISSION_SCOPE `SYNTHETIC_ONLY`; REVIEWER `OWNER`.

- Đầu vào: hợp đồng dữ liệu, `data_gia/books.csv`, `staging/demo/input/books.csv`, `projects.csv`, checkpoint và báo cáo hiện có.
- Đầu ra: danh mục pháp nhân/sổ/công trình nháp cho A và kết quả đối chiếu, nêu trường thiếu hoặc sai, không giả định danh tính thật.
- Nghiệm thu: BOOK_ID duy nhất, gắn đúng pháp nhân/chi nhánh/kỳ và dự án giả; thiếu định danh bắt buộc phải BLOCKED; có kiểm thử thực tế và kết quả.
- Checkpoint riêng dự kiến `staging/demo/checkpoints/M1-REG-A-001.json`; xác nhận quyền ghi và tên fixture khi thực hiện.

**`M1-REG-B-001`**: `DEMO_B` / `B_HN` / `DEMO-B-MISA-2026` / `2026-11` / PROJECT_ID nhãn giả lấy từ fixture / `SYN_B_001`; cùng hành động, phạm vi, reviewer và điều kiện như A, checkpoint `staging/demo/checkpoints/M1-REG-B-001.json`. Chạy riêng sổ B, không ghi chung checkpoint A.

## M2 — xử lý độc lập hai sổ

**`M2-QUEUE-A-001`**: `DEMO_A` / `NA` / `DEMO-A-CASH-2026` / `2026-11` / snapshot `SYN_A_001` / `PROCESS_SYNTHETIC_QUEUE` / `SYNTHETIC_ONLY` / reviewer `OWNER`. Đầu vào: registry A đã kiểm, queue và checkpoint A; đầu ra: kết quả hàng chờ giả, checkpoint `staging/demo/checkpoints/M2-QUEUE-A-001.json`. Nghiệm thu: đúng phạm vi, resume không lặp, thay đổi nguồn được phát hiện, lỗi A không ảnh hưởng B.

**`M2-QUEUE-B-001`**: `DEMO_B` / `B_HN` / `DEMO-B-MISA-2026` / `2026-11` / snapshot `SYN_B_001` / cùng action và quyền giả; đầu vào/đầu ra tương ứng B; checkpoint `staging/demo/checkpoints/M2-QUEUE-B-001.json`. Kiểm thử đồng thời hai job khi M1 được duyệt và đạt; tách đường ghi, không trộn kỳ hoặc pháp nhân.

## M3 — kiểm thử nghiệp vụ và phục hồi

**`M3-EVIDENCE-A-001`**: `DEMO_A` / `NA` / `DEMO-A-CASH-2026` / `2026-11` / `SYN_A_001` / `TEST_EVIDENCE_SYNTHETIC` / `SYNTHETIC_ONLY` / reviewer `OWNER`. Đầu vào: Timeline, evidence và kiểm thử giả hiện có. Đầu ra: kết quả kiểm thử từng ca 1–4 và 7; checkpoint `staging/demo/checkpoints/M3-EVIDENCE-A-001.json`. Nghiệm thu: mỗi lượt nguồn có RECORD_ID, ghép có chứng cứ, không nhân chi, cùng tiền khác mã không gộp, tách tiền ra/chi phí và chặn sai sổ.

**`M3-ISOLATION-B-001`**: `DEMO_B` / `B_HN` / `DEMO-B-MISA-2026` / `2026-11` / `SYN_B_001` / `TEST_ISOLATION_SYNTHETIC` / `SYNTHETIC_ONLY` / reviewer `OWNER`. Đầu vào: hai bộ fixture và checkpoint giả, writer mô phỏng và queue; đầu ra: ma trận ca 5–16 cùng log và checkpoint `staging/demo/checkpoints/M3-ISOLATION-B-001.json`. Nghiệm thu: thử khóa, version, retry, quyền giả, lỗi/quota, resume và không gộp xuyên sổ; ghi rõ ca Sheet/XLSX, MISA hoặc hệ thống thật chưa chứng minh. Mô phỏng không chứng minh hệ thống thật.

Mỗi ticket ghi PROJECT_ID nếu có, nguồn, phiên bản, kết quả, reviewer, model thực tế nếu xác minh được; checkpoint độc lập. Cần duyệt riêng trước tiếp tục theo yêu cầu hiện tại; không có ticket nào tự cấp quyền live.
