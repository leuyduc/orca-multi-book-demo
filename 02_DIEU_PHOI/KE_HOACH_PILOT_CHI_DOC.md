# Kế hoạch chuẩn bị pilot chỉ đọc — 21/11/2026

**Trạng thái: DỰ THẢO, CHƯA DUYỆT PILOT.** Chấp nhận kết quả demo theo phạm vi người dùng đã chọn; không có quyền kết nối hệ thống, đọc dữ liệu thực hay ghi thật trong lượt này. Kế hoạch không tự cấp quyền hoặc làm thay đổi gate.

## 1. Bằng chứng và phạm vi rà

Đã đọc `GATES_NGHIEM_THU.md`, `HOP_DONG_DU_LIEU.md`, `M0_PRECHECK.md`, ticket trước, báo cáo M3, báo cáo workbook/MISA và xem mã `workflow.ps1`, `writer_sim.ps1`, `test_workflow.ps1`. Các nhận xét về các ca còn lại dựa vào báo cáo test của worker; không chạy lại test trong lượt chỉ lập kế hoạch, không xác thực độc lập toàn bộ code, log hay artifact. Đây là rà soát của coordinator trên một phần mã và tài liệu, **không phải G3 độc lập đã hoàn thành**. Git/commit chưa xác minh. M0 cũ ghi Python không sẵn trên PATH; báo cáo M3 sau đó ghi đã dùng Python trong runtime Codex chạy 15 unittest, không chứng minh lệnh `python` mặc định đã hoạt động.

Worker báo 18 + 29 + 15 + 13 + 15 = 90 kiểm tra/assertion của các bộ đếm, exit 0; không đồng nhất với 90 nghiệp vụ. Bản rà này chưa kiểm chứng lại log gốc hay chạy lại. M1 định danh giả A/B được báo đạt, bốn metadata vẫn CHƯA XÁC MINH. M2 validator độc lập fingerprint registry và JOB, không bao phủ project hoặc nguồn ngoài; workflow M3 có thêm fingerprint project/evidence giả nhưng chưa ràng buộc manifest nguồn được xác thực. Khóa tệp writer chỉ dùng cục bộ và writer không nối đích ngoài.

## 2. Ma trận 16 ca — đối chiếu bằng chứng đã báo

`PASS_SIMULATED` là trạng thái **theo báo cáo worker**, chỉ phản ánh kiểm thử giả được mô tả, không phải PASS độc lập hoặc nghiệm thu live. `PARTIAL` còn phần yêu cầu chưa chứng minh; `BLOCKED` khi thiếu điều kiện để thử. Không ca nào được cấp PASS live.

| Ca | Trạng thái | Bằng chứng theo báo cáo / giới hạn còn lại |
|---|---|---|
| 1 | PASS_SIMULATED | Timeline: bill và chuyển khoản chung tham chiếu; chưa đọc chứng từ thực. |
| 2 | PASS_SIMULATED | Timeline: lượt nhận lại giữ record, không nhân chi; hash fixture giả. |
| 3 | PASS_SIMULATED | Cùng tiền, tham chiếu khác không gộp trong fixture. |
| 4 | PASS_SIMULATED | Liên kết quyết toán/tạm ứng tường minh trong fixture bổ sung, không suy đoán. |
| 5 | PASS_SIMULATED | Hai tiến trình và checkpoint riêng; không chứng minh môi trường phân tán. |
| 6 | PASS_SIMULATED | Writer JSON khóa cục bộ; chưa có writer Sheet. |
| 7 | PASS_SIMULATED | Sai pháp nhân/sổ bị từ chối trong fixture. |
| 8 | PARTIAL | Sai kỳ/chi nhánh bị chặn trong bao tự thiết kế; không phải schema MISA. Kiểm bản xuất xác thực BLOCKED do chưa có mẫu và quyền. |
| 9 | PASS_SIMULATED | Mất phản hồi sau commit JSON, retry không thêm; chưa có đích ngoài. |
| 10 | PASS_SIMULATED | Test đổi version/registry/project/JOB/evidence giả; chưa kiểm thay đổi đồng thời trên đích thật. |
| 11 | PASS_SIMULATED | Mã giao dịch trùng ở hai sổ vẫn riêng trong fixture. |
| 12 | PASS_SIMULATED | Lỗi project hoặc khóa A không chặn B; không bao phủ mọi lỗi. |
| 13 | PASS_SIMULATED | Kiểm tra duyệt A không áp dụng B trong mô phỏng; chưa có quyền thực. |
| 14 | PASS_SIMULATED | Ngắt ở các điểm được chọn rồi resume; chưa crash tại mọi điểm ghi. |
| 15 | PARTIAL | SORT/FILTER tạo vùng kết quả trong workbook giả, có tính lại bằng engine cục bộ; chưa thử sort/lọc trực tiếp và toàn bộ công thức/link/filter/bảo vệ trên Google Sheets. Kiểm ứng dụng BLOCKED vì chưa có môi trường và quyền. |
| 16 | PASS_SIMULATED | Quota giả QUEUED và sai scope BLOCKED; chưa thử quota/quyền thực. |

Mọi ca PASS_SIMULATED phải được rà lại bằng log, phiên bản code và tiêu chí phù hợp với phạm vi tiếp theo. 14/16 là phân loại mô phỏng theo báo cáo, không phải 14 ca nghiệm thu thực.

## 3. Ticket đề xuất — chưa thực hiện

Mọi ticket dùng `LEGAL_ENTITY_ID=DEMO_A`, `BRANCH_ID=NA`, `BOOK_ID=DEMO-A-CASH-2026`, `PERIOD=2026-11`, `PROJECT_ID=DEMO-PROJECT-A`, `SOURCE_SNAPSHOT_ID=SYN_A_001` khi cần ví dụ; `PERMISSION_SCOPE=SYNTHETIC_ONLY`, `REVIEWER=OWNER` là nhãn giả. Áp dụng tương ứng sổ B bằng ticket và checkpoint riêng. `SYN_A_001` hiện chỉ là nhãn, không phải manifest đã xác minh.

| JOB_ID | Đầu vào → đầu ra | Điều kiện nghiệm thu; checkpoint dự kiến | Thay đổi dự kiến nếu được giao |
|---|---|---|---|
| P1-SCHEMA-A-001 | Hợp đồng và registry giả → đặc tả bốn trường, nullability theo giai đoạn, mối quan hệ pháp nhân/chi nhánh/sổ/dự án/kỳ, config version. | Test thiếu, sai và không khớp phải BLOCKED khi trường đó được quy định bắt buộc; không suy năm tài chính hoặc owner. `checkpoints/P1-SCHEMA-A-001.json`. | Tài liệu hợp đồng, fixture và test trong demo; không sửa nguồn gốc. |
| P1-MANIFEST-A-002 | Danh sách file giả → schema manifest nguồn theo từng tệp, hash manifest, metadata/scope/version; schema snapshot sao lưu đích riêng. | Sửa/thêm/xóa file, sai scope/kỳ/schema/config hoặc hash không khớp phải chặn resume; test tệp rỗng, trùng tên, thứ tự và manifest giả bị đổi. `checkpoints/P1-MANIFEST-A-002.json`. | Thiết kế và sau phê duyệt code/test giả trong staging. |
| P1-G3-003 | Phiên bản mã cố định, log, ma trận → báo cáo reviewer độc lập về idempotency, khóa, quyền, bất biến, checkpoint và cross-book. | Rà người khác không tự nghiệm thu phần mình xây; findings có mức độ, tái hiện, quyết định khắc phục và bằng chứng; commit hoặc hash đầy đủ được ghi. `checkpoints/P1-G3-003.json`. | Báo cáo/kiểm thử trên bản sao giả; reviewer do chủ chỉ định. |
| P2-MISA-008 | Mẫu CSV/XLSX được phép và schema được xác nhận → mapping, fixture khử định danh và test parser. | Nhận đúng mẫu; sai đơn vị/chi nhánh/kỳ, thiếu định danh hoặc sai schema phải BLOCKED; thiếu dữ liệu phạm vi yêu cầu xác nhận có thẩm quyền, không đoán theo tên file. `checkpoints/P2-MISA-008.json`. | Fixture, parser/test sau quyền riêng; không tự truy cập MISA. |
| P2-SHEET-015 | Sheet thử độc lập hoàn toàn bằng dữ liệu giả → kết quả trước/sau filter, filter view, sort toàn hàng và thêm dòng. | Theo RECORD_ID đối chiếu giá trị, công thức, hyperlink thật, tổng, filter, định dạng và bảo vệ; lỗi bất kỳ FAIL; log và ảnh trước/sau. `checkpoints/P2-SHEET-015.json`. | Chỉ Sheet thử được chỉ định và được duyệt, tuyệt đối không Sheet đang vận hành. |
| P3-PILOT-READ-001 | Một bản sao được phép, phạm vi một pháp nhân/sổ/kỳ/công trình → báo cáo đối chiếu và staging đề xuất tại vùng được cấp quyền. | Không sai pháp nhân/sổ/kỳ, không mất/ghi đôi record, mọi ngoại lệ NEEDS_REVIEW; đối chiếu thủ công 100% phạm vi pilot; không ghi nguồn. `checkpoints/P3-PILOT-READ-001.json` trong vùng được duyệt. | Chỉ sau G3/G0-LIVE/G4 và duyệt cụ thể phạm vi, vị trí đầu ra; không kích hoạt writer. |

### Đặc tả metadata đề xuất, chưa triển khai

- `FISCAL_YEAR`: bắt buộc đối với sổ kế toán khi vào pilot; lưu định danh năm tài chính và ngày bắt đầu/kết thúc theo cấu hình được chủ dữ liệu xác nhận. Không mặc định trùng năm dương lịch.
- `SOURCE_REF`: bắt buộc khi có nguồn; tham chiếu bền vững đến từng tệp/manifest trong phạm vi được cấp quyền, không chỉ tên tệp. Không ghi đường dẫn nhạy cảm vào log công khai.
- `OWNER`: bắt buộc trước pilot; ID người/bộ phận chịu trách nhiệm theo danh mục có thẩm quyền, phân biệt người duyệt. Không suy từ reviewer của job.
- `LAST_SNAPSHOT`: có thể null khi khởi tạo demo; trước hành động ghi thật phải có bản sao lưu đích được xác nhận, đủ metadata, hash và chứng cứ thử khôi phục. Quy định này là đề xuất, không chứng minh hiện tại đã tồn tại.

### Manifest nguồn và snapshot sao lưu đích

Manifest nguồn: `SOURCE_SNAPSHOT_ID`, `LEGAL_ENTITY_ID`, `BRANCH_ID` khi áp dụng, `BOOK_ID`, `PERIOD_START`, `PERIOD_END`, `SOURCE_SYSTEM`, `SOURCE_REF`, `EXPORT_TIMESTAMP` có timezone, `EXPORTED_BY`, `VERIFIED_BY`, `FILE_COUNT`, `ROW_COUNT` khi có thể xác định, `SCHEMA_VERSION`, `MANIFEST_VERSION`, `CONFIG_VERSION`, `VERIFICATION_STATUS`, danh sách file với ID/đường dẫn tương đối, kích thước, SHA-256 từng file và số dòng khi áp dụng. Hash manifest tính trên dạng chuẩn hóa được quy định rõ, **không bao gồm chính trường hash**; lưu hash/phiên bản ở bản ghi kiểm chứng tách riêng. Hash chứng minh nội dung không đổi so với bản đã ghi, không tự chứng minh nguồn đúng hay người xuất được ủy quyền.

Snapshot sao lưu đích là bản chụp trước thay đổi để khôi phục, có mã riêng, scope, thời điểm, version đích, vị trí được bảo vệ, hash, người chịu trách nhiệm và bằng chứng thử khôi phục. Không dùng snapshot nguồn làm bằng chứng khôi phục đích. Bất kỳ thay đổi có liên quan ở manifest/file/phạm vi/kỳ/config phải buộc đánh giá lại checkpoint; chính sách ổn định và chống TOCTOU cần thiết kế riêng cho môi trường đích.

## 4. Pilot chỉ đọc — đề xuất, chưa cấp quyền

- **Phạm vi:** một pháp nhân, một BOOK_ID, một kỳ, một PROJECT_ID; tất cả ID thật và khoảng thời gian CHƯA XÁC ĐỊNH. Người có thẩm quyền xác nhận nguồn, bản sao, chủ dữ liệu, người đối chiếu, reviewer và vị trí lưu kết quả trước khi tạo JOB.
- **Đầu vào:** bản sao hoặc export đã được cấp quyền, manifest đã xác thực, danh mục phạm vi, mapping và metadata hoàn chỉnh theo gate đã duyệt. Không tự đồng bộ liên tục và không mở thêm công ty.
- **Thực hiện:** xác thực scope/manifest; đọc bản sao; tạo đề xuất tại vị trí riêng được phép; đối chiếu thủ công 100% record/giao dịch và ngoại lệ; mọi dữ liệu không đủ căn cứ là NEEDS_REVIEW. Lệnh chỉ đọc nguồn không đồng nghĩa không ghi: vị trí lưu báo cáo/checkpoint riêng phải được cho phép.
- **PASS:** không có record sai pháp nhân/sổ/kỳ, không mất hoặc nhân đôi record, trace được chứng từ và manifest, 100% phạm vi đã đối chiếu, mọi ngoại lệ có người xử lý, không có ghi ngoài vùng đầu ra đã duyệt. Kết quả phải có người kiểm tra và chủ dữ liệu duyệt.
- **Dừng/FAIL:** sai phạm vi, thiếu định danh hoặc quyền, hash/config thay đổi, không truy được nguồn, lỗi đối chiếu, thao tác ngoài phạm vi hoặc thiếu bằng chứng. Lưu lý do BLOCKED và không tiếp tục bằng checkpoint cũ.
- **Bằng chứng:** bản duyệt scope, version mã/config, manifest/hash, thống kê nguồn/record/giao dịch, log hạn chế dữ liệu nhạy cảm, danh sách ngoại lệ, đối chiếu thủ công, kết quả và người duyệt. Kết quả pilot chỉ đọc không tự cấp quyền ghi.

## 5. Checklist G0-LIVE và gate ghi tương lai

Trước pilot chỉ đọc: [ ] ủy quyền nguồn, pháp nhân, sổ, kỳ, hành động, người và thời hạn; [ ] xác minh quyền thực tối thiểu và nơi lưu bản sao/đầu ra; [ ] xác minh danh mục/metadata/manifest và quan hệ phạm vi; [ ] mã/version cố định, test và G3 độc lập; [ ] kế hoạch bảo mật, lưu trữ, xóa theo chính sách và người xử lý sự cố; [ ] G4 được duyệt. Cấu hình phiên quyền rộng không phải cách ly; môi trường và quyền kỹ thuật phải được kiểm riêng.

Trước bất kỳ pilot ghi hay ghi thật trong tương lai, cần gate và ủy quyền riêng: [ ] duyệt BOOK_ID/JOB_ID/bản ghi/version/số tiền/hành động; [ ] single writer và khóa theo sổ; [ ] idempotency tại đích, xử lý mất phản hồi bằng đọc lại trước retry; [ ] kiểm tra version và xung đột ngay trước ghi; [ ] audit trước/sau và quyền sửa audit tách biệt; [ ] sao lưu đích, hash, quyền và thử khôi phục; [ ] đọc lại đích, đối chiếu số dòng/tổng/công thức/mã, lỗi không chắc chắn không DONE; [ ] kế hoạch dừng và rollback. LockService nếu được dùng chỉ điều phối các thực thi cùng cơ chế khóa, không khóa thao tác người dùng hoặc client khác; phải thiết kế kiểm soát xung đột bổ sung. MISA V1 chỉ đọc/đối chiếu; không tự động thanh toán, phát hành hóa đơn, ký hay nộp hồ sơ.

## 6. Quyết định và bước nhỏ tiếp theo

Đề xuất `P1-SCHEMA-A-001`: chốt đặc tả metadata và nullability **chỉ trên dữ liệu giả**, sau đó mới thiết kế manifest; trước khi viết code/fixture cần chỉ định phạm vi thay đổi và được giao riêng. Các tệp dự kiến: hợp đồng dữ liệu, fixture demo, test và checkpoint theo ticket; trong lượt lập kế hoạch này không sửa chúng. Chưa có quyền MISA, Google hay nguồn thực; khi cần thử P2/P3 phải xin ủy quyền cụ thể cho nguồn, hành động, pháp nhân, sổ, kỳ, người, thời hạn và vị trí đầu ra. Không tạo remote, mua API hay kết nối ngoài.
