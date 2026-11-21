# 20 ca nghiệp vụ thu chi — DEMO chưa duyệt

Nguồn: hai workbook dữ liệu GIẢ do người dùng cung cấp ngày 21/11/2026. KHÔNG đưa workbook gốc lên repository Public; chỉ commit fixture đã chuẩn hóa, không có dữ liệu thực.

## Những gì được kiểm thử

- cases20_demo.json: 20 ca TC01–TC20, nhãn tình huống do người thiết kế fixture gán rõ ràng; không có ảnh bill thực.
- case20_engine.py: bộ quy tắc xác định phân loại, trạng thái, Thu/Chi ĐỀ XUẤT; không có API ghi.
- test_case20_engine.py: đối chiếu 20 ca với kỳ vọng từ workbook, kiểm tạm ứng/quyết toán, sai sổ, trùng mã, thiếu công trình và không tự duyệt.
- Ba đầu ra tại staging/demo/pilot-cash/_output/cases20: casebook_review.json, stagging_draft.csv, doi_chieu_draft.csv. Thư mục output bị Git ignore, không lưu lại trên GitHub.

## Chạy từ thư mục gốc repo

    python staging/demo/pilot-cash/test_case20_engine.py
    python staging/demo/pilot-cash/case20_engine.py --output-dir staging/demo/pilot-cash/_output/cases20

Chạy lại với cùng đầu ra: ALREADY_PREPARED. Đầu ra bị sửa thì BLOCKED, không ghi đè. Muốn thử lại cần thư mục đầu ra mới trong _output.

## Kết quả theo kỳ vọng ĐỀ XUẤT (chưa nghiệm thu)

- 20 ca, 9 READY_FOR_OWNER, 11 NEEDS_REVIEW/chặn/đối chiếu.
- Thu đề xuất 101.700.000 VND; Chi đề xuất 19.711.000 VND.
- Không có bút toán ghi thật, thuế đã xác nhận hay tiền chuyển thực tế.
- 20/20 khớp với workbook kiểm thử CHƯA được người phụ trách nghiệp vụ xác nhận.

## Cách áp dụng với template Sheets giả

Ba sheet nguồn: Nhật ký thu chi (hàng tiêu đề 8), stagging (hàng 6, giữ nguyên cách viết), Đối chiếu dòng tiền (hàng 3).

Bản xuất stagging_draft.csv giữ 16 vị trí cột theo template. Nhãn cột phản hồi được khử tên riêng thành Phản hồi người phụ trách. Khi dùng bản sao Sheet thật, cần kiểm cột bằng vị trí và schema, không thêm cột ngoài ý muốn.

Người chi, Người nhận, Hình thức và Bill/chứng từ để rỗng vì workbook 20 ca chỉ mô tả tình huống, không có chứng từ đã xác minh. READY_FOR_OWNER không đồng nghĩa hồ sơ đủ hay đã có quyền ghi.

Trạng thái Đã duyệt ở staging không kích hoạt ghi sổ. DEMO luôn đặt APPROVAL_STATUS=UNAPPROVED và DESTINATION_WRITE_ALLOWED=false.

## R01–R10

Các quy tắc từ workbook đề xuất gồm: bằng chứng thực thu/chi; chỉ một bên Thu/Chi và chống trùng; thiếu hóa đơn VAT; phân biệt tạm ứng và chi phí; quyết toán không nhân đôi chi; luân chuyển nội bộ ATM; thiếu mã/công trình/chênh tiền; lưu vết; duyệt không tự chuyển; và phân biệt dòng tiền quản trị với MISA/thuế.

Còn thiếu trước live: người phụ trách duyệt R01–R10; 10–20 giao dịch có kết quả đã xác nhận; đối chiếu công thức và phân quyền Sheets; kiểm duyệt có danh tính, backup/restore và hậu kiểm.
