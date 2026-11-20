# Chính sách quota: ưu tiên giảm lượt AI, không gộp giới hạn Plus

**Mục tiêu:** 0 API trả phí, 0 agent Codex thường trực, <100 hồ sơ/ngày tổng tất cả công ty.

1. 80–95% bước có thể mô tả bằng quy tắc được thực hiện bằng mã miễn phí **khi mã đã được xây và test**, không kết luận tỷ lệ thực tế trước khi đo.
2. Không dùng Codex để đọc lại ảnh/sao kê mỗi lần làm dashboard. Chỉ tổng hợp bằng mã trên dữ liệu đã xác minh.
3. Một phiên AI chỉ nhận một `JOB_ID`, khoảng dữ liệu nhỏ, có checkpoint, giới hạn nguồn đọc.
4. Mặc định Sol Medium; Luna Low cho mẫu hẹp; Astra High cho gate rủi ro, không làm nền cho mọi việc.
5. Đo theo tuần: số job; số phiên AI; tổng thời gian Codex; số lần phải làm lại; lỗi định tuyến; chênh lệch phát hiện; số hồ sơ chờ duyệt. Không coi số tokens ước lượng là quota của OpenAI nếu API không cung cấp con số đó.
6. Work và Codex chia hạn mức trên cùng tài khoản Plus (theo tài liệu OpenAI). Nhiều Plus không cộng quota; Orca chỉ điều phối phiên và xem trạng thái từng tài khoản.
7. Không tăng số agent chỉ vì có thêm sổ. `JOB_QUEUE` tăng, không cần tăng agent đồng tỷ lệ. Ưu tiên batch và chốt ngoại lệ.

**Ngưỡng khuyến nghị (giả định để thử, không phải giới hạn nhà cung cấp):** tối đa 2 agent chạy song song trên một tài khoản Plus; một reviewer Astra chỉ khởi động khi Builder xong; kiểm Usage trước một việc lớn. Các ngưỡng này điều chỉnh sau khi có dữ liệu thực tế.
