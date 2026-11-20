# P1-MANIFEST — xác minh nguồn dữ liệu giả cho nhiều sổ

**Phạm vi:** G0-DEMO, chỉ các tệp CSV giả do dự án tạo và chỉ đọc nguồn. `PILOT_READ` trong validator là tên *mô phỏng kiểm tra hợp đồng*, **không phải** quyền pilot thật. Không truy cập MISA, Zalo, Google, mạng ngoài; không ghi vào Sheet/MISA và không tự kích hoạt writer.

## Những gì đã xây dựng

- `manifest_demo.py`: tạo và kiểm chứng manifest (định danh pháp nhân, chi nhánh, sổ, dự án, kỳ, niên độ qua P1 schema; snapshot id; mốc xuất có múi giờ; người xuất/xác minh giả; file id, tên tương đối, byte, SHA-256, số dòng CSV).
- Hash của manifest nằm trong `source_seal.json`, **không nằm trong chính manifest**. Checkpoint theo từng sổ và fingerprint của cấu hình P1 nằm trong tệp riêng; không tự chuyển đổi checkpoint M1–M3.
- `fixture_manifest_A.json`, `fixture_manifest_B.json` và `input-A/`, `input-B/` là các nguồn giả độc lập. Tệp `.SYNTHETIC_ONLY_P1` là dấu chặn chủ ý.
- `output-A/`, `output-B/` là các manifest, seal và checkpoint minh họa *đã tạo và kiểm chứng trên các fixture giả*, không phải chứng từ thật.
- `test_manifest_demo.py`: bộ kiểm thử cả trạng thái hợp lệ, sửa thêm/xóa file, đổi schema/config/scope, dữ liệu CSV sai phạm vi, đường dẫn traversal, symlink, khôi phục checkpoint, nhiều sổ đồng thời và thử CLI.

## Cách chạy trên Windows trong Orca (Python 3.10+)

Mở terminal tại thư mục `orca-demo-multi-book`, dùng lệnh `py -3` nếu có, hoặc đường dẫn Python runtime do Orca cung cấp:

```powershell
py -3 staging\demo\p1-manifest\test_manifest_demo.py -q
py -3 staging\demo\p1-manifest\manifest_demo.py verify --document staging\demo\p1-manifest\fixture_manifest_A.json --source-root staging\demo\p1-manifest\input-A --output-dir staging\demo\p1-manifest\output-A
py -3 staging\demo\p1-manifest\manifest_demo.py verify --document staging\demo\p1-manifest\fixture_manifest_B.json --source-root staging\demo\p1-manifest\input-B --output-dir staging\demo\p1-manifest\output-B
```

Chỉ có lệnh `create` tạo thư mục đầu ra mới. Lệnh `verify` chỉ đọc toàn bộ các tệp nguồn, manifest, seal, checkpoint rồi trả `VERIFIED_SYNTHETIC_ONLY` (exit `0`) hoặc `BLOCKED` (exit `2`). Khi chạy `create`, phải dùng `--output-dir` **chưa tồn tại**; không ghi đè kết quả cũ. Ví dụ tạo lại sổ A vào thư mục mới:

```powershell
py -3 staging\demo\p1-manifest\manifest_demo.py create --document staging\demo\p1-manifest\fixture_manifest_A.json --source-root staging\demo\p1-manifest\input-A --output-dir staging\demo\p1-manifest\output-A-LAN2
```

**Mã này không có API cho dữ liệu thật.** CLI chỉ chấp nhận đường dẫn tài liệu, nguồn và đầu ra nằm trong `staging/demo`, yêu cầu dấu dữ liệu giả và mã nguồn đang được kiểm thử; không tự nhận file MISA hoặc Google Sheets. Muốn dùng dữ liệu thật phải thiết kế và nghiệm thu adapter mới riêng, G0-LIVE/G3/G4 và phân quyền đọc rõ ràng.

## Luật fingerprint và chống nhập nhầm sổ

1. P1 schema phải trả `READY_FOR_PILOT_READ_SIMULATION` và `DESTINATION_WRITE=false`; `OWNER`, `FISCAL_YEAR`, `SOURCE_REF` đều phải thỏa điều kiện giả lập.
2. `SOURCE_SNAPSHOT_ID` trong JOB bắt buộc khớp manifest. `SOURCE_REF`, `LEGAL_ENTITY_ID`, `BRANCH_ID`, `BOOK_ID`, `PROJECT_ID`, `PERIOD`, fingerprint cấu hình phải khớp.
3. Chỉ chấp nhận CSV UTF-8 có header, số cột mỗi dòng đồng nhất. Nếu CSV tự khai cột phạm vi (`LEGAL_ENTITY_ID`, `BRANCH_ID`, `BOOK_ID`, `PROJECT_ID`, `PERIOD`) thì kiểm **mọi dòng**. Những file không khai đủ cột chỉ được bảo đảm bằng metadata + hash, không coi là xác minh nguồn chính thức.
4. Tất cả file trong thư mục nguồn phải được liệt kê. Không chấp nhận file thêm/bớt, thư mục symlink, đường dẫn `..`, tên trùng không phân biệt hoa/thường trên Windows, file trống, loại file khác CSV.
5. Mọi lần `verify` đều đọc lại bytes và đối chiếu SHA-256/size/số dòng; checkpoint cũ sai dấu hoặc khác nguồn/config => `BLOCKED`. Dữ liệu giả A hỏng không buộc ngừng B.
6. Bản hash và seal **không chứng minh** người xuất được ủy quyền hay dữ liệu ban đầu là đáng tin. Người có quyền sửa đồng thời manifest và seal có thể tạo hash mới; chống sửa có chủ đích cần kiểm soát quyền và chữ ký riêng.
7. Kiểm tra tệp giữa lúc đọc bằng `stat` trước/sau và cấm symlink; không tuyên bố chống mọi TOCTOU hoặc khóa file ở Sheets/MISA.

## Hợp đồng sao lưu đích (không sinh tệp backup thật)

`SOURCE_MANIFEST` là bản kiểm kê file **nguồn**. `LAST_SNAPSHOT` của P1 schema là bản sao lưu **đích trước khi ghi**, phải có `KIND=DEMO_DESTINATION_BACKUP`, `ID`, `DESTINATION_VERSION`, `PROTECTED_LOCATION_ID`, `SHA256`, `CAPTURED_AT` có timezone, `RESPONSIBLE_OWNER`, `RESTORE_TEST_ID`, `RESTORE_TEST` và cùng scope. Không dùng manifest nguồn làm backup đích. Mã P1-MANIFEST không cung cấp chức năng sao lưu hoặc thử khôi phục.

## Giới hạn nghiệm thu

Hoàn thành `P1-MANIFEST-A-002` **trong G0-DEMO**. Chưa nối checkpoint P1 vào `workflow.ps1`, chưa chạy các test PowerShell của M1–M3 trong môi trường Linux bàn giao này, chưa đọc bản xuất MISA thật, chưa kiểm sort/filter Google Sheets, chưa có reviewer độc lập G3. Không được gọi trạng thái đã xác minh này là `LIVE_READY`.
