# IMPLEMENTATION_PLAN.md

> **Project:** Phân tích và dự báo ô nhiễm không khí theo khu vực và điều kiện thời tiết  
> **Quy mô nhóm:** 2 thành viên  
> **Vai trò tài liệu:** Kế hoạch triển khai dự án theo phase và milestone  
> **Phiên bản:** 1.1  
> **Cập nhật:** 15/09/2026
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
Open-Meteo Integration
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

dbt và Streamlit có thể cấu hình sau.

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
[ ] docker compose up hoạt động
[ ] PostgreSQL healthy
[ ] MinIO healthy
[ ] Airflow healthy
[ ] Hai thành viên dựng được environment từ repo
[ ] Không cần cấu hình bí mật bằng tay ngoài .env
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

## Flow

```text
Local/source UCI
      ↓
Validation
      ↓
Airflow ingestion task
      ↓
MinIO Raw
```

## Raw path

Candidate:

```text
raw/uci/air_quality/
```

Object metadata nên lưu:

- source file;
- station;
- ingestion timestamp;
- checksum nếu triển khai;
- source identifier.

## Definition of Done

```text
[ ] 1 station ingest thành công
[ ] rerun không gây lỗi/dữ liệu sai
[ ] raw source không bị transform
[ ] mở rộng đủ 12 stations
[ ] Airflow hiển thị task status rõ
[ ] raw objects truy vết được tới source
```

---

# 9. Phase 4 – Processing & Data Quality

## Mục tiêu

Chuyển Raw thành dữ liệu chuẩn hóa có thể đưa vào relational staging.

## Flow

```text
MinIO Raw
↓
Python/Pandas
↓
Validation
↓
Standardization
↓
MinIO Processed
```

## Xử lý chính

- parse timestamp;
- canonical column names;
- datatype conversion;
- station normalization;
- unit validation;
- duplicate check;
- missing profiling;
- data quality flags;
- format conversion.

Output ưu tiên:

```text
Parquet
```

## Missing

Ở phase này mới chốt strategy chi tiết sau khi Phase 1 hoàn tất.

Không mặc định phải impute toàn bộ.

Có thể có:

```text
historical_clean
```

vẫn chứa `NULL`.

ML imputation có thể nằm downstream.

## Definition of Done

```text
[ ] Canonical schema hoạt động
[ ] Timestamp chuẩn hóa
[ ] Units thống nhất
[ ] Duplicate policy hoạt động
[ ] Invalid records được phát hiện
[ ] Processed output reproducible
[ ] Không phá raw data
```

---

# 10. Phase 5 – Open-Meteo Investigation & Integration

## Mục tiêu

Xác định Open-Meteo **thực sự có giá trị gì** trước khi ingest toàn bộ.

Đây là phase thử nghiệm trước, không phải mặc định scale ngay.

## Step 1 – Station metadata

Xác minh:

```text
station
latitude
longitude
```

cho ít nhất một station.

## Step 2 – API proof-of-concept

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

và unit phù hợp.

## Step 3 – Compare

So sánh:

```text
UCI TEMP ↔ Open-Meteo temperature
UCI DEWP ↔ Open-Meteo dew point
UCI RAIN ↔ Open-Meteo rain
UCI WSPM ↔ Open-Meteo wind
```

Không kỳ vọng bằng nhau tuyệt đối.

Mục tiêu:

- kiểm tra alignment;
- timezone;
- độ hợp lý;
- giá trị enrichment.

## Step 4 – Decision Gate

Một trong ba quyết định:

```text
A. Giữ Open-Meteo đầy đủ
B. Chỉ lấy một số biến enrichment
C. Thay đổi vai trò/nguồn nếu không phù hợp
```

Quyết định phải cập nhật `PROJECT_CONTEXT.md`.

## Candidate enrichment

Ưu tiên kiểm tra:

```text
relative_humidity_2m
```

vì UCI không có humidity trực tiếp.

## Definition of Done

```text
[ ] Station coordinate được xác minh
[ ] API request đúng timezone
[ ] Unit đúng
[ ] Hourly join kiểm tra thành công
[ ] So sánh với UCI weather
[ ] Vai trò Open-Meteo được quyết định
```

---

# 11. Phase 6 – PostgreSQL Staging

## Mục tiêu

Load processed data vào relational staging.

Candidate schema:

```text
staging
```

Candidate tables:

```text
air_quality_hourly
weather_openmeteo_hourly
station_reference
```

## Kiểm tra

Sau load:

```text
source count
vs
target count
```

Kiểm tra:

- duplicates;
- station count;
- date range;
- NULL;
- type.

## Definition of Done

```text
[ ] Processed → PostgreSQL load reproducible
[ ] Row count reconciled
[ ] Key uniqueness kiểm tra
[ ] Schema rõ
[ ] dbt có thể đọc staging
```

---

# 12. Phase 7 – Data Warehouse & dbt

## Mục tiêu

Xây dựng dimensional warehouse phục vụ analytics.

## Bước 1 – Chốt grain

Working grain:

```text
1 station × 1 hour
```

Phải xác nhận lại từ Phase 1.

## Bước 2 – Chốt weather modeling

Quyết định:

```text
one fact
vs
separate weather fact
```

dựa trên dữ liệu thực tế.

## Core models

Candidate:

```text
dim_station
dim_date
dim_time
fact_air_quality_hourly
```

Có thể điều chỉnh.

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
mart_pm25_episodes   # logic + ngưỡng chốt Phase 8; mart nên có trước khi dashboard Phase 11
```

## Definition of Done

```text
[ ] Grain được document
[ ] Dimensions hoạt động
[ ] Fact hoạt động
[ ] dbt tests pass
[ ] Data lineage staging → DWH rõ
[ ] Một số OLAP-style queries chạy đúng
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

## Output

```text
analysis notebook
+
reusable analytical queries
+
candidate insights
+
mart_pm25_episodes (+ tài liệu ngưỡng và định nghĩa episode)
```

## Definition of Done

```text
[ ] Seasonal patterns được hiểu
[ ] Station differences được hiểu
[ ] Weather relationships được kiểm tra
[ ] PM2.5 episodes theo trạm: ngưỡng, độ dài, phân bố mùa/năm được document
[ ] Episode đa-trạm (overlapping / số trạm đồng thời) được phân tích
[ ] Episode gắn tóm tắt weather trong khoảng episode được phân tích
[ ] mart_pm25_episodes (hoặc tương đương) dùng được từ SQL
[ ] Data issues mới được document
[ ] Candidate ML features được xác định
```

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

Xây station profiles.

Ví dụ:

```text
mean_pm25
median_pm25
pm25_std
mean_pm10
mean_no2
mean_o3
high_pollution_ratio
seasonal indicators
...
```

Sau đó:

```text
standardize
↓
cluster
↓
evaluate
↓
interpret
```

## Evaluation

Có thể sử dụng:

```text
silhouette score
elbow method
cluster interpretability
```

Không chọn số cluster chỉ dựa vào một metric.

## Output

- station cluster assignment;
- cluster profile;
- visualization;
- interpretation.

---

# 16. Phase 10 – PM2.5 Forecasting

## Mục tiêu

Xây dựng mô hình dự báo PM2.5.

## Target ban đầu

```text
PM2.5(t+1h)
```

## Bước 1 – Baseline

Persistence:

```text
prediction(t+1)
=
PM2.5(t)
```

Machine Learning phải đánh bại baseline hoặc ít nhất giải thích được vì sao không.

## Bước 2 – Feature engineering

Candidate:

```text
station
hour
day_of_week
month
season

PM2.5 lags
weather
pollutant lags
rolling statistics
```

Chỉ dùng feature hợp lệ tại prediction time.

## Bước 3 – Split

Chronological:

```text
Train
↓
Validation
↓
Test
```

Không random split.

## Bước 4 – Models

Bắt đầu:

```text
Linear Regression
```

Sau đó:

```text
Random Forest
Gradient Boosting
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

## Definition of Done

```text
[ ] Baseline tồn tại
[ ] No leakage
[ ] Split đúng thời gian
[ ] Feature pipeline reproducible
[ ] ≥2 model được so sánh hợp lý
[ ] Test result được ghi lại
[ ] Error analysis được thực hiện
```

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

Tạo giao diện trực quan để khám phá kết quả của hệ thống.

Công nghệ:

```text
Streamlit
+
Plotly
```

## Minimum Viable Dashboard

### Overview

- KPI;
- pollutant trends;
- station selector;
- date filter.

### Station Analysis

- comparison;
- ranking;
- cluster.

### Pollution Episodes

- độ dài / số episode theo trạm;
- phân bố theo thời gian;
- mức độ đồng thời nhiều trạm;
- weather trung bình trong episode — đọc từ `mart_pm25_episodes`.

### Weather Analysis

- relationship với PM2.5;
- filter;
- scatter/time-series.

### Prediction

- actual vs predicted;
- error;
- model metrics;
- station/date selection.

## Map

Chỉ thêm khi station coordinates đã được xác minh.

## Definition of Done

```text
[ ] Dashboard đọc DWH/marts
[ ] Filter hoạt động
[ ] Charts rõ
[ ] Clustering hiển thị
[ ] Pollution episodes hiển thị (từ mart)
[ ] Prediction hiển thị
[ ] Không đọc trực tiếp CSV raw cho kết quả chính
```

---

# 19. Phase 12 – Integration & Hardening

## Mục tiêu

Biến các module rời thành một project hoàn chỉnh.

Kiểm tra end-to-end:

```text
source
↓
lake
↓
processing
↓
staging
↓
DWH
↓
mining
↓
dashboard
```

## Kiểm tra

- fresh environment setup;
- rerun pipeline;
- duplicate;
- broken dependency;
- config;
- logging;
- dbt tests;
- model artifact;
- dashboard query.

## Cleanup

Xóa:

- hard-coded path;
- notebook-only logic cần productionize;
- duplicated code;
- password trong repo;
- unused experiments.

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