# Lộ trình pilot thu chi — 1–2 sổ, dưới 100 hồ sơ/ngày

Mục tiêu: giảm việc nhập tay, không dùng API AI trả phí và luôn có người duyệt trước khi ghi. Chỉ phát triển trên dữ liệu GIẢ cho đến khi có ủy quyền nguồn, pháp nhân, sổ, kỳ và thao tác cụ thể.

| Mốc | Nội dung | Nghiệm thu | Trạng thái |
|---|---|---|---|
| D0 | M1–M3 PowerShell demo và P1 schema/manifest | Test gốc đạt, sổ A/B độc lập | Có nền tảng |
| D1 | P1 niêm phong CSV → tạo đề xuất thu chi và ngoại lệ | Ghép bill/transfer 1 TX; không nhân đôi, thiếu bằng chứng chờ duyệt, fail closed | Đã có mã, chờ PR/QA |
| D2 | Gắn manifest P1 với đúng dữ liệu nguồn của workflow M3 | Chặn nguồn đổi, không chấp nhận manifest của nguồn khác, checkpoint version mới rõ ràng | Chưa làm |
| D3 | Bảng điều hành DEMO + mô phỏng duyệt tách vai trò, chỉ ghi bản nháp vào vùng thử | Scope, người duyệt, version và hash phải khớp, không tự ghi thật | Chưa làm |
| G3 | Rà bảo mật, idempotency, cross-book, race/retry độc lập | Risk register + người duyệt + bằng chứng test | Chưa làm |
| D4 | Parser file MISA/Sheets đã khử định danh, pilot chỉ đọc trên bản sao được phép | Kiểm 100% mẫu, không nhầm công ty/chi nhánh/kỳ | Chưa có quyền |
| D5 | Thử ghi trên bản sao Sheet sau duyệt, audit/rollback/restore | G5 PASS trước khi xin G6, không thay sổ thật | Chưa làm |
| D6 | Pilot thật một sổ, sau đó hai sổ độc lập khi cần | G0-LIVE/G4–G6 được duyệt riêng, hậu kiểm đầy đủ | Chưa làm |

## Dữ liệu sẽ cần ở giai đoạn D4

- Danh mục sổ, loại sổ, chi nhánh/kỳ và ID người duyệt (không đưa dữ liệu nhạy cảm lên public).
- 1–2 mẫu CSV/XLSX đã khử định danh và đúng định dạng sổ.
- Khoảng 10–20 tình huống đầu vào/đầu ra được người phụ trách xác nhận: bill + chuyển khoản, tạm ứng, quyết toán, trùng chứng từ, sai kỳ, sai công trình, thiếu bằng chứng.
- Nguồn đọc và vị trí lưu kết quả riêng được chủ dữ liệu cấp quyền, không chung với repo public.

## Cách giao Codex qua Orca

1. Mỗi ticket làm ở một branch; đọc AGENTS.md, tài liệu này và test mới nhất.
2. Tự làm DEMO đến điểm nghiệm thu, không hỏi thao tác kỹ thuật nhỏ.
3. Chạy Python/PowerShell tests, tạo PR và báo kết quả, checkpoint, rủi ro.
4. Chưa đạt G3 thì không gắn LIVE_READY. Không tự bật writer lên Sheet/MISA thật.