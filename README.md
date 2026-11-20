# Orca / Codex - Multi-company Multi-book DEMO

Mã thử nghiệm ngoại tuyến chỉ dùng dữ liệu GIẢ cho nhiều công ty và nhiều sổ. Không kết nối MISA, Zalo, Google Sheets hoặc ngân hàng thật. Không dùng API trả phí.

## Kiểm thử Python (3.10+)

python tools/kiem_tra_demo.py --books data_gia/books.csv --jobs data_gia/jobs.csv
python -m unittest discover -s 05_KIEM_THU -p 'test_*.py'
python staging/demo/p1-schema/test_schema_demo.py
python staging/demo/p1-manifest/test_manifest_demo.py
python staging/demo/workbook-misa/test_envelope_demo.py

Bộ staging/demo/*.ps1 có các bài kiểm thử PowerShell chạy riêng trên Windows.

## Thành phần
- data_gia/: sổ, job của hai doanh nghiệp giả
- staging/demo/: workflow, Timeline và kiểm tra single writer
- staging/demo/p1-schema/: kiểm tra phạm vi/scope
- staging/demo/p1-manifest/: manifest SHA-256 và checkpoint nguồn
- 05_KIEM_THU/: unit tests offline
- 02_DIEU_PHOI/, 03_THIET_KE/, 04_MAU_BIEU/: nguyên tắc và mẫu

Trong Orca hãy đọc AGENTS.md, rồi dùng 00_PROMPT_DAN_VAO_ORCA.txt. Chưa nghiệm thu tích hợp với hệ thống kế toán thật. Không phải sản phẩm vận hành.

## Pilot thu chi DEMO (ngu?n P1 d� ni�m phong)

M� Python ? staging/demo/pilot-cash x? l� ngu?n CSV gi? sau khi x�c minh P1 v� sinh d? xu?t READY_FOR_OWNER/NEEDS_REVIEW; kh�ng c� quy?n ghi s? th?t. Xem 03_THIET_KE/PILOT_CASH_ARCHITECTURE.md, 02_DIEU_PHOI/ROADMAP_CASH_PILOT.md v� staging/demo/pilot-cash/README.md d? ch?y th?.
