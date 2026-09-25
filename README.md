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

Đã kiểm tra trên máy phát triển (2026-09-25):

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

Khởi động (sau khi copy `.env.example` → `.env`):

```powershell
copy .env.example .env
docker compose up airflow-init
docker compose up -d
docker compose ps
```

- Airflow UI: http://localhost:8080 (user/password từ `_AIRFLOW_WWW_USER_*` trong `.env`)
- Sample DAG: `sample_hello` (unpause + Trigger trong UI)
- Chi tiết Airflow: `config/airflow/README.md`
- Layout Data Lake: `config/minio/bucket_layout.md`

Network Docker: `air-quality-network` (DNS nội bộ: `postgres`, `minio` — không dùng `localhost` giữa container).
---

## 6. Tài liệu tham chiếu

Chi tiết kiến trúc và kế hoạch thực hiện được lưu trữ trong thư mục [`docs/`](docs/):
- [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md): Bối cảnh dự án, phạm vi và mục tiêu kinh doanh.
- [`docs/DATA_GUIDE.md`](docs/DATA_GUIDE.md): Mô tả dữ liệu PRSA 12 trạm, ý nghĩa các biến và quy tắc chất lượng dữ liệu.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Kiến trúc kỹ thuật chi tiết từ Ingestion, MinIO, PostgreSQL DWH đến ML/Dashboard.
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md): Kế hoạch thực thi qua 14 phase chi tiết kèm Definition of Done.
- [`docs/PROJECT_WBS.xlsx`](docs/PROJECT_WBS.xlsx): Bảng phân rã công việc WBS chi tiết cho 2 thành viên.
- [`docs/PROGRESS.md`](docs/PROGRESS.md): Nhật ký theo dõi tiến độ từng phase.
