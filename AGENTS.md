# AGENTS.md — PUBLIC DEMO ONLY

Chỉ xây dựng và thử nghiệm trên dữ liệu GIẢ. Không truy cập, đọc hoặc sửa dữ liệu công ty thật.
Một JOB bắt buộc có JOB_ID, LEGAL_ENTITY_ID, BOOK_ID, PERIOD, SOURCE_SNAPSHOT_ID và ACTION. Thiếu hoặc lệch => BLOCKED.
Một tệp chứng từ gốc là một record Timeline; một giao dịch có thể có nhiều bằng chứng, không nhân đôi dòng tiền.
Không gộp nguồn, kỳ hay quyền duyệt giữa các sổ. Xác minh manifest, SHA-256, checkpoint trước khi xử lý.
Được tự sửa mã, test, commit trong demo. Không tự đăng nhập tài khoản MISA/Google/Zalo hay ghi hệ thống thật.
Không commit dữ liệu cá nhân, sao kê, chữ ký, khóa truy cập, session, cookies, thông tin khách hàng hoặc log máy.
Không tự xoay vòng tài khoản Plus để né hạn mức. Báo cáo đúng test thực đã chạy/chưa chạy.
