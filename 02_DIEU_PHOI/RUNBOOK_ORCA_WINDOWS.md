# Runbook Orca/Codex (Windows)

## Trước phiên đầu
1. Mở Settings → Agents: kiểm quyền **Manual / Ask for approval**; kiểm Arguments không còn `--dangerously-bypass-approvals-and-sandbox`. Một số phiên Orca mặc định có cờ rất rộng; **không tin riêng dòng dặn trong AGENTS.md thay cho quyền hệ thống**.
2. Settings → Agents/Chat UI: chọn Chat cho Codex nếu cần giao diện trao đổi/model pill; dùng Terminal cho gỡ lỗi kỹ thuật. Kiểm từng session đang mở, vì đổi mặc định không nhất thiết đổi quyền phiên cũ.
3. Settings → Agents → Codex: xem trạng thái đăng nhập và Usage. Nếu có nhiều tài khoản thuộc quyền, sử dụng account switcher thủ công. Phiên đang chạy có thể giữ tài khoản cũ; tạo phiên mới/khởi động lại mới chắc chắn áp dụng tài khoản mới.
4. Settings: cân nhắc **tắt Share Codex history across accounts** trước khi trao đổi hồ sơ nhạy cảm; lưu ý việc tắt sau đó không thể thu hồi lịch sử đã chia sẻ. Tránh đồng bộ lịch sử giữa tài khoản thuộc những tổ chức khác nhau.
5. Bật Experimental Orchestration **chỉ khi** cần Runs/Tasks/Dispatch, đã hiểu CLI và đã nghiệm thu M0. Cách đơn giản hơn: tạo worktrees độc lập bằng UI, handoff file checkpoint.

## Cách mở một JOB
- Tạo worktree từ branch sạch cho từng JOB code; đặt tên `job/<JOB_ID>` và xác minh đúng repo.
- Chọn **Codex + model theo ROUTING_MODEL.md**.
- Dán prompt mẫu trong `04_MAU_BIEU/TICKET_PROMPT.md`, thay ID nguồn đã kiểm chứng; không dán toàn bộ bản riêng tư.
- Cho chạy test offline, reviewer đọc diff, sau đó mới merge code vào branch chính. Worktree chỉ bảo vệ filesystem code, không bảo vệ Sheets thật.

## Tài khoản Plus thứ hai (nếu mua, tùy điều khoản tài khoản/thiết bị)
- Không chia sẻ mật khẩu hoặc token giữa người dùng. Không tự xoay tài khoản để né giới hạn.
- Orca: Settings → Agents → Codex Accounts, thêm tài khoản theo hướng dẫn Orca trên máy sở hữu tài khoản; nhãn `PLUS_A`, `PLUS_B` chỉ là local label.
- Thời điểm chọn: **trước khi mở JOB mới**. Không đổi nóng giữa một JOB đang sửa dở, trừ khi đã có checkpoint đầy đủ, không nhầm phiên đăng nhập.
- Cùng mã nguồn code có thể tiếp tục từ Git commit/checkpoint; không coi lịch sử hội thoại là nguồn duy nhất.

## Handoff khi bị ngắt / thiếu quota
1. Worker ghi tệp checkpoint theo `04_MAU_BIEU/CHECKPOINT_MAU.md`: JOB, sổ, trạng thái, file đã đổi, lệnh đã chạy, nguồn và lỗi.
2. `git status`, commit nháp an toàn chỉ trong repo nếu được phép; không push dữ liệu nhạy cảm. Nếu chưa commit, lưu diff và nói rõ.
3. Chỉ mở phiên mới sau khi xác nhận model, tài khoản, repo, worktree, dữ liệu; đọc checkpoint trước và **không chạy lại việc đã ghi thành công**.
4. Nếu quota hết: dừng phần AI, giữ hàng đợi `BLOCKED_QUOTA`/`QUEUED`, để Apps Script/Python deterministic tiếp tục công việc độc lập. Không Auto Hand-off plugin làm ghi sổ thật.

## Các cấm quan trọng
- Không tự mở máy chủ, trả tiền API, cài plugin không kiểm duyệt với full disk access.
- Không tạo remote GitHub public chứa thông tin pháp nhân, link nội bộ hoặc nhân viên.
- Không dùng session tự động đăng nhập MISA/thuế/Zalo qua cookie, trình duyệt đang mở của người khác.
- Không cấp một bot quyền ghi cho nhiều pháp nhân trước khi có RBAC và test định tuyến.
