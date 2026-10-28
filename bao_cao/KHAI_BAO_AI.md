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

## 1b. Claude Code — phiên ngày 28/10/2026

- **Công cụ:** Claude Code (Anthropic), mô hình Claude Opus 5.5, chạy trên máy của thành viên nhóm.
- **Yêu cầu của nhóm:** tăng tốc dashboard, làm lại giao diện cho chuyên nghiệp, kiểm tra vai trò của biến thời tiết. Nhóm có thử đổi bài toán chính sang PM2.5(t+6) rồi yêu cầu hoàn tác; bài toán chính vẫn là t+1.

| Hạng mục | Việc AI đã làm | File chính |
|---|---|---|
| Hiệu năng | Bộ nhớ đệm phản hồi phía API (tự làm mới khi dữ liệu trong kho thay đổi) và bộ nhớ đệm phía trình duyệt | `dashboard/api/app/cache.py`, `dashboard/web/src/api/client.ts` |
| Giao diện | Thiết kế lại dashboard (theme, bảng màu mức PM2.5, các trang Tổng quan, OLAP, Cảnh báo, Phân cụm, Thời tiết, Dự báo, Bản đồ); bỏ trang Phát lại khỏi menu | `dashboard/web/src/` |
| OLAP | Thêm độ đo "Số giờ PM2.5 ≥ 115"; nhóm thuộc tính, roll-up/drill-down theo phân cấp, bộ lọc, mẫu nhanh, liên kết URL | `routers/olap.py`, `OlapPage.tsx` |
| Thời tiết | Thêm áp suất, điểm sương vào mart và API | `mart_pollution_weather.sql`, `routers/weather.py` |
| Thử nghiệm | Bỏ biến thời tiết khỏi mô hình ở tầm 1/3/6 giờ để đo đóng góp (kết quả: đóng góp tăng theo tầm) | script thử nghiệm ngoài repo |
| Khai phá | Thử `HORIZON_HOURS` = 6 rồi hoàn tác về 1 và chạy lại `run_all.py --from classify` | `src/classification/constants.py` |
| Báo cáo & slide | Đoạn diễn giải cây quyết định đọc từ artifacts; chụp lại ảnh dashboard; ma trận nhầm lẫn đặt TP ở góc trên trái | `bao_cao/`, `artifacts/dashboard_screenshots/` |

Nguyên tắc như phiên trước: số liệu đọc từ `artifacts/`, AI không commit thay nhóm.

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
