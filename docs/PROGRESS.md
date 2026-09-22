# Project Progress Log

Tài liệu ghi nhận tiến độ thực hiện theo từng phase của dự án.

---

## 2026-09-15

### Current phase
Phase 0 – Project Foundation (đang làm)

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
