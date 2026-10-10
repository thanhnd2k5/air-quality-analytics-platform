# IMPLEMENTATION_PLAN.md

> **Project:** Phân tích và dự báo ô nhiễm không khí theo khu vực và điều kiện thời tiết  
> **Quy mô nhóm:** 2 thành viên  
> **Vai trò tài liệu:** Kế hoạch triển khai dự án theo phase và milestone  
> **Phiên bản:** 1.2  
> **Cập nhật:** 06/10/2026
>
> Tài liệu này cần được đọc cùng:
>
> - `PROJECT_CONTEXT.md`
> - `DATA_GUIDE.md`
> - `ARCHITECTURE.md`
>
> Mục tiêu của tài liệu là trả lời:
>
> **Làm cái gì trước, cái gì sau, khi nào được chuyển phase, hai thành viên chia việc thế nào và đầu ra của mỗi phase là gì.**

---

# 1. Nguyên tắc triển khai

Dự án không được triển khai theo kiểu:

```text
Dựng hết Docker
↓
Làm hết Airflow
↓
Làm hết DWH
↓
Cuối cùng mới kiểm tra dữ liệu
```

Hướng thực hiện ưu tiên:

```text
Understand
↓
Build small
↓
Validate
↓
Run end-to-end
↓
Expand
```

Đặc biệt:

> **Phải làm một vertical slice với 1 trạm chạy xuyên suốt pipeline trước khi mở rộng toàn bộ 12 trạm.**

Điều này giúp phát hiện sớm lỗi:

- schema;
- timestamp;
- MinIO;
- PostgreSQL;
- dbt;
- Airflow;
- dashboard.

---

# 2. Tổng quan các phase

```text
Phase 0
Project Foundation
        ↓
Phase 1
Full Data Profiling
        ↓
Phase 2
Environment & Infrastructure
        ↓
Phase 3
UCI Ingestion → Data Lake
        ↓
Phase 4
Data Processing & Quality
        ↓
Phase 5
Open-Meteo Investigation & Integration
(5a Gate B → 5b pipeline)
        ↓
Phase 6
PostgreSQL Staging
        ↓
Phase 7
Data Warehouse + dbt
        ↓
Phase 8
Analytical Exploration
        ↓
Phase 9
Clustering
        ↓
Phase 10
PM2.5 Forecasting
        ↓
Phase 11
Web Dashboard
        ↓
Phase 12
Integration & Hardening
        ↓
Phase 13
Report / Demo Preparation
```

Không nhất thiết mọi phase phải hoàn toàn tuần tự.

Một số phần có thể làm song song khi dependency cho phép.

---

# 3. Phase 0 – Project Foundation

## Mục tiêu

Chuẩn bị repository và cách làm việc thống nhất trước khi code lớn.

## Công việc

Tạo repository:

```text
air-quality-project/
```

Tạo các thành phần cơ bản:

```text
docs/
src/
airflow/
dbt/
ml/
dashboard/
tests/
```

Chuẩn bị:

```text
.gitignore
.env.example
README.md
docker-compose.yml
```

README ban đầu chỉ cần:

- mục tiêu dự án;
- tech stack;
- cách tổ chức repo;
- link tới tài liệu context.

## Documentation

Đặt vào:

```text
docs/
├── PROJECT_CONTEXT.md
├── DATA_GUIDE.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
└── PROGRESS.md
```

## Definition of Done

Phase 0 hoàn thành khi:

```text
[ ] Repository hoạt động
[ ] Hai thành viên clone được repo
[ ] Folder structure tồn tại
[ ] .env.example tồn tại
[ ] Documentation nền được lưu
[ ] Git workflow thống nhất
```

---

# 4. Git workflow

Với nhóm 2 người, không cần workflow quá phức tạp.

Branch chính:

```text
main
```

Mỗi task đáng kể dùng branch:

```text
feature/data-profiling
feature/minio-ingestion
feature/dwh
feature/ml
feature/dashboard
```

Flow:

```text
create branch
↓
develop
↓
test
↓
commit
↓
merge main
```

Không cần GitFlow đầy đủ.

Không commit:

```text
.env
password
large raw datasets
model artifact quá lớn
Docker volume
__pycache__
```

---

# 5. Phase 1 – Full Dataset Profiling

## Mục tiêu

Hiểu **toàn bộ 12 trạm**, không chỉ Wanshouxigong.

Đây là phase bắt buộc trước khi thiết kế DWH cuối cùng.

## Input

12 file UCI PRSA.

## Công việc

Tạo profiling script có thể chạy tự động cho mọi file.

Mỗi station cần thu thập:

```text
station_name
row_count
column_count
start_time
end_time

duplicate_timestamp_count
missing_timestamp_count

missing count per variable
missing percentage
longest missing run

min
max
mean
median

negative value count
```

Ngoài từng station, cần kiểm tra toàn dataset:

- station list;
- schema consistency;
- date range consistency;
- row count consistency;
- timestamp overlap;
- missing pattern giữa các station.

## Output

```text
artifacts/data_profile/
├── station_profile.csv
├── missing_summary.csv
├── extreme_value_summary.csv
└── profiling_report.md
```

Có thể thêm chart phục vụ EDA.

## Quyết định cần đưa ra sau phase

- grain có đúng `station-hour` không;
- toàn bộ file có đủ timeline hay không;
- missing strategy sơ bộ;
- extreme-value investigation strategy;
- có bất thường station nào cần xử lý riêng hay không.

## Definition of Done

```text
[ ] Đã profile đủ 12 file
[ ] Schema consistency được kiểm tra
[ ] Timestamp continuity được kiểm tra
[ ] Missing được thống kê
[ ] Longest gaps được thống kê
[ ] Extreme values được thống kê
[ ] Kết quả được ghi vào DATA_GUIDE/PROGRESS
```

---

# 6. Phân chia Phase 1

### Thành viên A

- xây profiling script;
- kiểm tra timestamp;
- missing;
- duplicates;
- schema.

### Thành viên B

- phân tích distribution;
- extreme values;
- so sánh station;
- tổng hợp profiling report.

Sau đó hai người cùng review kết quả.

Không chia:

```text
A làm code
B chỉ viết báo cáo
```

Thành viên B vẫn phải chạy và hiểu profiling pipeline.

---

# 7. Phase 2 – Environment & Infrastructure

## Mục tiêu

Dựng môi trường Docker đủ để pipeline bắt đầu chạy.

## Thành phần

Ưu tiên dựng trước:

```text
PostgreSQL
MinIO
Airflow
```

dbt và dashboard (FastAPI/React) có thể cấu hình sau.

## Docker Compose

Các service tối thiểu:

```text
postgres
minio
airflow-webserver
airflow-scheduler
```

Các service Airflow phụ thuộc vào cách cấu hình chính thức được lựa chọn.

## Kiểm tra

### PostgreSQL

```text
connect thành công
create database
create schema
query thử
```

### MinIO

```text
console truy cập được
bucket tạo được
upload/download object được
```

### Airflow

```text
UI truy cập được
scheduler hoạt động
sample DAG chạy được
```

## Definition of Done

```text
[x] docker compose up hoạt động
[x] PostgreSQL healthy
[x] MinIO healthy
[x] Airflow healthy
[x] Hai thành viên dựng được environment từ repo
    (P2-28: thành viên A làm hộ B — recreate lần 2 từ repo + .env, 2026-09-29)
[x] Không cần cấu hình bí mật bằng tay ngoài .env
```

---

# 8. Phase 3 – UCI Ingestion → Data Lake

## Mục tiêu

Đưa raw UCI data vào MinIO thông qua pipeline có kiểm soát.

Không copy tay file vào bucket rồi coi là ingestion pipeline.

## Development strategy

Trước tiên:

```text
Wanshouxigong
```

Sau khi ổn:

```text
12 stations
```

Branch:

```text
feature/minio-ingestion
```

## Flow

```text
Local/source UCI
      ↓
Validation (light)
      ↓
Airflow ingestion task
      ↓
MinIO Raw (+ sidecar .meta.json)
```

## Quyết định kỹ thuật (chốt 2026-10-06)

| Mục | Quyết định |
|---|---|
| Object key | `raw/uci/air_quality/station=<Station>/ingestion_date=YYYY-MM-DD/<original_filename>` |
| Immutability | Không overwrite object cùng key |
| Idempotency | Cùng SHA-256 → skip upload, task success; khác checksum cùng ngày → fail rõ |
| Checksum | SHA-256 bắt buộc |
| Metadata | Sidecar `.meta.json` cạnh object + MinIO user-metadata tối thiểu (`station`, `source_file`, `sha256`, `ingestion_ts`) |
| Validate lúc ingest | Nhẹ: file tồn tại, khớp `file_inventory.csv`, đúng 18 cột, station khớp tên file; không impute/rename |
| Source trong container | Mount read-only `./data/raw/uci` → `/opt/airflow/data/raw/uci` |

Chi tiết path: `config/minio/bucket_layout.md`.

## Milestones

```text
K3-01  Spec & layout
K3-02  Library (MinIO client + validate + upload + CLI)
K3-03  Slice 1 trạm Wanshouxigong qua Airflow
K3-04  Scale 12 trạm + idempotent rerun
K3-05  Docs, evidence, đóng DoD
```

## WBS (P3-01 → P3-20)

### K3-01 Spec

- **P3-01** Xác nhận Phase 2 gate đã đóng; tạo branch `feature/minio-ingestion`
- **P3-02** Chốt object key + metadata schema (bucket_layout + IMPLEMENTATION_PLAN)
- **P3-03** Mount `data/raw/uci` (ro) vào Airflow services; cập nhật `config/airflow/README.md`

### K3-02 Library

- **P3-04** `src/utils/minio_client.py` — connect từ env `MINIO_*`, put/get/stat/list
- **P3-05** `src/validation/uci_raw.py` — inventory lookup, schema 18 cols, station match
- **P3-06** `src/ingestion/uci_to_minio.py` — sha256, build key, upload + sidecar, skip-if-same-checksum
- **P3-07** `scripts/ingest_uci_station.py` — CLI 1 station (smoke ngoài Airflow)
- **P3-08** Tests nhỏ trong `tests/` (validate + key builder)

### K3-03 One-station slice

- **P3-09** DAG `uci_ingest_raw` — param `station` (default `Wanshouxigong`); tasks `validate_source` → `upload_raw`
- **P3-10** Trigger manual 1 lần → object + `.meta.json` đúng path
- **P3-11** Verify download = source byte-identical (checksum); raw không transform
- **P3-12** Rerun cùng station → skip/idempotent success, không duplicate sai

### K3-04 Scale 12

- **P3-13** Mở rộng DAG/CLI nhận list 12 stations từ inventory
- **P3-14** Ingest đủ 12; list prefix đủ 12 station folders
- **P3-15** Rerun full 12 → skip/success không ghi đè
- **P3-16** Manifest run → `artifacts/ingestion/` (station, key, sha256, status)

### K3-05 Close

- **P3-17** Cập nhật README / bucket_layout (cách chạy DAG, path, metadata)
- **P3-18** Evidence: list objects + mẫu meta + DAG run logs text
- **P3-19** Tick DoD Phase 3; entry PROGRESS đóng phase
- **P3-20** PR merge `feature/minio-ingestion` → `main`

## Phân chia Phase 3

### Thành viên A (primary – pipeline)

- P3-03 compose mount
- P3-04 / P3-06 MinIO client + upload
- P3-09 DAG
- P3-13 scale orchestration
- Lead merge PR

### Thành viên B (primary – validation / verify / docs)

- P3-02 metadata/layout spec
- P3-05 validation (inventory/schema)
- P3-07 CLI smoke + P3-08 tests
- P3-11 / P3-14 / P3-15 verify + manifest artifacts
- P3-17 docs

### Shared

- P3-01 kickoff
- P3-10 lần chạy đầu
- P3-12 idempotent check
- P3-18 → P3-20 đóng gate

Không chia kiểu “A code, B chỉ viết docs”. Thành viên B phải trigger được DAG và giải thích được object key.

## Definition of Done

```text
[x] 1 station (Wanshouxigong) ingest thành công qua Airflow
[x] rerun không gây lỗi / không overwrite sai
[x] raw source không bị transform (byte/checksum)
[x] mở rộng đủ 12 stations
[x] Airflow hiển thị task status rõ
[x] raw objects truy vết được tới source (meta + sha256)
```

---

# 9. Phase 4 – Processing & Data Quality

## Mục tiêu

Chuyển Raw thành dữ liệu chuẩn hóa có thể đưa vào relational staging.

Không impute mặc định; không đụng Open-Meteo / Postgres staging (Phase 5–6).

## Development strategy

Trước tiên:

```text
Wanshouxigong
```

Sau khi ổn:

```text
12 stations
```

Branch:

```text
feature/data-processing
```

## Flow

```text
MinIO Raw (UCI CSV + .meta.json)
      ↓
Resolve latest raw object
      ↓
Python / Pandas (canonical + DQ flags)
      ↓
Parquet (+ sidecar .meta.json)
      ↓
MinIO Processed (+ quarantine nếu cần)
```

## Xử lý chính

- parse timestamp → `event_time_local`;
- canonical column names (DATA_GUIDE §5);
- datatype conversion;
- station normalization (`station_name`);
- unit validation (tên cột + range);
- duplicate check trên `station_name + event_time_local`;
- missing flags (không impute);
- `SUSPECT_CAP` cho extreme kiểu 999 / 10000;
- format conversion → Parquet.

Output ưu tiên:

```text
Parquet
```

## Quyết định kỹ thuật (chốt 2026-10-07)

| Mục | Quyết định |
|---|---|
| Object key (processed) | `processed/uci/air_quality/station=<Station>/process_date=YYYY-MM-DD/<station>_hourly.parquet` |
| Quarantine key | `processed/quarantine/uci/air_quality/station=<Station>/process_date=YYYY-MM-DD/...` |
| Immutability | Không overwrite object cùng key |
| Idempotency | Cùng `source_sha256` + `schema_version` tại key → skip; khác source/schema cùng key → fail rõ |
| Checksum | SHA-256 của bytes Parquet (ghi trong sidecar); `process_ts` deterministic = `process_dateT00:00:00Z` |
| Metadata | Sidecar `.meta.json` cạnh Parquet (`run_ts` = wall-clock audit) |
| Timestamp | `event_time_local` từ year/month/day/hour; giả định wall time `Asia/Shanghai` (DATA_GUIDE §8) |
| Missing | Giữ `NULL`; chỉ flag (`has_missing_pollutant`, `has_missing_weather`, …) |
| Imputation | **Không** impute pollutant/weather trong Phase 4 |
| Extremes | Giữ giá trị; đánh `suspect_cap` / `SUSPECT_CAP`; không xóa / winsorize |
| Negatives (pollutant/RAIN/WSPM) | Quarantine row (hoặc fail nếu schema-critical); không sửa thầm |
| Duplicates | Fail + evidence nếu trùng natural key; không `drop_duplicates` im lặng |
| Raw | Chỉ đọc từ MinIO; không mutate local `data/raw` hay raw objects |

Canonical rename: DATA_GUIDE §5. Chi tiết path: `config/minio/bucket_layout.md`.

## Missing

Không mặc định phải impute toàn bộ.

Có thể có:

```text
historical_clean
```

vẫn chứa `NULL`.

ML imputation / short-gap interpolate deferred downstream (Phase 5/10).

## Milestones

```text
K4-01  Spec & layout
K4-02  Library (schema + transform + DQ + write + CLI + tests)
K4-03  Slice 1 trạm Wanshouxigong qua CLI/Airflow
K4-04  Scale 12 trạm + idempotent rerun
K4-05  Docs, evidence, đóng DoD
```

## WBS (P4-01 → P4-20)

### K4-01 Spec

- **P4-01** Xác nhận Phase 3 gate đã đóng (PR #4 merged); dùng branch `feature/data-processing`
- **P4-02** Chốt object key processed/quarantine + metadata schema (bucket_layout + IMPLEMENTATION_PLAN)
- **P4-03** Chốt canonical map + DQ flag set + no-impute policy; entry PROGRESS kickoff

### K4-02 Library

- **P4-04** `src/processing/schema.py` — UCI→canonical rename, dtypes, lineage columns
- **P4-05** `src/processing/transform.py` — CSV bytes → DataFrame; `event_time_local`; cast types
- **P4-06** `src/processing/dq.py` — duplicate key; non-neg ranges; missing flags; `SUSPECT_CAP`; quarantine split
- **P4-07** `src/processing/uci_to_processed.py` — resolve raw → transform/DQ → Parquet + sidecar → MinIO; skip-if-same-checksum
- **P4-08** `scripts/process_uci_station.py` — CLI `--station` / `--all`
- **P4-09** Tests trong `tests/unit/test_uci_process.py` (schema + timestamp + DQ + key builder)

### K4-03 One-station slice

- **P4-10** DAG `uci_process_raw` — param `station` (default `Wanshouxigong`); tasks `resolve_raw` → `transform_and_dq` → `write_processed`
- **P4-11** Trigger manual 1 lần → Parquet + `.meta.json` đúng path
- **P4-12** Verify canonical columns; row count ≈ raw; raw không đổi; flags/quarantine hợp lý
- **P4-13** Rerun cùng station → skip/idempotent success, không overwrite sai

### K4-04 Scale 12

- **P4-14** Mở rộng DAG/CLI nhận list 12 stations từ inventory / conf
- **P4-15** Process đủ 12; list prefix đủ 12 station folders
- **P4-16** Rerun full 12 → skip/success không ghi đè
- **P4-17** Manifest run → `artifacts/processing/` (station, raw_key, processed_key, sha256, status, quarantine_rows)

### K4-05 Close

- **P4-18** Cập nhật README / bucket_layout / Airflow README (cách chạy DAG, path, flags)
- **P4-19** Evidence: list objects + mẫu meta + DAG run logs; tick DoD; PROGRESS đóng phase
- **P4-20** PR merge `feature/data-processing` → `main`

## Phân chia Phase 4

### Thành viên A (primary – pipeline)

- P4-04 / P4-07 schema write path + orchestrator
- P4-10 DAG
- P4-14 scale orchestration
- Lead merge PR

### Thành viên B (primary – DQ / verify / docs)

- P4-02 / P4-03 key + policy spec
- P4-05 / P4-06 transform + dq
- P4-08 CLI + P4-09 tests
- P4-12 / P4-15 / P4-16 verify + manifest artifacts
- P4-18 docs

### Shared

- P4-01 kickoff
- P4-11 lần chạy đầu
- P4-13 idempotent check
- P4-19 → P4-20 đóng gate

Không chia kiểu “A code, B chỉ viết docs”. Thành viên B phải trigger được DAG và giải thích được processed key.

## Definition of Done

```text
[x] Canonical schema hoạt động
[x] Timestamp chuẩn hóa (event_time_local)
[x] Units thống nhất (tên cột + range check)
[x] Duplicate policy hoạt động (fail nếu trùng key)
[x] Invalid records được phát hiện (quarantine / flags)
[x] Processed output reproducible + idempotent
[x] Không phá raw data
[x] 12 stations processed trên MinIO
```

---

# 10. Phase 5 – Open-Meteo Investigation & Integration

## Mục tiêu

Xác định Open-Meteo **thực sự có giá trị gì** trước khi ingest toàn bộ.

Chia thành **Phase 5a Investigation (Gate B)** rồi **Phase 5b Integration** (chỉ khi Gate B ≠ C).

Không mặc định scale 12 trạm × full range trước khi có số liệu so sánh.

Working preference biến (chi tiết `DATA_GUIDE.md` §24 / `PROJECT_CONTEXT.md` §15):

```text
RH            → derive từ TEMP + DEWP (sau resolve); không ưu tiên RH từ API
Open-Meteo    → cloud_cover (+ tối đa 1 biến phụ sau EDA)
biến trùng    → UCI primary; Open-Meteo fill khi UCI missing
pollutant NA  → không fill bằng Open-Meteo
```

POC station mặc định: **Wanshouxigong** (đã có raw + processed Phase 3/4).

---

## Phase 5a – Investigation (Gate B)

### Step 1 – Station metadata

Xác minh:

```text
station
latitude
longitude
```

cho ít nhất một station (seed: `data/raw/reference/stations.csv`).

### Step 2 – API proof-of-concept

Thử:

```text
1 station
+
1 month
```

với:

```text
timezone=Asia/Shanghai
```

và unit phù hợp (temp °C, rain mm, wind **m/s**).

Hourly variables POC:

```text
temperature_2m
dew_point_2m
rain
wind_speed_10m
wind_direction_10m
surface_pressure
cloud_cover
```

### Step 3 – Compare

So sánh:

```text
UCI TEMP ↔ Open-Meteo temperature_2m
UCI DEWP ↔ Open-Meteo dew_point_2m
UCI RAIN ↔ Open-Meteo rain
UCI WSPM ↔ Open-Meteo wind_speed_10m
```

Đồng thời đo: % missing UCI weather có thể fill bằng Open-Meteo; sanity `cloud_cover` 0–100.

Không kỳ vọng bằng nhau tuyệt đối (gridded ≠ station weather).

Mục tiêu:

- kiểm tra alignment;
- timezone;
- độ hợp lý;
- giá trị enrichment + fill.

### Step 4 – Decision Gate B

Một trong ba quyết định:

```text
A. Giữ Open-Meteo đầy đủ
B. Enrichment (cloud_cover) + fill weather UCI missing   ← kỳ vọng mặc định
C. Thay đổi vai trò/nguồn nếu không phù hợp
```

Quyết định phải cập nhật `PROJECT_CONTEXT.md` + `PROGRESS.md`.

### Definition of Done – Phase 5a

```text
[x] Station coordinate được xác minh
[x] API request đúng timezone + units
[x] Hourly join 1 tháng kiểm tra thành công
[x] So sánh với UCI weather + % fill potential
[x] Gate B recorded; docs synced (cloud_cover, không RH API làm candidate chính)
```

### Không làm ở 5a

Airflow DAG production, ingest 12 trạm, Postgres staging, RH derive production, dashboard charts.

---

## Phase 5b – Integration (chỉ sau Gate B ≠ C)

### Mục tiêu

Pipeline tái lập: Open-Meteo API → MinIO raw JSON → processed `om_*` Parquet; mirror pattern UCI Phase 3/4.

Scale path:

```text
1 station × full UCI range
        ↓
rerun idempotent
        ↓
12 stations
```

### Definition of Done – Phase 5b

```text
[x] Raw OM trên MinIO + sidecar request metadata
[x] Processed om_* Parquet reproducible + idempotent
[x] DAG chạy thành công ≥ 1 station full range
[x] Fill-rate / join check documented
[x] Role cuối (thường B) khóa trong docs
```

Postgres staging `weather_openmeteo_hourly`, dbt join `weather_final`, RH derive production → **Phase 6+**.

---

# 11. Phase 6 – PostgreSQL Staging

## Mục tiêu

Load processed data vào relational staging trên DB `air_quality_dw`, schema `staging`.

Volume Postgres đã init từ Phase 2 nên **DDL do loader apply** (`config/postgres/ddl/staging.sql`), không dựa vào `docker-entrypoint-initdb.d`.

Bảng:

```text
staging.air_quality_hourly          -- 1:1 Parquet UCI processed
staging.weather_openmeteo_hourly    -- 1:1 Parquet Open-Meteo processed
staging.station_reference           -- 1:1 data/raw/reference/stations.csv
staging.load_registry               -- vận hành: idempotency (không phải fact)
```

Không làm ở Phase 6 (để Phase 7): `weather_final`, derive RH, model `stg_*` / dim / fact. “dbt có thể đọc staging” = project dbt tối thiểu + `sources.yml` + `dbt debug` / `dbt parse`.

## Quyết định load

- Cột hourly = cột Parquet canonical. Weather UCI nằm trong `air_quality_hourly`. Không join, không impute.
- `event_time_local` là `timestamp without time zone` (wall clock Asia/Shanghai).
- Unique `(station_name, event_time_local)`. `station_reference` unique `station_id` và `station_name`.
- Chọn object processed có `process_date` mới nhất. Không đọc `processed/quarantine/`.
- Hourly: một transaction `DELETE` theo `station_name` rồi `COPY`. Reference: `TRUNCATE` + `COPY`.
- Skip khi `load_registry` khớp object key mới nhất + sidecar `source_sha256` + `schema_version` + `row_count`, và bảng vẫn còn đúng số dòng đó (reference: SHA-256 file CSV, key ổn định `data/raw/reference/stations.csv`).
- Đổi checksum hoặc schema → replace slice trạm đó (không fail kiểu no-overwrite của MinIO).

## Kiểm tra

Sau load:

```text
source count (sidecar row_count)
vs
target count
```

Kiểm tra:

- duplicates trên natural key;
- station count;
- date range `2013-03-01 00:00` → `2017-02-28 23:00` khi đủ 35 064 giờ;
- NULL trên natural key;
- type cột khớp DDL.

Artifact: `artifacts/staging/`.

## Milestones

```text
K6-01  Spec & DDL
K6-02  Library (DDL apply + loaders + CLI + tests)
K6-03  Slice 1 trạm Wanshouxigong qua CLI/Airflow
K6-04  Scale 12 trạm + idempotent rerun + đối soát
K6-05  Docs, dbt sources smoke, đóng DoD
```

## WBS

### K6-01 Spec

- Ghi quyết định load + WBS vào mục này và kickoff `docs/PROGRESS.md`
- DDL `config/postgres/ddl/staging.sql` (4 bảng, PK/unique)

### K6-02 Library

- `src/staging/` resolve latest Parquet + sidecar, load UCI, load Open-Meteo, load `station_reference`, ghi registry
- CLI `scripts/load_staging.py` (`--station` / `--all`)
- Unit tests: skip-if-same, replace-on-change, không đụng quarantine

### K6-03 One-station slice

- DAG `staging_load` — `ensure_schema` → `load_station_reference` → `load_air_quality` → `load_openmeteo` → `reconcile`
- Default station `Wanshouxigong`; conf `station` / `stations`
- Verify 35 064 hàng mỗi bảng hourly, unique key, MinIO không đổi, rerun → `skipped_identical`

### K6-04 Scale 12

- `--all` / conf 12 stations
- Rerun full → skip
- `scripts/verify_staging_load.py` → `artifacts/staging/`

### K6-05 Close

- README + Airflow README
- `dbt/air_quality_dbt/` sources cho 3 bảng nghiệp vụ; smoke parse/debug
- Tick DoD; PROGRESS; PR `feature/postgres-staging`

## Definition of Done

```text
[x] Processed → PostgreSQL load reproducible
[x] Row count reconciled
[x] Key uniqueness kiểm tra
[x] Schema rõ
[x] dbt có thể đọc staging
```

---

# 12. Phase 7 – Data Warehouse & dbt

## Mục tiêu

Xây dựng dimensional warehouse phục vụ analytics.

## Bước 1 – Grain (đã chốt)

Grain Phase 1, xác nhận trên dữ liệu staging:

```text
1 station × 1 hour
```

12 trạm × 35.064 giờ (`2013-03-01 00:00` → `2017-02-28 23:00`) = 420.768 dòng fact.

## Bước 2 – Weather modeling (đã chốt)

Một fact, không tách weather fact. UCI và Open-Meteo cùng grain station-hour, join 1:1.

Resolve trên `int_station_hour` rồi ghi vào `dwh.fact_air_quality_hourly`:

- số liệu thời tiết: UCI nếu có giá trị, không thì Open-Meteo, cả hai thiếu thì null (không impute);
- `*_source` ∈ `uci` | `openmeteo` | null;
- `wind_direction`: text 16 hướng của UCI; khi UCI trống thì `round(độ / 22.5) mod 16` sang cùng bộ hướng;
- `cloud_cover_pct` chỉ từ Open-Meteo;
- `relative_humidity_pct` derive từ nhiệt độ và điểm sương đã resolve (Magnus / Alduchov & Eskridge 1996), kẹp 0–100; null nếu thiếu một trong hai hoặc ≤ −240;
- pollutant không fill từ Open-Meteo;
- `has_missing_*` và `data_quality_status` trên fact mô tả dòng đã resolve. Cờ UCI gốc nằm ở staging. `SUSPECT_CAP` vẫn ưu tiên hơn `MISSING_MEASUREMENT`;
- mart: `hour_count` là số giờ lịch, `*_hour_count` là số giờ không null đi vào từng average / tổng mưa;
- `dim_date.week_of_year` là tuần ISO, đi với `iso_year`.

Cột thô từng nguồn nằm ở `staging` / `stg_*`.

## Core models

```text
staging.stg_air_quality          view
staging.stg_weather_openmeteo    view
staging.stg_station              view
staging.int_station_hour         view
dwh.dim_station                  table   station_key = station_id
dwh.dim_date                     table   date_key YYYYMMDD, 1461 ngày
dwh.dim_time                     table   time_key = giờ 0–23
dwh.fact_air_quality_hourly      table   420768
mart.mart_station_daily          table   17532 (12 × 1461)
mart.mart_station_monthly        table   576 (12 × 48), avg từ fact
mart.mart_pollution_weather      table   station-day PM2.5/PM10/O3 + weather
```

`mart_pm25_episodes` (+ multi-station) đã làm ở Phase 8. Macro `generate_schema_name` dùng schema `staging` / `dwh` / `mart` đúng tên, không prefix `staging_`.

## dbt tests

Tối thiểu kiểm tra:

```text
not_null
unique
relationships
accepted_values
```

khi phù hợp.

## Analytical marts

Chỉ tạo mart phục vụ query thật.

Ví dụ:

```text
mart_station_daily
mart_station_monthly
mart_pollution_weather
mart_pm25_episodes              # Phase 8d — lock 115 / 3h
mart_pm25_multi_station_events  # Phase 8d — K=6
```

## Definition of Done

```text
[x] Grain được document
[x] Dimensions hoạt động
[x] Fact hoạt động
[x] dbt tests pass (52/52)
[x] Data lineage staging → DWH rõ
[x] Một số OLAP-style queries chạy đúng
```

---

# 13. Vertical Slice Milestone

Đây là milestone quan trọng đầu tiên.

Trước khi coi phần Data Engineering ổn, phải demo được:

```text
1 UCI station
      ↓
Airflow
      ↓
MinIO Raw
      ↓
Processing
      ↓
MinIO Processed
      ↓
PostgreSQL staging
      ↓
dbt
      ↓
DWH
      ↓
SQL analytical query
```

Nếu vertical slice chưa chạy:

> Không tiếp tục thêm hàng loạt module.

---

# 14. Phase 8 – Exploratory & Analytical Analysis

## Mục tiêu

Hiểu dữ liệu từ DWH trước khi train model.

EDA chính thức phải ưu tiên đọc dữ liệu từ:

```text
DWH / analytical dataset
```

không xây toàn bộ kết quả cuối trực tiếp trên CSV source.

## Phân tích

### Temporal

- hourly;
- daily;
- monthly;
- seasonal.

### Station

- mean/median;
- variance;
- peaks;
- ranking.

### Pollutant

- PM2.5;
- PM10;
- SO₂;
- NO₂;
- CO;
- O₃.

### Weather

- temperature;
- pressure;
- dew point/humidity;
- rainfall;
- wind;
- cloud cover (nếu enrichment đã có).

### Pollution episodes (phạm vi Phase 8)

Trả lời câu hỏi trong `PROJECT_CONTEXT.md`:

> Các đợt ô nhiễm cao thường kéo dài bao lâu?

Phạm vi phân tích gồm theo trạm, đa-trạm và điều kiện thời tiết liên quan.

**Công việc trong Phase 8:**

1. Chốt và document ngưỡng “PM2.5 cao” sau EDA (phân vị / guideline — nêu rõ lý do).
2. **Theo từng trạm:** đoạn giờ liên tiếp ≥ ngưỡng = một episode; thống kê số lượng, độ dài, phân bố theo mùa/năm; so sánh giữa các trạm.
3. **Đa trạm:** xác định khoảng thời gian nhiều trạm cùng trong episode (hoặc overlapping); mức độ lan theo không gian (số trạm đồng thời).
4. **Gắn weather:** trong mỗi episode (hoặc cửa sổ quanh episode), tóm tắt điều kiện khí tượng (vd. TEMP, WSPM, RH derive, cloud nếu có) — tương quan/pattern, không khẳng định nhân quả.
5. Materialize **`mart_pm25_episodes`** (và nếu cần bảng phụ episode–station / episode summary) để notebook và dashboard tái sử dụng.

Phân tích trên lịch sử DWH; không xây detector vận hành realtime.  
Definition of Done Phase 8 bao gồm các mục episode bên dưới trước khi chuyển Phase 9.

## Quyết định làm việc (kickoff Phase 8)

Phạm vi **Full DoD** (temporal + station + đủ pollutant + weather + episodes + ML candidates).

| Hạng mục | Chốt working |
|----------|----------------|
| Nguồn đọc | `dwh.fact_air_quality_hourly` + dims / mart hiện có — không CSV raw |
| Ngưỡng ứng viên | Cố định **75** và **115**; thêm **P90/P95** toàn mạng (có bảng P90/P95 theo trạm để so) |
| Min độ dài | Chính **3h**; sensitivity **1h** và **6h** |
| Null PM2.5 giữa chuỗi | **Cắt** episode (không nối qua thiếu số) |
| Đa-trạm K | Report **K=3,6,9**; chốt 1 K sau notebook (fallback **K=3**) |
| Mart | `mart_pm25_episodes` (1 station × 1 episode) + `mart_pm25_multi_station_events` |
| Branch | `feature/phase-8-eda` (từ tip Phase 7) |

**Gate trước dbt mart:** `artifacts/eda/episode_definition.md` (bộ `(threshold, min_hours, K)` + lý do).

## Output

```text
analysis notebook
+
reusable analytical queries
+
candidate insights
+
mart_pm25_episodes (+ mart đa-trạm + tài liệu ngưỡng và định nghĩa episode)
```

## WBS (P8-01 → P8-24)

### P8a – Kickoff

- **P8-01** Branch `feature/phase-8-eda`; smoke fact (420768 rows / 12 stations)
- **P8-02** Skeleton `notebooks/eda/`, `artifacts/eda/`, `sql/eda/`; WBS + PROGRESS kickoff
- **P8-03** Helper đọc DWH `src/eda/db.py` + `scripts/smoke_dwh_fact.py`

### P8b – Full EDA

- **P8-04** Temporal (hourly / daily / monthly / seasonal)
- **P8-05** Station (mean / median / variance / peaks / ranking)
- **P8-06** Pollutant suite (PM2.5, PM10, SO₂, NO₂, CO, O₃)
- **P8-07** Weather ↔ pollution (pattern, không causal)
- **P8-08** Data issues + `artifacts/eda/eda_findings.md`

### P8c – Episodes

- **P8-09** Prototype island detection (SQL/Python)
- **P8-10** Sensitivity threshold × min_hours
- **P8-11** Concurrent stations + K grid
- **P8-12** Lock → `artifacts/eda/episode_definition.md`
- **P8-13** Stats theo trạm (duration, season/year)
- **P8-14** Multi-station analysis
- **P8-15** Weather-in-episode analysis

### P8d – Marts

- **P8-16** dbt vars + `mart_pm25_episodes`
- **P8-17** `mart_pm25_multi_station_events`
- **P8-18** YAML / sanity tests
- **P8-19** `dbt run` + `dbt test` + `artifacts/eda/mart_episode_checks.json`

### P8e – Close

- **P8-20** `artifacts/eda/ml_feature_candidates.md`
- **P8-21** Docs sync (PLAN / CONTEXT / ARCH / PROGRESS)
- **P8-22** Tick DoD Phase 8
- **P8-23** Evidence bundle review
- **P8-24** PR khi được yêu cầu

## Phân chia Phase 8

```text
P8a  Kickoff + smoke DWH
P8b  Full EDA notebooks
P8c  Episode sensitivity → lock definition
P8d  dbt marts + tests
P8e  ML candidates + đóng DoD
```

## Definition of Done

```text
[x] Seasonal patterns được hiểu
[x] Station differences được hiểu
[x] Weather relationships được kiểm tra
[x] PM2.5 episodes theo trạm: ngưỡng, độ dài, phân bố mùa/năm được document
[x] Episode đa-trạm (overlapping / số trạm đồng thời) được phân tích
[x] Episode gắn tóm tắt weather trong khoảng episode được phân tích
[x] mart_pm25_episodes (hoặc tương đương) dùng được từ SQL
[x] Data issues mới được document
[x] Candidate ML features được xác định
```

Evidence: `artifacts/eda/eda_findings.md`, `episode_definition.md`, `ml_feature_candidates.md`, `mart_episode_checks.json`; marts `mart.mart_pm25_episodes` (6318), `mart.mart_pm25_multi_station_events` (487).

---

# 15. Phase 9 – Station Clustering

## Mục tiêu

Phân nhóm các trạm có profile ô nhiễm tương đồng.

## Không làm

Không đơn giản chạy:

```text
KMeans(all hourly rows)
```

rồi nói đó là cluster station.

## Hướng chính

Xây station profiles → standardize → cluster → evaluate → interpret.

## Decisions (locked)

- Window: **2013-03-01 → 2016-12-31** (bỏ 2017 partial)
- Features v1: pollutant stats + seasonal PM2.5 + pct ≥75/115 + episode stats; **không** lat/lon/district/weather trong model
- Method: **KMeans K=2**, `random_state=42`; Ward hierarchical đối chiếu (agreement 1.0)
- Labels: `elevated_core` (9) / `cleaner_outskirts` (3)
- Persist: dbt seed `station_cluster_assignment` → `mart.mart_station_cluster` (không sửa `dim_station`)

## WBS (P9-01 → P9-30)

### P9a – Kickoff

- **P9-01** Branch `feature/phase-9-clustering`
- **P9-02** Skeleton `artifacts/clustering/`, `sql/clustering/`, `src/clustering/`
- **P9-03** Smoke window + episode mart → `kickoff_smoke.json`
- **P9-04** PROGRESS kickoff

### P9b – Station profiles

- **P9-05…P9-11** `station_pollution_profile.sql` → `station_profiles.csv` + feature dictionary + QC

### P9c – Clustering → lock

- **P9-12…P9-19** KMeans grid + Ward + figures → `cluster_lock.json`

### P9d – Mart

- **P9-20…P9-23** seed + `mart_station_cluster` + dbt tests + `mart_cluster_checks.json`

### P9e – Close

- **P9-24…P9-28** interpretation, cluster vs district, ML candidates, PLAN/CONTEXT sync

### P9f – PR

- **P9-29…P9-30** Evidence review + PR khi được yêu cầu

## Phân chia

```text
P9a  Kickoff + smoke
P9b  Station profiles
P9c  Clustering experiments → lock
P9d  dbt seed + mart + tests
P9e  Interpretation + docs
P9f  PR (optional)
```

## Definition of Done

```text
[x] Station profiles (1 row/station) documented
[x] Không cluster grain hourly
[x] KMeans + hierarchical + K selection documented
[x] cluster_lock.json + assignment + profiles + figures
[x] Interpretation + cluster vs district
[x] mart.mart_station_cluster queryable; dbt tests PASS
[x] ml_feature_candidates cập nhật cluster_id
[x] PROGRESS + IMPLEMENTATION_PLAN + PROJECT_CONTEXT sync
```

Evidence: `artifacts/clustering/` (profiles, lock, methodology, interpretation, mart checks, figures); `mart.mart_station_cluster`.

---

# 16. Phase 10 – PM2.5 Forecasting

## Mục tiêu

Xây dựng mô hình dự báo PM2.5.

## Target ban đầu

```text
PM2.5(t+1h)
```

## Decisions (locked tại kickoff P10a)

- Horizon: **t+1h** only (multi-horizon = P2)
- ML window: **2013-03-01 → 2016-12-31**; 2017 excluded from primary eval
- Split: Train → **2015-12** | Val **2016-01→06** | Test **2016-07→12**
- Strategy: **global model** (station + `cluster_id` features); không 12 per-station models trong DoD
- Models: Persistence → LinearRegression → HistGradientBoosting (sklearn)
- Features v1: calendar; **PM2.5 at t**; lags 1/2/3/6/12/24 + roll 6h/24h; weather at t + lag1; station; `cluster_id`
- Persistence baseline: `y_hat(t+1) = PM2.5(t)` (`pm25_ug_m3`), not `pm25_lag_1`
- Persist: artifacts + **`mart.pm25_predictions`** (P10d); model → `models/pm25_forecast/`
- Metrics: MAE primary; RMSE, R² secondary

## Bước 1 – Baseline

Persistence:

```text
prediction(t+1)
=
PM2.5(t)
```

Machine Learning phải đánh bại baseline hoặc ít nhất giải thích được vì sao không.

## Bước 2 – Feature engineering

Candidate (v1 locked):

```text
station / cluster_id
hour / month / season
PM2.5 lags + rolling
weather at t (+ lag 1)
```

Chỉ dùng feature hợp lệ tại prediction time.

## Bước 3 – Split

Chronological (locked):

```text
Train  2013-03 → 2015-12
Val    2016-01 → 2016-06
Test   2016-07 → 2016-12
```

Không random split. 2017 = optional sensitivity only.

## Bước 4 – Models

```text
Persistence
Linear Regression
HistGradientBoosting
```

Chỉ thêm model khác khi có lý do.

## Metrics

Primary:

```text
MAE
```

Secondary:

```text
RMSE
R²
```

## WBS (P10-01 → P10-30)

### P10a – Kickoff

- **P10-01** Branch `feature/phase-10-forecasting`
- **P10-02** Skeleton `artifacts/forecasting/`, `sql/forecasting/`, `src/forecasting/`, `models/pm25_forecast/`
- **P10-03** Smoke fact ML window + cluster join → `kickoff_smoke.json`
- **P10-04** PROGRESS + PLAN WBS kickoff

### P10b – Feature pipeline

- **P10-05…P10-12** Extract → lags/rolling/target t+1 → split helpers → leakage QC → feature dictionary

### P10c – Baseline + models → lock

- **P10-13…P10-20** Persistence + Linear + HistGB; Val/Test metrics → `model_lock.json`

### P10d – Artifacts + mart

- **P10-21…P10-25** `models/pm25_forecast/` + `mart.pm25_predictions` + dbt tests + `mart_prediction_checks.json`

### P10e – Close

- **P10-26…P10-28** Error analysis, docs sync; optional episode features / 2017 sensitivity

### P10f – PR

- **P10-29…P10-30** Evidence review + PR khi được yêu cầu

## Phân chia

```text
P10a  Kickoff + smoke
P10b  Feature pipeline + leakage QC
P10c  Baseline + models → lock
P10d  Model artifacts + mart + tests
P10e  Error analysis + docs
P10f  PR (optional)
```

## Definition of Done

```text
[x] Baseline tồn tại
[x] No leakage
[x] Split đúng thời gian
[x] Feature pipeline reproducible
[x] ≥2 model được so sánh hợp lý
[x] Test result được ghi lại
[x] Error analysis được thực hiện
[x] mart.mart_pm25_predictions queryable; dbt tests PASS
[x] PROGRESS + IMPLEMENTATION_PLAN + PROJECT_CONTEXT sync
```

Evidence: `artifacts/forecasting/` (kickoff, feature_qc, model_lock, metrics, error_analysis, mart checks, figures);
`models/pm25_forecast/`; `mart.mart_pm25_predictions`.

---

# 17. Global model vs station-specific model

Working strategy:

> Thử **global model cho toàn bộ station trước**.

Input có thông tin station.

Sau đó nếu cần có thể so sánh:

```text
global model
vs
per-station model
```

Không mặc định train 12 model ngay.

Global model:

- ít code lặp;
- tận dụng nhiều dữ liệu;
- hợp quy mô nhóm.

---

# 18. Phase 11 – Web Dashboard

## Mục tiêu

Tạo giao diện trực quan (read-only) để khám phá kết quả DWH / marts / ML.

## Công nghệ (locked P11a – 2026-10-10)

```text
FastAPI  →  PostgreSQL (dwh / mart)
React (Vite + TS) + Mantine + ECharts + react-leaflet
```

- **Không** Streamlit; **không** Tailwind / Redux / Zustand / auth.
- UI tiếng Việt; chỉ hiển thị dữ liệu (filter → chart/table/map).
- Map MVP: 12 marker Leaflet (coords LITERATURE). Heatmap nội suy kiểu Windy = nice-to-have sau, không DoD.

## Minimum Viable Dashboard

### Tổng quan

- KPI; xu hướng pollutant; chọn trạm; lọc ngày.

### Trạm

- so sánh; xếp hạng; cluster (`mart_station_cluster`).

### Đợt ô nhiễm

- độ dài / số episode theo trạm;
- phân bố theo thời gian;
- sự kiện đa-trạm;
- weather trong episode — `mart_pm25_episodes` / `mart_pm25_multi_station_events`.

### Thời tiết

- quan hệ với PM2.5; filter; scatter/time-series — `mart_pollution_weather`.

### Dự báo

- actual vs predicted; lỗi; metric tóm tắt; lọc trạm/ngày/split — `mart_pm25_predictions`.

### Bản đồ

- 12 điểm + màu cluster/PM; popup; chú thích nguồn coords.

## WBS (P11a → P11f)

### P11a – Lock + skeleton

- Branch `feature/phase-11-dashboard`
- Docs lock stack; scaffold `dashboard/api` + `dashboard/web`
- `GET /api/health`, `GET /api/stations`

### P11b – Tổng quan + Trạm

- KPI, trends, compare/rank, cluster

### P11c – Đợt ô nhiễm + Thời tiết

### P11d – Dự báo + Bản đồ

### P11e – Polish tối thiểu + Docker/README

- `dashboard-api` trong `docker-compose.yml` + `dashboard/api/Dockerfile`
- `dashboard/README.md` hướng dẫn demo; DoD đánh dấu

### P11f – Close / PR khi được yêu cầu

## Definition of Done

```text
[x] Dashboard đọc DWH/marts qua FastAPI
[x] Filter hoạt động
[x] Charts rõ (ECharts)
[x] Clustering hiển thị
[x] Pollution episodes hiển thị (từ mart)
[x] Prediction hiển thị
[x] Map 12 trạm (Leaflet)
[x] Không đọc trực tiếp CSV raw cho kết quả chính
[x] Không auth / CRUD / train model từ UI
```

---

# 19. Phase 12 – Integration & Hardening

## Mục tiêu

Biến các module rời thành một project hoàn chỉnh — chứng minh chuỗi end-to-end còn sống, không làm feature mới.

```text
source → lake → processing → staging → DWH → mining → dashboard
```

## Decisions (locked P12a – 2026-10-11)

- **E2E = Hybrid:** không `docker compose down -v`; giữ volume; smoke idempotent toàn chuỗi; thêm **1 slice fresh** (Wanshouxigong).
- **Mining = Verify + docs:** không retrain P9/P10; kiểm artifacts / `models/` / mart + `check_mart_*`; ghi rõ recreate nếu volume mất.
- **Không** meta-DAG orchestration mới — dùng DAG/script hiện có + runbook.
- **Dashboard web** giữ local `npm run dev`; API Compose `:8100`.
- Branch: `feature/phase-12-integration`.
- Evidence: `artifacts/integration/` + runbook `artifacts/integration/runbook_hybrid.md`.

## Ngoài phạm vi

- Full rebuild từ `down -v`; retrain HistGB / re-lock clustering
- Heatmap / auth / Dockerize web / report (Phase 13)

## WBS (P12a → P12f)

### P12a – Lock + skeleton

- Branch + docs (PLAN §19, PROGRESS)
- `artifacts/integration/` + runbook hybrid

### P12b – Infra smoke (giữ volume)

- Compose healthy: postgres, minio, airflow-*, `dashboard-api`
- Evidence: compose ps + Airflow `/health`

### P12c – Pipeline idempotent + slice fresh

- Idempotent: ingest/process UCI → Open-Meteo (skip OK) → staging → `dbt run` + `dbt test`
- Slice: Wanshouxigong path không chỉ skip (DAG/CLI)
- Evidence JSONL / logs dưới `artifacts/integration/`

### P12d – Mining verify + dashboard smoke

- `check_mart_cluster` / `check_mart_episodes` / `check_mart_predictions` / `run_olap_checks`
- Dashboard: health, stations, overview, episodes, predictions meta, map (12)
- Web: `npm run build` (screenshot → Phase 13)

### P12e – Hardening / cleanup

- Scan secret / hard-coded path; sửa nếu phát hiện
- README mục Phase 12; tick DoD; đóng PROGRESS

### P12f – Close / PR khi được yêu cầu

## Definition of Done

```text
[ ] Compose services healthy trên volume hiện có (không bắt buộc down -v)
[ ] Idempotent rerun pipeline không fail (skip OK)
[ ] Slice fresh 1 trạm chứng minh path hoạt động
[ ] dbt test PASS
[ ] Mart checks (episodes/cluster/predictions) + OLAP smoke OK
[ ] Mining artifacts verified; không bắt buộc retrain
[ ] Dashboard API (+ web build) smoke OK
[ ] Runbook + evidence trong artifacts/integration/
[ ] Không secret trong repo; cleanup rõ ràng nếu phát hiện
[ ] PLAN DoD + PROGRESS đóng phase
```

## Cleanup (khi phát hiện)

- hard-coded path; password trong repo; code trùng / experiment thừa
- notebook-only logic cần productionize (chỉ nếu chặn demo)

---

# 20. Phase 13 – Report & Demo Preparation

Đây mới là lúc chuyển hệ thống thành nội dung bài tập lớn.

Không bắt đầu report cuối quá sớm khi hệ thống chưa ổn.

Cần chuẩn bị evidence:

```text
Architecture
Airflow DAG
MinIO objects
Processed data
PostgreSQL DWH
dbt models/tests
Dashboard
Clustering
Prediction
Metrics
```

Ảnh chụp nên lấy từ hệ thống thật.

Không dựng screenshot giả chỉ để báo cáo đẹp.

---

# 21. Chia việc cho nhóm 2 người

Không chia cứng từ đầu kiểu:

```text
Người A = Data Engineering
Người B = Machine Learning
```

vì cuối kỳ một người sẽ không hiểu nửa còn lại.

Tốt hơn là mỗi người có **primary ownership**, nhưng vẫn review phần của nhau.

## Thành viên A – Primary Data Pipeline

Primary:

- Docker;
- Airflow;
- MinIO;
- ingestion;
- processing;
- PostgreSQL staging.

Secondary:

- review DWH;
- hỗ trợ dashboard data access;
- hiểu ML pipeline.

## Thành viên B – Primary Analytics

Primary:

- profiling;
- dbt/DWH modeling;
- EDA;
- clustering;
- ML;
- dashboard.

Secondary:

- review ingestion;
- hiểu Airflow/MinIO;
- kiểm thử pipeline.

### Shared

Cả hai cùng làm:

- architecture decisions;
- data-quality rules;
- DWH grain;
- Open-Meteo decision;
- model interpretation;
- integration;
- demo;
- báo cáo.

---

# 22. Có thể làm song song như thế nào?

Sau Phase 1:

```text
A
Infrastructure + ingestion

B
Station metadata + data exploration
```

Sau khi staging có dữ liệu:

```text
A
Pipeline hardening

B
dbt / DWH
```

Khi DWH ổn:

```text
A
Dashboard infrastructure / integration

B
Clustering + ML
```

Sau đó:

```text
A + B
Integration
↓
Testing
↓
Report/demo
```

---

# 23. Không tối ưu việc chia task quá sớm

Nếu trong thực tế một thành viên:

- mạnh Python;
- mạnh SQL;
- mạnh frontend;
- có nhiều thời gian hơn;

có thể điều chỉnh ownership.

Nguyên tắc vẫn là:

> Không tạo một “single point of failure” mà chỉ một người hiểu một subsystem quan trọng.

---

# 24. PROGRESS.md

`PROGRESS.md` được tạo ngay khi bắt đầu Phase 0.

Format:

```text
## YYYY-MM-DD

### Current phase

### Completed

### Evidence

### Decisions

### Problems

### Next
```

Không cần ghi từng lệnh terminal.

Chỉ ghi thông tin giúp phiên sau hiểu:

- đã làm gì;
- kết quả ra sao;
- quyết định gì;
- đang mắc ở đâu.

---

# 25. Decision Gate

Một số phase không được đi tiếp tự động.

## Gate A – Sau profiling

Phải hiểu dữ liệu trước khi chốt DWH.

## Gate B – Open-Meteo

Phải chứng minh vai trò của nguồn này trước khi tải toàn bộ.

## Gate C – DWH

Warehouse phải ổn trước khi model cuối được xây.

## Gate D – ML

Phải có baseline và leakage check trước khi coi model tốt.

## Gate E – Dashboard

Dashboard phải sử dụng pipeline thật, không bypass DWH.

---

# 26. Priority levels

### P0 – Bắt buộc

- raw ingestion;
- MinIO;
- ETL;
- staging;
- DWH;
- dbt;
- analysis;
- clustering;
- PM2.5 forecasting;
- dashboard.

### P1 – Nên có

- Open-Meteo enrichment;
- data-quality report;
- prediction table;
- map station;
- automated tests.

### P2 – Chỉ làm nếu dư thời gian

- forecast nhiều horizon;
- PM10 prediction;
- advanced spatial visualization;
- model tuning sâu;
- extra ML models.

P2 không được làm khi P0 chưa hoàn chỉnh.

---

# 27. Thứ tự ưu tiên khi thiếu thời gian

Nếu tiến độ gặp vấn đề:

```text
1. Data correctness
2. Pipeline end-to-end
3. DWH
4. Analysis
5. PM2.5 baseline + ML
6. Dashboard
7. Clustering
8. Extra enrichment
9. Extra models/features
```

Không bỏ Data Warehouse để dành thời gian chạy thêm model.

Đây là môn:

**Kho dữ liệu và Khai phá dữ liệu**

nên cả hai phần phải tồn tại rõ ràng.

---

# 28. Anti-scope-creep

Không tự động thêm:

```text
Kafka
Spark
Hadoop
Kubernetes
real-time IoT
LSTM
Transformer
complex GIS
```

Nếu một công nghệ mới được đề xuất, phải trả lời:

```text
Vấn đề hiện tại là gì?
Công nghệ mới giải quyết gì?
Có cách đơn giản hơn không?
Chi phí triển khai?
Lợi ích cho bài?
```

---

# 29. Tiêu chí hoàn thành toàn dự án

Project được xem là hoàn thành khi hai thành viên có thể chạy và giải thích:

```text
UCI CSV
+
Weather source
      ↓
Airflow
      ↓
MinIO
      ↓
Processing
      ↓
PostgreSQL staging
      ↓
dbt
      ↓
Data Warehouse
      ↓
 ┌────┴─────┐
 ↓          ↓
Mining     Dashboard
 ↓
PM2.5 Forecast
```

Và trả lời được:

- Vì sao có Data Lake?
- Vì sao cần staging?
- Vì sao dùng dbt?
- Grain của warehouse là gì?
- Fact và dimension được thiết kế thế nào?
- Missing được xử lý ra sao?
- Open-Meteo có giá trị gì?
- Cluster nói lên điều gì?
- Model dự báo thời điểm nào?
- Baseline là gì?
- Có leakage không?
- Metric bao nhiêu?
- Dashboard lấy dữ liệu từ đâu?

---

# 30. Trình tự bắt đầu thực tế

Khi bắt đầu code, **không dựng tất cả một lúc**.

Thứ tự làm ngay:

```text
STEP 1
Thu đủ 12 UCI files

STEP 2
Viết script profiling

STEP 3
Profile toàn dataset

STEP 4
Cập nhật DATA_GUIDE

STEP 5
Khởi tạo repository

STEP 6
Dựng PostgreSQL + MinIO

STEP 7
Ingest Wanshouxigong

STEP 8
Processed pipeline

STEP 9
PostgreSQL staging

STEP 10
dbt + minimal DWH

STEP 11
Chứng minh vertical slice

STEP 12
Mở rộng 12 stations
```

Chỉ sau vertical slice này mới chuyển mạnh sang Open-Meteo, analytics và Machine Learning.

---

# 31. Milestone chính

## Milestone 1 – Data Understood

```text
12 stations profiled
```

## Milestone 2 – Infrastructure Ready

```text
Docker + MinIO + PostgreSQL + Airflow
```

## Milestone 3 – Vertical Data Pipeline

```text
1 station
source → DWH
```

## Milestone 4 – Full Warehouse

```text
12 stations → DWH
```

## Milestone 5 – Multi-source Integration

```text
UCI + Open-Meteo
```

## Milestone 6 – Analytics

```text
EDA + station analysis
```

## Milestone 7 – Mining

```text
Clustering + PM2.5 forecasting
```

## Milestone 8 – Product

```text
Web Dashboard
```

## Milestone 9 – Final Integration

```text
End-to-end demo
```

---

# 32. Bước tiếp theo ngay sau tài liệu này

Task triển khai đầu tiên:

> **Thu thập đủ 12 file UCI và xây dựng script profiling toàn dataset.**

Không cần Airflow ngay ở task đầu tiên.

Profiling bằng Python trước giúp tránh dựng architecture dựa trên giả định.

Output đầu tiên cần đạt:

```text
station_profile.csv
+
profiling_report.md
```

Sau khi có chúng:

> quay lại `DATA_GUIDE.md`, cập nhật các phát hiện thực tế rồi mới triển khai infrastructure.