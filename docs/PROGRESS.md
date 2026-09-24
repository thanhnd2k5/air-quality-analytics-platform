# Project Progress Log

Tài liệu ghi nhận tiến độ thực hiện theo từng phase của dự án.

---

## 2026-09-25

### Current phase
Phase 1 – Decision Gate + cập nhật tài liệu (**P1-39 → P1-50**)

### Completed
- Đóng **Decision Gate Phase 1** (P1-39 → P1-47) dựa trên `artifacts/data_profile/`.
- **P1-38:** thống nhất không vẽ chart ở Phase 1; để Phase 5 (EDA) và Phase 11 (Dashboard).
- **P1-48 / P1-49:** cập nhật `docs/DATA_GUIDE.md` (v1.2) — full 12-station profile, missing strategy sơ bộ, extreme/physical rules, bảng assumptions xác nhận/bác bỏ (§53).
- **P1-50:** cập nhật checkpoint này trong `PROGRESS.md` và trạng thái task trên WBS.

### Decisions (Decision Gate)
- **P1-39 Grain:** `station-hour` chính thức cho DWH.
- **P1-40 Timeline:** 12 trạm đồng nhất `2013-03-01 00:00` → `2017-02-28 23:00` (35,064 giờ/trạm).
- **P1-41 Station quality:** không loại trạm; chú ý gap pollutant dài tại Dongsi, Dingling, Shunyi, Wanliu (DQ flag).
- **P1-42 / P1-43 Missing:** weather = gap ngắn; pollutant = có long gap (đặc biệt CO/NO2/O3). Policy: UCI → Open-Meteo fill → short-gap impute + flag; pollutant target không fill / không tạo ground truth giả.
- **P1-44 Extreme:** giữ raw; `999`/`10000` đánh dấu điều tra EDA (`SUSPECT_CAP`); không xóa tại gate.
- **P1-45 Duplicate:** 0 duplicate thật.
- **P1-46 Physical:** 0 invalid negative; TEMP/DEWP âm hợp lệ.
- **P1-47 Station rules:** một policy toàn cục; không pipeline riêng theo trạm.

### Evidence
- `artifacts/data_profile/profiling_report.md` và 3 CSV summary.
- `docs/DATA_GUIDE.md` §2, §3, §11–13, §16, §18, §34, §48–49, §53.

### Next
- **P1-51:** commit profiling code + artifacts + docs — trong commit này.
- **P1-52:** mở PR / merge `feature/data-profiling` vào `main` để đóng Phase 1.
- Sau đó Phase 2 (Environment & Infrastructure: Docker, MinIO, Postgres).

---

## 2026-09-22

### Current phase
Phase 1 – Full Dataset Profiling

### Completed
- Hoàn thành **P1-01** (Thu thập đủ 12 file CSV PRSA UCI trong `data/raw/uci/`).
- Hoàn thành **P1-02** & **P1-03** (Tạo danh sách inventory file `data/raw/reference/file_inventory.csv`, xác nhận đúng 12 station, không thiếu/trùng file).
- Hoàn thành **P1-04** (Kiểm tra schema sơ bộ: 12/12 file đều có đúng 18 cột đồng nhất).
- Hoàn thành **P1-05** (Xác nhận mỗi file chỉ chứa dữ liệu của 1 trạm duy nhất).
- Hoàn thành **P1-06** (Kiểm tra raw dataset ngoài Git qua `.gitignore`).
- Hoàn thành **P1-07 đến P1-21** (Viết script `scripts/run_profiling.py` hoàn chỉnh, kiểm thử thành công trên `Aotizhongxin` và có thể tái sử dụng qua CLI).
- Hoàn thành **P1-22 đến P1-33** (Chạy profiling tự động toàn bộ 12 trạm, kiểm tra schema consistency, timeline continuity, missing values, extreme & negative values).
- Hoàn thành **P1-34 đến P1-37** (Tự động sinh 4 artifacts: `station_profile.csv`, `missing_summary.csv`, `extreme_value_summary.csv` và `profiling_report.md`).

### Evidence
- `data/raw/reference/file_inventory.csv`: Ánh xạ 12 trạm và file CSV thô.
- `artifacts/data_profile/station_profile.csv`: 12 trạm đều đạt chuẩn 35,064 giờ (tổng 420,768 dòng), 0 duplicate, 0 missing hours.
- `artifacts/data_profile/missing_summary.csv`: Thống kê missing % và longest missing run chi tiết cho từng trạm và biến.
- `artifacts/data_profile/extreme_value_summary.csv`: Thống kê min/max, percentiles, xác nhận 0 vi phạm giá trị âm ở các biến chất ô nhiễm và lượng mưa.
- `artifacts/data_profile/profiling_report.md`: Báo cáo đúc kết tổng hợp.

### Decisions
- Nháp căn cứ Decision Gate từ profiling (chính thức đóng ngày 2026-09-25 — xem entry trên).

### Next
- Họp Decision Gate Phase 1 (P1-39 đến P1-47) — **đã hoàn thành 2026-09-25**.
- Cập nhật `docs/DATA_GUIDE.md` (P1-48, P1-49) — **đã hoàn thành**.

---

## 2026-09-15

### Current phase
Phase 0 – Project Foundation (đã hoàn thành)

### Completed
- Thống nhất **working preference** cho Open-Meteo / RH / episodes (chưa khóa cứng sau Phase 5).
- Tạo seed tọa độ 12 trạm: `data/raw/reference/stations.csv` (nguồn ACP 2022 Supplement Table S1); điền `district` từ Skyviewor + PMC9510312.

### Decisions
- **RH:** derive trong ETL từ UCI `TEMP` + `DEWP` (không ưu tiên lấy RH từ Open-Meteo).
- **Open-Meteo enrichment:** ưu tiên `cloud_cover`; tối đa thêm 1 biến phụ nếu EDA ủng hộ.
- **Biến weather trùng UCI:** UCI primary; fill missing bằng Open-Meteo khi join được; flag/lineage nguồn.
- **Pollutant missing:** xử lý riêng; không fill bằng Open-Meteo.
- **PM2.5 episodes:** đưa vào Phase 8 (theo trạm + đa-trạm + gắn weather) và hiển thị trên dashboard Phase 11; ngưỡng chốt sau EDA.
- **Station coordinates:** dùng Foreback et al. 2022 ACP Supp. Table S1; status `LITERATURE`.
- **Station district:** Skyviewor 区县 + đối chiếu PMC9510312 (vd. Dingling → Changping); không gán theo tên trạm.
- Đã cập nhật `PROJECT_CONTEXT.md`, `DATA_GUIDE.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md` theo preference trên.

### Problems
- Một số paper khác ghi tọa độ lệch nhẹ — chốt một nguồn tọa độ (ACP S1).

### Next
- Tiếp tục Phase 0 còn lại (`.env.example`, README, docker-compose khung) rồi Phase 1 profiling.

---

## 2026-09-13

### Current phase
Phase 0 – Project Foundation

### Completed
- Khởi tạo repository và branch `main`.
- Thống nhất Git workflow giữa 2 thành viên (dùng nhánh `feature/...`, không commit code bừa bãi trực tiếp lên `main`).
- Checkout nhánh làm việc `feature/project-setup` cho Phase 0.
- Thiết lập cấu trúc thư mục hoàn chỉnh theo thống nhất (`src/`, `airflow/`, `dbt/`, `ml/`, `dashboard/`, `tests/`, `artifacts/`, `scripts/`, `data/`).
- Di dời 12 file CSV dữ liệu thô vào `data/raw/uci/` và thiết lập `.gitignore` loại trừ file dữ liệu lớn khỏi Git tracking.
- Khởi tạo các file `__init__.py` và `.gitkeep` để Git theo dõi khung thư mục.

### Evidence
- Trạng thái `git status` xác nhận 12 file CSV gốc trong `PRSA_Data_...` được đưa vào `data/raw/uci/` và không còn bị Git track trực tiếp.
- Khung thư mục đầy đủ các phân hệ và packages Python đã sẵn sàng.

### Decisions
- Giữ cấu trúc `artifacts/data_profile/` ở cấp root để lưu trữ kết quả phân tích theo đúng tài liệu `IMPLEMENTATION_PLAN.md`.
- Giữ nguyên `dbt/air_quality_dbt/` theo kiến trúc ban đầu trong `ARCHITECTURE.md`.
- Sử dụng `data/raw/uci/` phục vụ local development và dùng MinIO làm Data Lake chính thức của dự án.

### Problems
- Không có vướng mắc kỹ thuật lớn.

### Next
- Hoàn thiện `.env.example`, `README.md`, `docker-compose.yml` bản khung (P0-07, P0-08, P0-09).
- Commit nhánh `feature/project-setup` và tạo PR / merge vào `main` để kiểm chứng luồng Git (P0-12).
- Chuyển sang Phase 1: Viết script profiling dữ liệu 12 trạm quan trắc (`scripts/run_profiling.py`).
