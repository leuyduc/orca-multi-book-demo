# Hợp đồng dữ liệu đa công ty / đa sổ (bản phác thảo)

## Các khóa định danh
- `LEGAL_ENTITY_ID`: pháp nhân; không dùng tên viết tắt như bằng chứng pháp lý.
- `BRANCH_ID`: chi nhánh nếu có; Demo B Hà Nội tách phạm vi tổng công ty.
- `BOOK_ID`: sổ quản trị/kế toán cụ thể; bất biến theo tên tab. Một pháp nhân có thể nhiều sổ.
- `PROJECT_ID`: công trình; phải xác minh gắn với pháp nhân.
- `PERIOD`: kỳ kế toán/khung ngày (ISO 8601); không đổi ngầm.
- `RECORD_ID`: duy nhất theo ảnh/file gốc trong Timeline.
- `TRANSACTION_ID`: nghiệp vụ tiền thực tế; liên kết nhiều `RECORD_ID`.
- `JOB_ID`: đơn vị công việc, có trạng thái/checkpoint độc lập.
- `SOURCE_SNAPSHOT_ID`: định danh file nguồn + thời điểm bản xuất + hash khi có, tránh xử lý lại bản đã đổi.

## DM_SO (BOOK_REGISTRY)
`BOOK_ID | LEGAL_ENTITY_ID | BRANCH_ID | BOOK_KIND | SOURCE_SYSTEM | FISCAL_YEAR | PERIOD | SOURCE_REF | OWNER | READ_SCOPE | WRITE_SCOPE | LAST_SNAPSHOT | STATUS`.

### P1-SCHEMA-A-001 — quy tắc kiểm thử giả theo giai đoạn

Đặc tả dưới đây và validator `staging/demo/p1-schema/schema_demo.py` chỉ xử lý fixture giả `SYNTHETIC_ONLY`; `PILOT_READ` và `PRE_WRITE` là **tên kịch bản kiểm quy tắc giả**, không cấp quyền mở nguồn, ghi đích hay triển khai pilot. Các gate G0-LIVE/G3/G4, ủy quyền cụ thể và kiểm soát trước ghi vẫn phải được xét riêng. Dữ liệu CSV/demo cũ không bị đổi và chưa tự động áp dụng schema P1.

| Trường | Demo offline | Mô phỏng pilot chỉ đọc | Mô phỏng trước ghi thật |
|---|---|---|---|
| `FISCAL_YEAR` | Có thể null chưa xác minh; nếu có phải gồm ID, ngày bắt đầu/kết thúc hợp lệ chứa toàn bộ kỳ. | Bắt buộc với loại sổ kế toán `ACCOUNTING`/`MISA_LEDGER`; các loại sổ quản trị giả có thể null. Nếu có năm tài chính, phải có ID xác nhận giả trong danh mục giả. | Cùng quy tắc pilot; nguồn thật và niên độ phải được chủ dữ liệu xác nhận riêng. |
| `SOURCE_REF` | Null khi `SOURCE_PRESENT=false`; nếu có nguồn thì bắt buộc tham chiếu giả có ID bền vững `SYNREF:...` và đúng pháp nhân, nhánh, sổ, dự án, kỳ. | Phải có nguồn và tham chiếu đúng scope. | Cùng quy tắc pilot; không coi ID giả hay tên file là bằng chứng quyền nguồn. |
| `OWNER` | Có thể null; nếu có phải là ID vai trò giả trong danh mục giả. | Bắt buộc ID vai trò giả trong danh mục giả cho mô phỏng; reviewer không mặc nhiên là owner. | Cùng quy tắc pilot; owner giả không phải người có quyền hay bằng chứng phê duyệt thật. |
| `LAST_SNAPSHOT` | Có thể null khi không ghi đích. | Có thể null khi không ghi đích. | Bắt buộc đối tượng sao lưu **đích giả lập**, đúng scope, có ID, thời điểm kèm múi giờ, version đích, ID vị trí bảo vệ giả, ID người chịu trách nhiệm giả, hash 64 ký tự, kết quả và mã thử khôi phục giả; một snapshot nguồn không thay thế bản sao lưu đích. |

Bốn khóa metadata phải hiện diện trong cấu trúc P1; `null` là chưa xác minh, không phải giá trị đã xác nhận. `DESTINATION_WRITE` phải là boolean: `false` cho cả demo và pilot chỉ đọc, `true` chỉ mô phỏng kiểm điều kiện trước ghi; điều này không kích hoạt writer. Năm tài chính không mặc định là năm dương lịch: cấu hình giả có thể bắt đầu tháng 7 và kết thúc tháng 6 năm sau. Validator chỉ kiểm cú pháp ID tham chiếu, hình dạng hash và nhãn thử phục hồi; không chứng minh tham chiếu tồn tại, hash thật, thử khôi phục thật hay quyền thực tế. Trường hợp không có chi nhánh được biểu diễn bằng `null` hoặc `NA` và so khớp như cùng trạng thái không có chi nhánh; chuỗi rỗng hoặc thiếu khóa bị từ chối.

`LEGAL_ENTITY_ID`, `BOOK_ID`, `PERIOD`, `PROJECT_ID` bắt buộc cho JOB P1-A; `BRANCH_ID` phải hiện diện và có thể null như trên. BOOK, PROJECT và JOB phải cùng pháp nhân/nhánh/sổ/kỳ; PROJECT_ID của JOB và PROJECT phải khớp. `SOURCE_REF` và backup khi có phải cùng scope, bao gồm PROJECT_ID. `CONFIG_VERSION=P1-DEMO-1` phải xuất hiện và khớp ở gốc, BOOK, PROJECT và JOB; giá trị khác hoặc thiếu bị BLOCKED. `PERIOD` ở validator P1 này là tháng `YYYY-MM`; không tự chuyển kỳ hoặc mở rộng sang định dạng khoảng ngày.

Checkpoint P1 lưu `CONFIG_VERSION`, giai đoạn và SHA-256 của JSON cấu hình chuẩn hóa (sắp khóa, UTF-8, không khoảng trắng). Resume chỉ hợp lệ khi phiên bản, giai đoạn, fingerprint và trạng thái khớp sau khi kiểm lại schema; checkpoint thiếu phiên bản hoặc phiên bản khác bị BLOCKED, thay scope/config/metadata cũng bị BLOCKED. Đây là fingerprint cấu hình giả, không phải manifest từng tệp nguồn, không chống sửa đồng thời hoặc chứng minh tính xác thực. Không di trú ngầm checkpoint M1/M2/M3 cũ: chúng không có P1 version và không tương thích với `resume` P1; luồng cũ vẫn là luồng riêng, cần tích hợp/di trú được thiết kế và phê duyệt ở ticket khác.

## JOB_QUEUE
`JOB_ID | BOOK_ID | LEGAL_ENTITY_ID | BRANCH_ID | PROJECT_ID | PERIOD | JOB_TYPE | SOURCE_SNAPSHOT_ID | PRIORITY | STATUS | CHECKPOINT | OWNER | MODEL_USED | LAST_UPDATED | APPROVAL_REF | RESULT_REF`.

## TIMELINE
`RECORD_ID | LEGAL_ENTITY_ID | PROJECT_ID | CHANNEL | SOURCE_DATE | TRANSACTION_DATE | SOURCE_LINK | RAW_SHA256 | SOURCE_CONTEXT | LINKED_TRANSACTION_ID | STATE`.

## STAGING
`TRANSACTION_ID | LEGAL_ENTITY_ID | BRANCH_ID | PROJECT_ID | BOOK_ID | TRANSACTION_DATE | TYPE | AMOUNT_IN | AMOUNT_OUT | SETTLED_COST | EVIDENCE_RECORD_IDS | SOURCE_REF | STATUS | APPROVER | VERSION`.

## AUDIT_LOG
`EVENT_ID | JOB_ID | BOOK_ID | RECORD_ID | TRANSACTION_ID | ACTION | BEFORE_VERSION | AFTER_VERSION | APPROVER | APPROVAL_REF | RESULT | TIMESTAMP`.

## CROSS_BOOK_LINK
`LINK_ID | FROM_BOOK_ID | TO_BOOK_ID | FROM_TX | TO_TX | LINK_TYPE | AMOUNT | EVIDENCE | STATUS | REVIEWER`.

## Các bất biến cần test
1. Một `JOB_ID` không ghi sang `BOOK_ID` khác, kể cả Sheet tab trùng tên.
2. `BOOK_ID + TRANSACTION_ID + VERSION + ACTION` là khóa idempotency đề xuất cho ghi tương lai; việc ghi phải theo sổ, có khóa và kiểm tra bản ghi trước/sau.
3. Hai BOOK khác có mã ngân hàng giống nhau không tự động coi là trùng/xóa; chuyển liên sổ chỉ liên kết đối chiếu.
4. Ảnh nguồn có thể trùng nội dung do gửi lại; vẫn giữ RECORD_ID/timeline theo từng lượt nhận và đánh dấu linked duplicate; không nhân đôi khoản chi.
5. Thao tác ghi thật phải có người/phiên bản được duyệt, kiểm tra nguồn và quyền. Bản đầu **không có live writer**.
6. Trạng thái lỗi/quota không làm các sổ khác ngừng; không báo DONE nếu chưa xác minh.
