# P1 → Cash Pilot (chỉ dữ liệu giả)

Luồng này kiểm tra manifest P1 đã niêm phong, đọc bảng chứng từ CSV và tạo một file **đề xuất chờ duyệt**. Không gọi workflow M3 PowerShell, writer, API hay hệ thống thật.

## Chạy thử từ gốc repository

1. Niêm phong nguồn giả (chạy đúng một lần; output phải chưa tồn tại):

    python staging/demo/p1-manifest/manifest_demo.py create --document staging/demo/p1-manifest/fixture_manifest_A.json --source-root staging/demo/p1-manifest/input-A --output-dir staging/demo/pilot-cash/_output/manifest-A

2. Lập đề xuất thu chi sau khi xác minh SHA256:

    python staging/demo/pilot-cash/pilot_cash_demo.py --document staging/demo/p1-manifest/fixture_manifest_A.json --source-root staging/demo/p1-manifest/input-A --manifest-dir staging/demo/pilot-cash/_output/manifest-A --output-dir staging/demo/pilot-cash/_output/proposals-A

3. Chạy test:

    python staging/demo/pilot-cash/test_pilot_cash_demo.py

Đầu ra JSON: staging/demo/pilot-cash/_output/proposals-A/cash_proposals.json.

Fixture A: 3 bằng chứng, 2 giao dịch đề xuất; 1 giao dịch bill + chuyển khoản đủ điều kiện **trình duyệt**, 1 giao dịch thiếu chuyển khoản cần kiểm tra. Không tự xem đề xuất là đã duyệt và không tự ghi.

Nếu chạy lại với chính bản nguồn/manifest/đầu ra: ALREADY_PREPARED. Thay đổi file nguồn sau khi niêm phong sẽ bị BLOCKED. Không xóa/ghi đè snapshot cũ để che giấu sự thay đổi; nếu cần thử kịch bản mới thì tạo bộ giả mới với manifest và thư mục output riêng.

Tất cả _output đều bị gitignore, không commit dữ liệu khác giả định hoặc tài liệu khách hàng. Manifest hash không chứng minh một chứng từ là thật hoặc được phép sử dụng.

**Trạng thái:** D1 DEMO, chưa nối trực tiếp P1 với workflow.ps1 của M3, chưa có giao diện duyệt, người duyệt có danh tính xác thực, ghi Sheet/MISA, backup hay hậu kiểm live.