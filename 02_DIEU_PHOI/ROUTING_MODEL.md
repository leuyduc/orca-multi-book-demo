# Phân công model / reasoning effort cho Orca + Codex

**Nguồn:** OpenAI model selection (https://developers.openai.com/api/docs/guides/model-selection), GPT-6.2 in Codex (https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex), Orca native Chat (https://orca.dev/docs/agents/native-chat), Orca orchestration (https://orca.dev/docs/cli/orchestration).

**Không cố định model không có trong tài khoản.** Xác nhận từ model picker đang chạy; phiên bản Codex CLI ≥0.166.0 cho 6.2. Model/effort của từng worker có thể đặt qua UI hoặc CLI Orca (Orchestration còn experimental). Giữ một model mặc định cho đa số việc để tránh mất quota chuyển vòng liên tục.

| Loại JOB | Agent | Model ưu tiên | Effort | Khi nào dùng | Phải kiểm tra |
|---|---|---|---|---|---|
| Phân rã yêu cầu, lập ticket, tổng hợp tiến độ | Coordinator | GPT-6.2 Sol | Medium | Mỗi đầu việc lớn, không lặp mỗi chứng từ | Không sửa nguồn thật; hoàn tất checkpoint |
| Viết Python, Apps Script, CSV import, bộ kiểm thử | Builder | GPT-6.2 Sol | Medium | Mặc định | Unit tests, dữ liệu giả, diff |
| Chuyển cấu trúc/hàng chờ sang mẫu chuẩn ngắn | Preparer | GPT-6 Luna | Low | Khi đầu vào đã rõ, mẫu đầu ra chặt | Không tự định khoản; không điền thiếu |
| Đọc ảnh chứng từ, kiểm UI trên screenshot **được cấp quyền** | Visual reviewer | GPT-6.1 Terra | Medium | Chỉ khi cần nhìn ảnh; dữ liệu nhạy cảm phải được cho phép | Người duyệt rà số tiền/ngày |
| Rà thiết kế đa sổ, race condition, idempotency, phân quyền | Architect/Independent QA | GPT-6.2 Astra | High | Các gate quan trọng, không thường xuyên | Báo lỗi và bằng chứng thử |
| Lỗi khó kéo dài hoặc xung đột nguồn | Escalation | GPT-6.2 Astra | High, cân nhắc Xhigh | Chỉ nếu Sol thất bại và có test tái hiện | Giới hạn phạm vi, so trước/sau |
| So tổng bảng, nhóm vật tư, nhận trùng mã chính xác | **Không dùng AI** | Apps Script / Python | — | Lịch chạy thường xuyên | Công thức và đối soát độc lập |

### Tối ưu quota
- Ngày thường: **0 phiên Orca bắt buộc**. Xử lý theo lô bằng mã không gọi AI; chỉ ngoại lệ hay thay đổi phần mềm mới khởi Codex.
- Khi phát triển: 1 Coordinator Sol, 1 Builder Sol; chỉ bật reviewer Astra **cuối mỗi mốc**. Không để nhiều agent đồng thời đọc cùng một bộ hồ sơ.
- Dừng/kết thúc phiên khi xong; tránh dùng context khổng lồ. Mỗi nhiệm vụ gửi tối đa vài tệp liên quan, mã IDs, link nguồn đúng quyền và checkpoint; không gửi cả lịch sử riêng tư.
- Mọi phiên Codex và Work trên **cùng một Plus chia sẻ hạn mức Work/Codex**. Chạy nhiều agent song song tiêu thụ cùng hạn mức, không biến nó thành quota cộng gộp.
- Có nhiều tài khoản Plus chỉ quản lý được phiên/hạn mức **riêng** theo cơ chế Orca. Không tự xoay tài khoản để lách rate-limit; không dùng Auto Hand-off plugin trên dữ liệu thật.

### Quy tắc chuyển model
1. Bắt đầu Sol/Medium; nếu việc quá hẹp, đã có quy tắc và cần 1 lần soạn/đọc, chọn Luna/Low.
2. Nếu cần đọc ảnh/nhận diện giao diện, Terra/Medium (cần phép với chứng từ thật).
3. Nếu phát hiện xung đột nhiều sổ, thiết kế ghi tiền, hiệu ứng pháp lý: chuyển sang Astra/High **để REVIEW**, không cho tự sửa thực tế.
4. Không dùng hai model cùng giải một bài dễ; chỉ reviewer độc lập cho phần rủi ro cao.
5. Model picker không có model được nêu → chọn model còn hỗ trợ tương đương theo khuyến nghị hiện hành, ghi rõ tên thực tế vào `MODEL_USED` của ticket.

### Orca CLI (ví dụ *minh họa*, chưa chạy)
```powershell
orca status --json
orca orchestration run-create --objective "Offline multi-book prototype" --json
orca orchestration task-create --task-title "Demo reconciliation" --spec "Use synthetic data; no live reads" --json
# Thay <TASK_ID> và <MODEL_ID_DANG_CO> bằng kết quả thực của CLI/model picker.
orca orchestration worker-start --task <TASK_ID> --worktree current --agent codex --model <MODEL_ID_DANG_CO> --effort medium --json
```
`--model/--effort` là cờ theo phiên worker, không phải các biến môi trường giả định. Orca Orchestration cần bật Experimental, một số panel không khả dụng; có thể chỉ dùng giao diện tạo worktree/agent, không bắt buộc CLI điều phối.
