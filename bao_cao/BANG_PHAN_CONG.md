# Bảng phân công — BTL INT1422

> **NHÓM ĐIỀN.** Bài 12 yêu cầu: nộp bảng ghi rõ phần việc của từng thành viên. Mỗi người phải trình bày được phần của mình khi được hỏi. Thành viên không đóng góp sẽ bị trừ điểm riêng.
> Cột "Bằng chứng" nên trỏ tới commit/PR thật trên Git: `git log --author="<tên>" --stat`.

## Thành viên

| STT | Họ và tên | MSSV | Tài khoản Git |
|---|---|---|---|
| 1 | [Họ tên] | [MSSV] | [username] |
| 2 | [Họ tên] | [MSSV] | [username] |
| 3 | [Họ tên — xoá dòng nếu nhóm 2 người] | [MSSV] | [username] |

## Phân công theo năm phần việc bắt buộc

| Phần việc (Bài 12) | Sản phẩm trong repo | Phụ trách | Review | Bằng chứng (commit / PR) | % đóng góp |
|---|---|---|---|---|---|
| 1. Thu thập & tiền xử lý | `src/ingestion/`, `src/processing/`, `src/staging/`, `scripts/download_uci_dataset.py`, `docs/DATA_PREPROCESSING.md` | [Tên] | [Tên] | [PR #…] | [%] |
| 2. Thiết kế kho dữ liệu | `docs/DW_DESIGN.md`, `artifacts/dwh/figures/star_schema.png`, `dim_wind_direction.sql` | [Tên] | [Tên] | [PR #…] | [%] |
| 3. Cài đặt kho & tính khối | `dbt/air_quality_dbt/models/`, `tests/`, `mart_olap_cube.sql`, `scripts/run_olap_checks.py` | [Tên] | [Tên] | [PR #…] | [%] |
| 4. Dịch vụ OLAP | `sql/olap/olap_operations.sql`, `notebooks/olap/olap_demo.ipynb`, trang `/olap` | [Tên] | [Tên] | [PR #…] | [%] |
| 5. Chức năng khai phá | `src/classification/`, `scripts/run_classification.py`, trang `/canh-bao` | [Tên] | [Tên] | [PR #…] | [%] |
| Hạ tầng & chạy 1 lệnh | `docker-compose.yml`, `airflow/`, `scripts/run_all.py` | [Tên] | [Tên] | [PR #…] | [%] |
| Phân tích bổ trợ | EDA (`notebooks/eda/`), phân cụm (`src/clustering/`), hồi quy (`src/forecasting/`) | [Tên] | [Tên] | [PR #…] | [%] |
| Báo cáo & slide | `bao_cao/` | [Tên] | [Tên] | [PR #…] | [%] |

## Phân công trình bày (15 phút)

| Phần | Thời lượng | Slide | Người trình bày |
|---|---|---|---|
| Câu hỏi nghiệp vụ | 2 phút | 1–2 | [Tên] |
| Dữ liệu & làm sạch | 3 phút | 3–5 | [Tên] |
| Kho dữ liệu + demo OLAP trực tiếp | 4 phút | 6–9 | [Tên] |
| Kết quả khai phá + bằng chứng | 4 phút | 10–13 | [Tên] |
| Khuyến nghị & hạn chế | 2 phút | 14–15 | [Tên] |

## Lưu ý về bằng chứng Git (CLO3)

Tại thời điểm rà soát (12/10/2026), lịch sử Git có 2 danh tính tác giả. Một danh tính chứa gần như toàn bộ commit code, danh tính còn lại chủ yếu là commit merge PR. Giảng viên chấm CLO3 dựa trên "lịch sử kho mã", nên nhóm cần:
- để **mỗi thành viên tự commit** phần việc mình làm, dưới tài khoản của chính mình. Các thay đổi trong đợt hoàn thiện này đang chưa commit; nên chia ra commit theo đúng người phụ trách từng phần;
- review chéo qua Pull Request (người review để lại nhận xét);
- ghi biên bản họp (`BIEN_BAN_HOP_TEMPLATE.md`).
