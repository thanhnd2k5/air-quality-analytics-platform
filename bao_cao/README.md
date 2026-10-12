# bao_cao/ — Sản phẩm nộp BTL INT1422

| File | Nội dung | Trạng thái |
|---|---|---|
| `BaoCao_BTL_INT1422.docx` (+ `.pdf` xem trước) | Báo cáo 19 trang theo 5 phần việc của Bài 12 | Bản nháp đầy đủ; nhóm điền ô [..] |
| `Slide_BTL_INT1422.pptx` (+ `.pdf`) | 15 slide, khung 2-3-4-4-2 phút, có speaker notes | Nhóm điền tên ở slide 1 và 15 |
| `BANG_PHAN_CONG.md` | Bảng phân công theo phần việc + phân công trình bày | **Nhóm điền** |
| `KHAI_BAO_AI.md` | Khai báo dùng AI (phần Claude Code đã ghi sẵn) | **Nhóm bổ sung + xác nhận** |
| `BIEN_BAN_HOP_TEMPLATE.md` | Mẫu biên bản họp | Ghi biên bản thật mỗi buổi |

## Sinh lại báo cáo và slide từ số liệu mới nhất

Mọi con số trong `.docx` và `.pptx` đều được đọc từ `artifacts/` lúc build. Sau khi `python scripts/run_all.py` chạy lại, chỉ cần:

```powershell
pip install -r bao_cao/requirements.txt
python bao_cao/build_report.py
python bao_cao/build_slides.py
# Windows + Office: cập nhật mục lục và xuất PDF
powershell -ExecutionPolicy Bypass -File bao_cao/finalize_office.ps1
```

Nếu không dùng script PowerShell: mở `.docx` trong Word, chuột phải vào mục lục → **Update Field**.

> Build lại sẽ ghi đè file `.docx`/`.pptx`. Nếu nhóm đã sửa tay trong Word/PowerPoint, hãy lưu bản sửa ở tên khác hoặc chuyển phần sửa vào script.

## Việc nhóm cần tự làm trước khi nộp

1. Điền tên, MSSV, số nhóm, lớp, giảng viên (trang bìa, Phụ lục B, slide 1 và 15).
2. Điền `BANG_PHAN_CONG.md` và `KHAI_BAO_AI.md` (phần 2 và 3).
3. Commit theo đúng người phụ trách từng phần (bằng chứng CLO3).
4. Tập demo OLAP trực tiếp: `cd dashboard/web && npm run dev` → `/olap`. Phương án dự phòng là `notebooks/olap/olap_demo.ipynb`.
