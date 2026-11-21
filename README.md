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

## D2/D3 — Bộ kiểm thử 20 ca thu chi (chưa được phê duyệt nghiệp vụ)

- staging/demo/README_P1_M3_BRIDGE.md: tạo, niêm phong, xác minh snapshot đúng 1 sổ rồi chạy M3 trên cùng CSV. Không cấp live writer.
- staging/demo/pilot-cash/README_CASES20.md: 20 ca giả từ workbook người dùng đã gửi; tạo 9 đề xuất chờ duyệt và 11 việc cần đối chiếu; xuất CSV draft.
- Workbook gốc không được đẩy lên Public. Các kết quả khớp 20/20 chỉ là đối chiếu với quy tắc kỳ vọng chưa được chủ nghiệp vụ xác nhận.

## Integrated P0/P1 evidence demo (Windows)

See staging/demo/README_CASH_REVIEW_FLOW.md. The new
cash_review_flow.py runs P1-sealed M3 on structured synthetic evidence
and produces review-only staging/reconciliation files. workflow.ps1
now requires P1 proof for normal invocations. No real approvals or writes.

## P3 simulated review and audit

See staging/demo/README_REVIEW_DECISIONS_DEMO.md. This is a SIMULATION of
human decisions (with role labels but no real identity authentication).
It never writes into the main cash book. G3 and live approval remain pending.
