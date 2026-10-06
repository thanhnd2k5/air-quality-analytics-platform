# Project Progress Log

Tài liệu ghi nhận tiến độ thực hiện theo từng phase của dự án.

---

## 2026-10-06 (Phase 3 – **HOÀN THÀNH** kỹ thuật; chờ PR)

### Current phase
Phase 3 – UCI Ingestion → Data Lake (**P3-01 → P3-20 DONE** — PR #4)

### Completed
- **K3-01:** WBS + object-key convention + branch `feature/minio-ingestion`
- **K3-02:** `minio_client`, `uci_raw`, `uci_to_minio`, CLI, unit tests (4 passed)
- **P3-03:** mount `./data/raw` (ro); Airflow dùng `MINIO_ROOT_*`; `_PIP_ADDITIONAL_REQUIREMENTS=minio` chỉ trên webserver/scheduler (tránh fail init chạy root)
- **K3-03:** CLI upload Wanshouxigong; verify byte-identical SHA-256; rerun → `skipped_identical`; DAG `uci_ingest_raw` run `manual__2026-10-06T06:59:30+00:00` → **success** (`validate_source` + `upload_raw`)
- **K3-04:** ingest đủ 12 trạm; rerun 12 → toàn bộ skip; list MinIO = 12 stations
- **K3-05:** README + bucket_layout + evidence `artifacts/ingestion/` + tick DoD Phase 3
- **P3-20:** mở PR #4 `feature/minio-ingestion` → `main`

### Decisions
- Airflow client creds = `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (tránh lệch `MINIO_SECRET_KEY` trong `.env`)
- Host CLI smoke cũng dùng ROOT credentials

### Evidence
- `artifacts/ingestion/verify_wanshouxigong_p3-11.json`
- `artifacts/ingestion/ingest_all_p3-14.jsonl`, `ingest_all_rerun_p3-15.jsonl`
- `artifacts/ingestion/list_raw_uci_p3-14.json` (12 stations)
- `artifacts/ingestion/dag_runs_uci_ingest_raw.txt`, `compose_ps_p3.txt`, `airflow_health_p3.json`
- PR: https://github.com/thanhnd2k5/air-quality-analytics-platform/pull/4

### Next
- Review / merge PR #4
- Sau đó Phase 4 – Processing & Data Quality

---

## 2026-10-06 (Phase 3 – Kickoff / K3-01 Spec)

### Current phase
Phase 3 – UCI Ingestion → Data Lake (**K3-01** đang làm; WBS P3-01 → P3-20)

### Completed
- Chốt kế hoạch chi tiết Phase 3 + chia việc A/B trong `IMPLEMENTATION_PLAN.md` §8.
- Chốt object key / immutability / idempotency / SHA-256 / sidecar `.meta.json`.
- Cập nhật `config/minio/bucket_layout.md` với convention Phase 3.
- **P3-01:** branch `feature/minio-ingestion`.
- **P3-03:** mount `./data/raw` (ro) vào Airflow; inject `MINIO_*` + `UCI_*` env; default `_PIP_ADDITIONAL_REQUIREMENTS=minio`.
- **P3-04 → P3-09:** `minio_client`, `uci_raw` validation, `uci_to_minio` ingest, CLI `scripts/ingest_uci_station.py`, unit tests (4 passed), DAG `uci_ingest_raw`.

### Decisions
- Key: `raw/uci/air_quality/station=<Station>/ingestion_date=YYYY-MM-DD/<original_filename>`
- Không overwrite; cùng checksum → skip; khác checksum cùng key → fail.
- Validate lúc ingest chỉ nhẹ (inventory + 18 cột + station match); DQ nặng để Phase 4.
- Mount `./data/raw` (không chỉ `uci/`) để có cả `file_inventory.csv`.

### Next
- **K3-03:** Trigger DAG `uci_ingest_raw` (Wanshouxigong) + verify checksum + rerun idempotent
- Smoke CLI (host): `py scripts/ingest_uci_station.py --station Wanshouxigong` (cần MinIO up)
- DAG đã thêm: `airflow/dags/uci_ingest_raw_dag.py` (P3-09)

---

## 2026-09-29 (Phase 2 – **HOÀN THÀNH**)

### Current phase
Phase 2 – Environment & Infrastructure (**P2-01 → P2-30 DONE**)

### Completed (đóng gate)
- **P2-25 / P2-26:** Integration clean up + restart/volume persistence (marker Postgres/MinIO còn sau `down`/`up`/`restart`).
- **P2-27:** Recreate máy A từ repo + `.env`.
- **P2-28:** Thành viên B bận — **A làm hộ**: recreate lần 2 chỉ từ repo + `.env` (không secret ngoài `.env`); 4 service healthy; Airflow `/health` OK; MinIO bucket layout OK; DAG `sample_hello` list được.
- **P2-29:** README §5 start/stop/restart/`down -v`/UI/recreate checklist.
- **P2-30:** Evidence + PROGRESS; DoD Phase 2 trong `IMPLEMENTATION_PLAN.md` đánh dấu xong.

### Decisions
- P2-28 chấp nhận proxy recreate lần 2 trên máy A khi B không available (ghi rõ trong PROGRESS / DoD).

### Evidence
- `artifacts/infra/compose_ps_k2-05.txt`, `airflow_health_k2-05.json`
- `artifacts/infra/compose_ps_p2-28.txt`, `airflow_health_p2-28.json`
- README §5; `config/airflow/README.md`; `config/minio/bucket_layout.md`

### Next
- Chuyển **Phase 3 – UCI Ingestion → Data Lake**.

---

## 2026-09-29 (Phase 2 – Integration / K2-05)

### Current phase
Phase 2 – Environment & Infrastructure (**K2-01 → K2-05** xong trên máy A; **P2-28** chờ máy B) — **đã đóng phía trên**.

### Completed
- **P2-25:** `docker compose down` → `up airflow-init` → `up -d` — postgres / minio / airflow-webserver / airflow-scheduler cùng **healthy**.
- **P2-26:** Seed marker Postgres (`staging._p2_volume_probe`) + MinIO object; sau `compose down/up` và `compose restart` marker vẫn còn; DAG `sample_hello` vẫn list được.
- **P2-27:** Máy A dựng lại từ repo + `.env` (không secret ngoài `.env`) — OK.
- **P2-29:** README §5 bổ sung start / stop / restart / `down -v` reset / UI ports / recreate checklist 2 máy.
- **P2-30:** Evidence `artifacts/infra/compose_ps_k2-05.txt`, `artifacts/infra/airflow_health_k2-05.json`; cập nhật PROGRESS.

### Pending
- **P2-28:** — **đã xong** (A làm hộ B, xem entry HOÀN THÀNH phía trên).

### Evidence
- `artifacts/infra/compose_ps_k2-05.txt`
- `artifacts/infra/airflow_health_k2-05.json` (Airflow `/health` → metadatabase + scheduler healthy)
- README §5

### Next
- Phase 3.

---

## 2026-09-26 (Phase 2 – Airflow)

### Current phase
Phase 2 – Environment & Infrastructure (**K2-01 → K2-04** xong; tiếp **K2-05 integration**)

### Completed
- **P2-17:** Chốt Airflow tối thiểu — image `apache/airflow:2.10.5`, **LocalExecutor**, metadata DB `airflow_db`, services `airflow-init` / `webserver` / `scheduler` (`config/airflow/README.md`).
- **P2-18:** `airflow-init` migrate metadata + tạo user admin (`_AIRFLOW_WWW_USER_*`).
- **P2-19 / P2-20:** `airflow-webserver` (:8080) và `airflow-scheduler` healthy.
- **P2-21:** Mount `airflow/{dags,logs,plugins}` + `src` (`PYTHONPATH=/opt/airflow`).
- **P2-22:** SQLAlchemy URL nội bộ `postgres:5432/airflow_db` (ghép từ `POSTGRES_*` trong compose).
- **P2-23:** UI http://localhost:8080/health → 200; scheduler healthcheck OK.
- **P2-24:** DAG `sample_hello` trigger manual → **success**.

### Decisions
- Không dùng Celery/Redis ở Phase 2 — LocalExecutor đủ cho monorepo local.
- Connection string Airflow lấy từ `POSTGRES_USER`/`POSTGRES_PASSWORD` (tránh lệch URL cứng trong `.env`).

### Evidence
- `docker compose ps` → postgres / minio / airflow-webserver / airflow-scheduler **healthy**.
- DAG run `sample_hello` state **success**.

### Next
- **P2-25 → P2-30:** integration từ trạng thái sạch, restart/volume, recreate 2 máy, docs start/stop/reset, checkpoint — **K2-05 làm 2026-09-29** (còn P2-28 máy B).

---

## 2026-09-25 (Phase 2)

### Current phase
Phase 2 – Environment & Infrastructure (**K2-01 → K2-03** xong; tiếp **K2-04 Airflow**)

### Completed
- **P2-01:** Xác nhận Phase 1 đã qua Decision Gate (PR #3 trên `main`).
- **P2-02:** Ghi nhận Docker Engine **29.3.1**, Docker Compose **v5.1.1** (README §5).
- **P2-03:** Thêm `config/postgres/init/`, `config/minio/`, `scripts/infra/`, `airflow/logs/.gitkeep`.
- **P2-04:** Hoàn thiện `.env.example` (Postgres dw + airflow_db, MinIO single bucket, Airflow placeholders).
- **P2-05:** Compose network `air-quality-network` dùng chung cho postgres/minio.
- **P2-06 → P2-10:** Postgres healthy; DB `air_quality_dw` + schemas `staging/dwh/mart`; DB `airflow_db`; host port **5433** (tránh conflict 5432).
- **P2-11 → P2-16:** MinIO healthy (`coollabsio/minio` — Docker Hub `minio/minio` đã gỡ 2026-09); bucket `air-quality-lake` + prefix markers; upload/download sample OK.

### Decisions
- Warehouse DB name: `air_quality_dw` (khớp ARCHITECTURE).
- Host Postgres port mặc định: **5433** nếu máy đã chiếm 5432.
- MinIO image: `coollabsio/minio:latest` (thay `minio/minio` đã biến mất trên Docker Hub).

### Evidence
- `docker compose ps` → postgres/minio **healthy**.
- `config/`, `scripts/infra/`, `README.md` §5, `config/minio/bucket_layout.md`.

### Next
- **K2-04:** Airflow LocalExecutor + webserver/scheduler + sample DAG (P2-17 → P2-24) — **đã xong 2026-09-26**.
- **K2-05 / K2-06:** integration test, recreate trên 2 máy, docs start/stop.

---

## 2026-09-25 (Phase 1 closed)

### Current phase
Phase 1 – **HOÀN THÀNH** (P1-01 → P1-52; merged PR #3)

### Completed
- Đóng **Decision Gate Phase 1** (P1-39 → P1-47) dựa trên `artifacts/data_profile/`.
- **P1-38:** thống nhất không vẽ chart ở Phase 1; để Phase 5 (EDA) và Phase 11 (Dashboard).
- **P1-48 / P1-49:** cập nhật `docs/DATA_GUIDE.md` (v1.2) — full 12-station profile, missing strategy sơ bộ, extreme/physical rules, bảng assumptions xác nhận/bác bỏ (§53).
- **P1-50:** cập nhật checkpoint trong `PROGRESS.md` và trạng thái task trên WBS.
- **P1-51:** commit profiling script + artifacts + docs trên `feature/data-profiling`.
- **P1-52:** merge PR #3 vào `main` (`4ba4665`).

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
- GitHub PR: https://github.com/thanhnd2k5/air-quality-analytics-platform/pull/3

### Next
- Chuyển **Phase 2** (xem entry phía trên).

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
