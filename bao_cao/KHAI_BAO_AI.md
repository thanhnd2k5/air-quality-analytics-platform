# Khai báo sử dụng công cụ AI — BTL INT1422

> Bài 12: *"Nếu dùng công cụ AI hỗ trợ, phải khai báo rõ trong báo cáo."*
> Phần 1 do Claude Code ghi lại về chính phiên làm việc của nó. **Phần 2 và 3 nhóm phải tự điền và xác nhận.**

## 1. Claude Code — phiên ngày 12/10/2026

- **Công cụ:** Claude Code (Anthropic), mô hình Claude Opus 5.5, chạy trên máy của thành viên nhóm, thao tác trực tiếp trên repo.
- **Yêu cầu của nhóm:** đánh giá repo so với yêu cầu Bài 12, sau đó "fix hết các gap còn sót lại".

| Hạng mục | Việc AI đã làm | File chính |
|---|---|---|
| Đánh giá | Đọc slide yêu cầu (Bài 9, Bài 12), đối chiếu từng tiêu chí với repo | — |
| Khai phá (Phần 5) | Đổi bài toán chính sang phân loại cảnh báo PM2.5 ≥ 115: baseline, cây quyết định, HistGB, chọn ngưỡng trên val, ma trận nhầm lẫn, onset recall, McNemar, độ nhạy theo tầm | `src/classification/`, `scripts/run_classification.py`, `tests/unit/test_classification.py` |
| Thiết kế kho (Phần 2) | Thêm chiều Hướng gió + phân cấp; vẽ lược đồ sao; viết lý do chọn độ mịn, số khối con | `dim_wind_direction.sql`, `docs/DW_DESIGN.md`, `scripts/draw_star_schema.py` |
| Cài đặt & khối (Phần 3) | Khối `GROUP BY CUBE` (32 khối con), mart cảnh báo, dbt test mới, kiểm chứng từng ô của khối | `mart_olap_cube.sql`, `mart_pm25_alerts.sql`, `scripts/run_olap_checks.py` |
| OLAP (Phần 4) | 18 truy vấn cho 5 thao tác + ROLLUP/CUBE/GROUPING SETS; notebook demo; trang web `/olap` | `sql/olap/`, `notebooks/olap/`, `dashboard/.../OlapPage.tsx`, `routers/olap.py` |
| Ứng dụng | Trang `/canh-bao` + API; sửa lỗi biểu đồ ECharts 6 ở các trang cũ | `dashboard/` |
| Chạy 1 lệnh | `scripts/run_all.py`, script tải dữ liệu UCI; kiểm chứng chạy từ trạng thái trống | `scripts/run_all.py`, `scripts/download_uci_dataset.py` |
| Tài liệu dữ liệu (Phần 1) | Bảng tỷ lệ thiếu + cách xử lý từng cột; nguồn và giấy phép | `docs/DATA_PREPROCESSING.md`, `scripts/build_missing_table.py` |
| Báo cáo & slide | Script sinh bản nháp báo cáo .docx và slide .pptx từ số liệu thật | `bao_cao/build_report.py`, `bao_cao/build_slides.py` |

**Nguyên tắc đã tuân thủ:**
- Không có con số nào do AI tự viết ra. Mọi số liệu trong báo cáo/slide đều được script đọc từ `artifacts/`, sinh ra khi chạy code trên dữ liệu thật.
- Toàn bộ chuỗi đã được chạy lại từ trạng thái trống (`docker compose down -v`, xoá dữ liệu thô, rồi `python scripts/run_all.py`): 14/14 bước thành công, 130/130 dbt test pass, 58/58 unit test pass.
- AI không commit thay nhóm, không bịa tên thành viên hay biên bản họp.

## 2. Các công cụ AI khác — NHÓM ĐIỀN

`docs/PROJECT_CONTEXT.md` có ghi tài liệu được viết để "các phiên ChatGPT/AI sau hiểu dự án", tức là nhóm đã dùng AI ở các phase trước. Khai báo cụ thể:

| Công cụ | Thời gian / phase | Dùng vào việc gì | Thành viên sử dụng |
|---|---|---|---|
| [ChatGPT / Cursor / Copilot / …] | [Phase …] | [ví dụ: lập kế hoạch WBS, viết tài liệu kiến trúc, gợi ý code …] | [Tên] |
| | | | |

## 3. Cam kết — NHÓM XÁC NHẬN

- [ ] Nhóm đã đọc, chạy lại và hiểu toàn bộ phần do AI hỗ trợ, và giải thích được khi giảng viên hỏi.
- [ ] Nhóm chịu trách nhiệm về tính đúng đắn của mã nguồn, số liệu và báo cáo.

Chữ ký / họ tên các thành viên: ……………………………………
