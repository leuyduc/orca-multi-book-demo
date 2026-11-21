# D2 — P1 manifest kết nối M3 theo từng sổ (offline DEMO)

m3_p1_bridge.py tạo snapshot độc lập cho mỗi sổ từ bốn CSV giả books.csv, queue.csv, projects.csv, evidence.csv. Snapshot lọc đúng pháp nhân/chi nhánh/sổ/kỳ/công trình rồi niêm phong bằng manifest SHA-256 P1. Chính những byte đó được M3 PowerShell đọc.

## Chạy trên Windows từ gốc repo

    python staging/demo/m3_p1_bridge.py prepare --book DEMO-A-CASH-2026
    python staging/demo/m3_p1_bridge.py verify --book DEMO-A-CASH-2026
    python staging/demo/m3_p1_bridge.py run --book DEMO-A-CASH-2026

Sổ B dùng --book DEMO-B-MISA-2026. A/B có sandbox và checkpoint riêng tại staging/demo/_p1_m3/<BOOK_ID>, nơi này bị Git ignore.

- prepare: tạo snapshot mới và seal/checkpoint; thư mục đã có thì BLOCKED, không tự làm lại khi nguồn thay đổi.
- verify: P1 kiểm file/scope/hash/checkpoint; chưa gọi M3.
- run: P1 verify trước; gọi M3 trên chính snapshot đó; P1 verify sau, xác nhận trạng thái/kết quả M3. Rerun không nhân đôi trong DEMO.
- Nguồn đổi, file thiếu/thêm, scope sai, manifest/checkpoint hỏng: BLOCKED. Lỗi A không buộc B ngừng.

Giới hạn: workflow.ps1 cũ còn tồn tại để chạy hồi quy, không tự buộc P1 nếu chạy trực tiếp, vì vậy luồng verified phải dùng bridge. Verify trước/sau không thể chứng minh chặn mọi thay đổi đồng thời. Chưa có transaction/lock của Google Sheets hay MISA. Không kết nối hệ thống thật, không có AI API trả phí, phê duyệt thật hoặc writer.

VERIFIED_M3_SYNTHETIC_ONLY không đồng nghĩa LIVE_READY.
