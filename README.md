# Air Quality Analytics Platform

Nền tảng thu thập, lưu trữ, chuyển đổi dữ liệu và phân tích nâng cao (Data Warehouse & Machine Learning) cho dữ liệu chất lượng không khí đa trạm tại Bắc Kinh (PRSA Dataset).

Bài tập lớn học phần **INT1422 – Kho dữ liệu và Khai phá dữ liệu** (PTIT).

---

## 0. Chạy lại toàn bộ từ đầu bằng một lệnh

Yêu cầu: **Docker Desktop đang chạy**, **Python 3.10+**, có Internet ở lần chạy đầu (tải zip UCI + gọi Open-Meteo).

```powershell
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python scripts/run_all.py         # ← một lệnh duy nhất (~10 phút lần đầu)
```

`run_all.py` tự làm toàn bộ chuỗi:
1. Tạo `.env` từ `.env.example` (mật khẩu ngẫu nhiên, không commit).
2. Tải 12 CSV UCI.
3. Bật PostgreSQL + MinIO.
4. CSV → lake → Parquet → làm giàu Open-Meteo.
5. Nạp staging.
6. Chạy dbt: lược đồ sao, khối con, data cube.
7. Dựng lại ma trận đặc trưng từ kho.
8. Train và đánh giá **mô hình phân loại cảnh báo**.
9. Chạy 130 dbt test và các bộ đối chiếu mart.
10. Kiểm chứng 5 thao tác OLAP + chạy notebook OLAP.
11. Bật dashboard API.

Mọi bước đều idempotent. Kết quả ghi vào `artifacts/run_all/run_summary.json`, log từng bước ở `artifacts/run_all/logs/`.

| Tuỳ chọn | Tác dụng |
|---|---|
| `--list` | Liệt kê 14 bước |
| `--from STEP` / `--only a,b` / `--skip a,b` | Chạy tiếp hoặc chạy một phần (khi một bước lỗi, script in sẵn lệnh `--from` để chạy tiếp) |
| `--retrain-all` | Fit lại cả phân cụm trạm và hồi quy PM2.5. Mặc định hai phân tích bổ trợ này dùng kết quả đã khoá và chỉ kiểm chứng, vì fit lại cho ra đúng cùng số liệu nhưng ghi đè metadata của lock. |
| `--with-airflow` | Bật thêm Airflow webserver + scheduler |

Giao diện web: `cd dashboard/web && npm install && npm run dev`, rồi mở http://localhost:5180. Các trang mới là **OLAP** (`/olap`) và **Cảnh báo** (`/canh-bao`).

> **Trùng cổng?** Nếu 5433 / 9000 / 9001 / 8100 đã bị chương trình khác chiếm, hãy sửa `POSTGRES_PORT`, `MINIO_PORT` + `MINIO_ENDPOINT`, `MINIO_CONSOLE_PORT`, `DASHBOARD_API_PORT` trong `.env` rồi chạy lại.

### Nguồn dữ liệu và giấy phép

| Bộ dữ liệu | Nguồn | Giấy phép |
|---|---|---|
| Beijing Multi-Site Air Quality (12 trạm, 420 768 bản ghi giờ, 03/2013–02/2017) | [UCI ML Repository #501](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality). Chen, S. (2017), DOI [10.24432/C5RK5G](https://doi.org/10.24432/C5RK5G) | CC BY 4.0 |
| Thời tiết lịch sử theo giờ (lấp chỗ thiếu + mây che phủ) | [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) (tái phân tích ERA5) | CC BY 4.0, API miễn phí cho mục đích phi thương mại |

Dữ liệu thô không được commit (`data/raw/uci/` nằm trong `.gitignore`). `scripts/download_uci_dataset.py` tự tải và kiểm tra kích thước file. Không có dữ liệu cá nhân.

### Đối chiếu yêu cầu bài tập lớn (Bài 12)

| Phần việc | Sản phẩm trong repo |
|---|---|
| 1. Thu thập & tiền xử lý | `docs/DATA_PREPROCESSING.md` (tỷ lệ thiếu + cách xử lý từng cột), `artifacts/data_profile/` |
| 2. Thiết kế kho | `docs/DW_DESIGN.md`: lược đồ sao 4 chiều, phân cấp khái niệm, lý do chọn độ mịn, `artifacts/dwh/figures/star_schema.png` |
| 3. Cài đặt & tính khối | `dbt/air_quality_dbt/models/`, khối tính trước `mart_station_daily`, `mart_station_monthly`, `mart_olap_cube` (GROUP BY CUBE, 32 khối con), kiểm chứng `artifacts/dwh/olap_checks.json` (100% ô đúng) |
| 4. Dịch vụ OLAP | `sql/olap/olap_operations.sql`, `notebooks/olap/olap_demo.ipynb`, dashboard `/olap` |
| 5. Khai phá (phân loại) | `src/classification/`, `scripts/run_classification.py`, `artifacts/classification/` (ma trận nhầm lẫn, so với baseline, McNemar), dashboard `/canh-bao` |
| Báo cáo, slide, phân công, khai báo AI | `bao_cao/` |

---

## 1. Mục tiêu dự án

- **Ingestion & Data Lake**: Tự động hóa thu thập dữ liệu quan trắc 12 trạm và lưu trữ an toàn trên MinIO S3 Lake.
- **Staging & Data Warehouse**: Xây dựng kiến trúc kho dữ liệu Star Schema (PostgreSQL + dbt) theo chuẩn `station-hour`, 4 chiều (Thời gian, Giờ, Địa điểm, Hướng gió).
- **Data Mining (bài toán chính)**: **Phân loại cảnh báo vượt ngưỡng** PM2.5(t+1h) ≥ 115 µg/m³ bằng cây quyết định và HistGradientBoosting, so sánh với baseline persistence.
- **Phân tích bổ trợ**: EDA, phân cụm đặc trưng trạm (K-Means), hồi quy PM2.5 t+1h.
- **Serving & Dashboard**: Trực quan hóa KPI, OLAP tương tác, cảnh báo, bản đồ 12 trạm và dự báo PM2.5 qua web app (FastAPI + React).

---

## 2. Tech Stack

- **Lưu trữ dữ liệu (Storage)**: MinIO (Data Lake - Object Storage), PostgreSQL (Staging & Data Warehouse).
- **Điều phối (Orchestration)**: Apache Airflow (Docker).
- **Chuyển đổi dữ liệu (Transformation)**: dbt-core (dbt-postgres).
- **Xử lý dữ liệu & ML**: Python 3.10+, Pandas, PyArrow/Polars, Scikit-learn, XGBoost/LightGBM.
- **Giao diện trực quan (BI / Dashboard)**: FastAPI, React (Vite), Mantine, ECharts, Leaflet.
- **Kiểm thử & Chất lượng (Quality & Testing)**: pytest, Great Expectations / dbt tests.
- **Hạ tầng (Infrastructure)**: Docker & Docker Compose.

---

## 3. Cấu trúc Repository

```text
air-quality-analytics-platform/
│
├── airflow/                      # DAGs và plugins điều phối Airflow
│   ├── dags/
│   └── plugins/
│
├── artifacts/                    # Kết quả profiling, báo cáo phân tích, đồ thị
│   └── data_profile/
│
├── dashboard/                    # Web dashboard (api FastAPI + web React)
│
├── data/                         # Dữ liệu cục bộ phục vụ dev (được .gitignore)
│   └── raw/
│       └── uci/                  # 12 file CSV dữ liệu thô
│
├── dbt/                          # Dự án dbt chuyển đổi DWH
│   └── air_quality_dbt/
│       ├── models/
│       │   ├── staging/
│       │   ├── intermediate/
│       │   ├── warehouse/
│       │   └── marts/
│       ├── tests/
│       └── dbt_project.yml
│
├── docs/                         # Tài liệu kiến trúc và hướng dẫn triển khai
│   ├── ARCHITECTURE.md
│   ├── DATA_GUIDE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── PROJECT_CONTEXT.md
│   ├── PROJECT_WBS.xlsx
│   └── PROGRESS.md
│
├── ml/                           # Pipeline học máy & phân cụm
│   ├── notebooks/
│   ├── features/
│   ├── training/
│   └── models/
│
├── scripts/                      # CLI automation scripts (e.g. run_profiling.py)
│
├── src/                          # Core reusable Python package
│   ├── ingestion/
│   ├── processing/
│   ├── validation/
│   └── utils/
│
├── tests/                        # Automated unit & integration tests
│   ├── unit/
│   └── integration/
│
├── .env.example                  # Template biến môi trường mẫu
├── .gitignore                    # Bộ lọc file Git
├── docker-compose.yml            # Hạ tầng container (Postgres, MinIO, Airflow)
├── requirements.txt              # Danh sách thư viện Python
└── README.md
```

---

## 5. Yêu cầu môi trường (Phase 2)

Đã kiểm tra trên máy phát triển (2026-09-25 / integration 2026-09-29):

| Thành phần | Phiên bản |
|---|---|
| Docker Engine | 29.3.1 |
| Docker Compose | v5.1.1 |

Khuyến nghị: Docker Desktop (Windows) với WSL2 backend.

### Hạ tầng Compose hiện tại

```text
postgres            → localhost:5433   (DB air_quality_dw + airflow_db; container :5432)
minio               → API :9000 / Console :9001   (bucket air-quality-lake)
airflow-webserver   → UI :8080
airflow-scheduler   → LocalExecutor (no Redis)
```

Network Docker: `air-quality-network` (DNS nội bộ: `postgres`, `minio` — **không** dùng `localhost` giữa container).

### Start / stop / reset

**Lần đầu (máy mới):**

```powershell
copy .env.example .env
# Sửa mật khẩu trong .env (POSTGRES_*, MINIO_*, _AIRFLOW_WWW_USER_*)
# Giữ POSTGRES_USER khớp volume nếu đã init trước đó (mặc định: postgres)

docker compose up airflow-init
docker compose up -d
docker compose ps
bash scripts/infra/init_minio.sh   # bucket + prefix markers (Git Bash / WSL)
```

**Start lại (đã có volume):**

```powershell
docker compose up -d
docker compose ps
```

**Stop (giữ data):**

```powershell
docker compose stop
# hoặc:
docker compose down          # xóa container, GIỮ volume
```

**Restart nhanh:**

```powershell
docker compose restart
```

**Reset an toàn (XÓA toàn bộ DB / MinIO local — thận trọng):**

```powershell
docker compose down -v
docker compose up airflow-init
docker compose up -d
bash scripts/infra/init_minio.sh
```

`down -v` xóa named volumes (`postgres_data`, `minio_data`). Chỉ dùng khi cố ý dựng lại từ đầu.

### Truy cập UI

| UI | URL | Đăng nhập |
|---|---|---|
| Airflow | http://localhost:8080 | `_AIRFLOW_WWW_USER_USERNAME` / `_AIRFLOW_WWW_USER_PASSWORD` trong `.env` |
| MinIO Console | http://localhost:9001 | `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` |

- Sample DAG: `sample_hello` (unpause + Trigger trong Airflow UI)
- Phase 3 DAG: `uci_ingest_raw` (default station `Wanshouxigong`; conf `{"station":"..."}` hoặc `{"stations":[...]}`)
- Phase 4 DAG: `uci_process_raw` (default station `Wanshouxigong`; conf `{"station":"..."}` / `{"stations":[...]}` / `{"process_date":"YYYY-MM-DD"}`)
- Phase 5 DAG: `openmeteo_ingest_raw` (API → MinIO raw → processed `om_*`; conf `station`/`stations`, `start`/`end`, `process_date`)
- Phase 6 DAG: `staging_load` (processed Parquet + `stations.csv` → PostgreSQL `staging`; default `Wanshouxigong`; conf `station`/`stations`, `skip_reference`)
- Chi tiết Airflow: `config/airflow/README.md`
- Layout Data Lake: `config/minio/bucket_layout.md`

### Phase 3 – UCI → MinIO Raw (host CLI)

Yêu cầu MinIO healthy + bucket đã bootstrap. Host CLI dùng `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (khớp server). Trong `.env`, giữ `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` giống ROOT.

```powershell
# 1 station
py scripts/ingest_uci_station.py --station Wanshouxigong

# all 12
py scripts/ingest_uci_station.py --all

# verify one object (byte-identical)
py scripts/verify_uci_ingest.py

# list raw objects
py scripts/list_uci_raw_objects.py
```

### Phase 4 – Raw → Processed Parquet (host CLI)

Yêu cầu raw UCI đã có trên MinIO (Phase 3). Output: `processed/uci/air_quality/...` (+ quarantine nếu có). Không impute; giữ NULL + DQ flags.

```powershell
# 1 station
py scripts/process_uci_station.py --station Wanshouxigong --process-date 2026-10-07

# all 12
py scripts/process_uci_station.py --all --process-date 2026-10-07

# verify processed (schema, row count, raw untouched)
py scripts/verify_uci_processed.py --station Wanshouxigong --process-date 2026-10-07

# list processed objects
py scripts/list_uci_processed_objects.py
```

Object key: `raw/uci/air_quality/station=<Station>/ingestion_date=YYYY-MM-DD/<original_filename>` (+ `.meta.json`).

### Phase 5 – Open-Meteo Investigation & Integration

Gate B = **B** (enrichment `cloud_cover` + fill UCI weather missing). RH derive từ TEMP+DEWP — không ưu tiên RH từ API.

```powershell
# POC (1 station × 1 month) + compare
py -3 scripts/poc_openmeteo_fetch.py --station Wanshouxigong --start 2015-01-01 --end 2015-01-31
py -3 scripts/poc_openmeteo_compare.py --station Wanshouxigong --om-json artifacts/openmeteo/poc/wanshouxigong_2015-01-01_2015-01-31.json --process-date 2026-10-07

# Full range ingest + process
py -3 scripts/ingest_openmeteo_station.py --station Wanshouxigong --ingestion-date 2026-10-07
py -3 scripts/process_openmeteo_station.py --station Wanshouxigong --process-date 2026-10-07
py -3 scripts/ingest_openmeteo_station.py --all --ingestion-date 2026-10-07
py -3 scripts/process_openmeteo_station.py --all --process-date 2026-10-07

# Fill-rate check (UCI missing filled by OM)
py -3 scripts/openmeteo_fill_rate.py --station Wanshouxigong
```

Keys: `raw/openmeteo/historical_weather/...`, `processed/weather/openmeteo/...` (xem `config/minio/bucket_layout.md`).

### Phase 6 – PostgreSQL staging

Host CLI dùng `POSTGRES_HOST` / `POSTGRES_PORT` trong `.env` (thường `localhost:5433`). Airflow trong Compose ghi đè thành `postgres:5432`. Loader tự apply `config/postgres/ddl/staging.sql` (init SQL không chạy lại trên volume cũ).

Bảng: `staging.air_quality_hourly`, `staging.weather_openmeteo_hourly`, `staging.station_reference`, cộng `staging.load_registry`. Không join `weather_final` / không derive RH ở phase này.

Idempotency: skip khi registry khớp object key mới nhất + `source_sha256` + `schema_version` + `row_count`, và bảng vẫn còn đủ dòng. Partition `process_date` mới thì load lại. Quarantine MinIO không được load.

```powershell
py scripts/load_staging.py --station Wanshouxigong
py scripts/load_staging.py --all
py scripts/verify_staging_load.py --all
```

Ở Phase 6, dbt chỉ khai báo source. Model warehouse nằm ở Phase 7.

### Phase 7 – Data warehouse (dbt)

Một fact `dwh.fact_air_quality_hourly` (station × giờ). Weather: UCI trước, Open-Meteo khi UCI null, null nếu cả hai thiếu. RH derive từ nhiệt độ và điểm sương đã resolve. `cloud_cover_pct` chỉ từ Open-Meteo. Cờ `data_quality_status` trên fact mô tả dòng đã resolve; cờ UCI gốc nằm ở staging. Mart: `mart.mart_station_daily`, `mart.mart_station_monthly`, `mart.mart_pollution_weather`, cộng Phase 8 `mart.mart_pm25_episodes` / `mart.mart_pm25_multi_station_events` (ngưỡng 115 µg/m³, min 3h, đa-trạm K=6 — xem `artifacts/eda/episode_definition.md`). `hour_count` là số giờ lịch; `pm25_hour_count` (và các `*_hour_count` khác) là số giờ không null trong trung bình.

Image `dbt-postgres:1.9` vì dbt 1.9 không import được trên Python 3.14. Trong container, host Postgres là `postgres:5432`:

```powershell
docker run --rm --network air-quality-network --env-file .env -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 run --project-dir /dbt/air_quality_dbt --profiles-dir /dbt
docker run --rm --network air-quality-network --env-file .env -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 test --project-dir /dbt/air_quality_dbt --profiles-dir /dbt
py scripts/run_olap_checks.py
```

### Phase 11 – Web Dashboard

Stack: FastAPI + React (Vite) + Mantine + ECharts + Leaflet. Chi tiết: [`dashboard/README.md`](dashboard/README.md).

```powershell
# API trong Compose (cần Postgres/marts đã có)
docker compose up -d postgres dashboard-api
# API: http://127.0.0.1:8100/docs  (không dùng :8000 — dễ đụng project khác)

# UI local
cd dashboard/web
npm install
npm run dev
# → ưu tiên http://localhost:5180/ (tránh đụng Vite app khác ở 5173/5174)
# Dev gọi thẳng API qua dashboard/web/.env.development
```

### Phase 12 – Integration (hybrid)

Không `down -v`. Giữ volume; smoke idempotent + 1 slice fresh (Wanshouxigong); mining verify (không retrain). Runbook đầy đủ:

[`artifacts/integration/runbook_hybrid.md`](artifacts/integration/runbook_hybrid.md)

Evidence: `artifacts/integration/` (`pipeline_p12c_summary.json`, `mining_dashboard_p12d_summary.json`, …).

**Lưu ý host CLI MinIO:** `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` phải khớp `MINIO_ROOT_*` (sai → `SignatureDoesNotMatch`). Sau `dbt run`, nếu mart cluster/predictions lệch lock: `dbt seed --full-refresh` + reload `staging.pm25_predictions_raw` từ `predictions_locked.parquet` (xem runbook §4).

**Dashboard UI:** nếu `Failed to fetch` dù `/api/health` OK → CORS; `docker compose up -d dashboard-api --force-recreate` (regex compose dùng `[0-9]`/`[.]`, không `\\d`).

### Recreate checklist (2 thành viên)

Trên mỗi máy, chỉ cần repo + `.env` (không commit `.env`):

1. Clone / pull nhánh hiện tại
2. `copy .env.example .env` và điền secret
3. Chạy khối **Lần đầu** ở trên
4. `docker compose ps` → postgres, minio, airflow-webserver, airflow-scheduler đều **healthy**
5. Mở Airflow UI và MinIO Console được

Không cấu hình secret bằng tay ngoài file `.env`.

Nếu một thành viên không available: thành viên còn lại chạy thêm **một lần recreate** (`docker compose down` → `up airflow-init` → `up -d`) và lưu evidence — đủ cho P2-28 proxy (đã áp dụng 2026-09-29).
---

## 6. Tài liệu tham chiếu

Chi tiết kiến trúc và kế hoạch thực hiện được lưu trữ trong thư mục [`docs/`](docs/):
- [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md): Bối cảnh dự án, phạm vi và mục tiêu kinh doanh.
- [`docs/DATA_GUIDE.md`](docs/DATA_GUIDE.md): Mô tả dữ liệu PRSA 12 trạm, ý nghĩa các biến và quy tắc chất lượng dữ liệu.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Kiến trúc kỹ thuật chi tiết từ Ingestion, MinIO, PostgreSQL DWH đến ML/Dashboard.
- [`docs/DW_DESIGN.md`](docs/DW_DESIGN.md): Thiết kế kho (lược đồ sao, độ mịn, phân cấp, khối con tính trước) và năm thao tác OLAP.
- [`docs/DATA_PREPROCESSING.md`](docs/DATA_PREPROCESSING.md): Nguồn, giấy phép, tỷ lệ thiếu và cách xử lý từng cột.
- [`artifacts/classification/classification_report.md`](artifacts/classification/classification_report.md): Kết quả bài toán phân loại cảnh báo.
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md): Kế hoạch thực thi qua 14 phase chi tiết kèm Definition of Done.
- [`docs/PROJECT_WBS.xlsx`](docs/PROJECT_WBS.xlsx): Bảng phân rã công việc WBS chi tiết cho 2 thành viên.
- [`docs/PROGRESS.md`](docs/PROGRESS.md): Nhật ký theo dõi tiến độ từng phase.
