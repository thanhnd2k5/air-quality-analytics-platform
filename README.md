# Air Quality Analytics Platform

Nền tảng thu thập, lưu trữ, chuyển đổi dữ liệu và phân tích nâng cao (Data Warehouse & Machine Learning) cho dữ liệu chất lượng không khí đa trạm tại Bắc Kinh (PRSA Dataset).

---

## 1. Mục tiêu dự án

- **Ingestion & Data Lake**: Tự động hóa thu thập dữ liệu quan trắc 12 trạm và lưu trữ an toàn trên MinIO S3 Lake.
- **Staging & Data Warehouse**: Xây dựng kiến trúc kho dữ liệu Star Schema (PostgreSQL + dbt) theo chuẩn `station-hour`.
- **Data Mining & Machine Learning**: Phân tích khám phá (EDA), phân cụm đặc trưng trạm (K-Means) và dự báo chỉ số ô nhiễm $PM_{2.5}$ thời điểm $t+1$h.
- **Serving & Dashboard**: Trực quan hóa KPIs chất lượng không khí, bản đồ ô nhiễm và dự báo theo thời gian thực trên Streamlit Dashboard.

---

## 2. Tech Stack

- **Lưu trữ dữ liệu (Storage)**: MinIO (Data Lake - Object Storage), PostgreSQL (Staging & Data Warehouse).
- **Điều phối (Orchestration)**: Apache Airflow (Docker).
- **Chuyển đổi dữ liệu (Transformation)**: dbt-core (dbt-postgres).
- **Xử lý dữ liệu & ML**: Python 3.10+, Pandas, PyArrow/Polars, Scikit-learn, XGBoost/LightGBM.
- **Giao diện trực quan (BI / Dashboard)**: Streamlit, Plotly.
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
├── dashboard/                    # Ứng dụng Web Streamlit
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

Một fact `dwh.fact_air_quality_hourly` (station × giờ). Weather: UCI trước, Open-Meteo khi UCI null, null nếu cả hai thiếu. RH derive từ nhiệt độ và điểm sương đã resolve. `cloud_cover_pct` chỉ từ Open-Meteo. Cờ `data_quality_status` trên fact mô tả dòng đã resolve; cờ UCI gốc nằm ở staging. Mart: `mart.mart_station_daily`, `mart.mart_station_monthly`, `mart.mart_pollution_weather`. `hour_count` là số giờ lịch; `pm25_hour_count` (và các `*_hour_count` khác) là số giờ không null trong trung bình.

Image `dbt-postgres:1.9` vì dbt 1.9 không import được trên Python 3.14. Trong container, host Postgres là `postgres:5432`:

```powershell
docker run --rm --network air-quality-network --env-file .env -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 run --project-dir /dbt/air_quality_dbt --profiles-dir /dbt
docker run --rm --network air-quality-network --env-file .env -e POSTGRES_HOST=postgres -e POSTGRES_PORT=5432 -e DBT_SEND_ANONYMOUS_USAGE_STATS=false -e DO_NOT_TRACK=1 -v "${PWD}/dbt:/dbt" ghcr.io/dbt-labs/dbt-postgres:1.9.0 test --project-dir /dbt/air_quality_dbt --profiles-dir /dbt
py scripts/run_olap_checks.py
```

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
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md): Kế hoạch thực thi qua 14 phase chi tiết kèm Definition of Done.
- [`docs/PROJECT_WBS.xlsx`](docs/PROJECT_WBS.xlsx): Bảng phân rã công việc WBS chi tiết cho 2 thành viên.
- [`docs/PROGRESS.md`](docs/PROGRESS.md): Nhật ký theo dõi tiến độ từng phase.
