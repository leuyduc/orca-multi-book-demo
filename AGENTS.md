# AGENTS.md — PUBLIC DEMO ONLY

Chỉ xây dựng và thử nghiệm trên dữ liệu GIẢ. Không truy cập, đọc hoặc sửa dữ liệu công ty thật.
Một JOB bắt buộc có JOB_ID, LEGAL_ENTITY_ID, BOOK_ID, PERIOD, SOURCE_SNAPSHOT_ID và ACTION. Thiếu hoặc lệch => BLOCKED.
Một tệp chứng từ gốc là một record Timeline; một giao dịch có thể có nhiều bằng chứng, không nhân đôi dòng tiền.
Không gộp nguồn, kỳ hay quyền duyệt giữa các sổ. Xác minh manifest, SHA-256, checkpoint trước khi xử lý.
Được tự sửa mã, test, commit trong demo. Không tự đăng nhập tài khoản MISA/Google/Zalo hay ghi hệ thống thật.
Không commit dữ liệu cá nhân, sao kê, chữ ký, khóa truy cập, session, cookies, thông tin khách hàng hoặc log máy.
Không tự xoay vòng tài khoản Plus để né hạn mức. Báo cáo đúng test thực đã chạy/chưa chạy.

Bộ ca thu chi D2/D3 có kết quả GIẢ chưa được người phụ trách xác nhận. READY_FOR_OWNER không phải APPROVED. Không tự ghi Nhật ký, không chép nguyên workbook hoặc file chứa thông tin cá nhân lên repo Public. Luồng M3 niêm phong dùng m3_p1_bridge.py; workflow.ps1 cũng phải kiểm P1, còn workflow_regression_test_only.ps1 là bản hồi quy giả và không được triển khai thật.

M3 workflow.ps1 direct invocations require P1 seal and have NO bypass flag.
Unsealed regression tests are isolated in workflow_regression_test_only.ps1
and MUST be excluded from any live deployment.
New review-only entrypoint: staging/demo/cash_review_flow.py; it does not
grant approval, read original photos or write any actual ledger.

P3 review_decisions_demo.py is a DEMO simulator only. Its mock reviewer label
does not authenticate any human. Actions DEMO_APPROVE/DEMO_REJECT/
DEMO_REQUEST_MORE never create posting permissions and must never be used to
authorize a real ledger write. Audit is versioned per DEMO event with previous hash, correction reason and timestamp; no authenticated identity or live authorization.

G3 review fixes: checkpoint amount_out and settled_cost must independently
match sealed evidence, even if checkpoint amount is unchanged. A structured
evidence match is NOT document verification. Business approval is forbidden
without original media, payee and payment reference checks; the 20-case
labels remain an unapproved business fixture.
