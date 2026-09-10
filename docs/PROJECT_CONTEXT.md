# PROJECT_CONTEXT.md

> **Project:** Phân tích và dự báo ô nhiễm không khí theo khu vực và điều kiện thời tiết  
> **Môn học:** Kho dữ liệu và Khai phá dữ liệu  
> **Quy mô nhóm:** 2 thành viên  
> **Trạng thái:** Chuẩn bị triển khai  
> **Phiên bản tài liệu:** 1.0  
> **Cập nhật:** 11/09/2026

---

# 1. Mục đích của tài liệu

`PROJECT_CONTEXT.md` là tài liệu ngữ cảnh trung tâm của toàn bộ dự án.

Tài liệu này **không phải báo cáo nộp giảng viên**. Nó được sử dụng để:

- giúp hai thành viên nắm thống nhất mục tiêu và kiến trúc;
- giúp các phiên ChatGPT/AI sau hiểu dự án trước khi tiếp tục triển khai;
- tránh thay đổi scope hoặc công nghệ một cách vô tình;
- lưu lại các quyết định quan trọng;
- phân biệt rõ nội dung đã chốt và nội dung còn cần kiểm chứng;
- làm cơ sở xây dựng các tài liệu chi tiết tiếp theo.

Mọi phiên làm việc mới liên quan tới dự án nên đọc:

1. `PROJECT_CONTEXT.md`;
2. `PROGRESS.md` nếu dự án đã bắt đầu triển khai;
3. tài liệu chuyên biệt của phase đang thực hiện.

---

# 2. Chủ đề

## Phân tích và dự báo ô nhiễm không khí theo khu vực và điều kiện thời tiết

Dự án xây dựng một quy trình dữ liệu tương đối hoàn chỉnh, từ thu thập dữ liệu nhiều nguồn đến lưu trữ, xây dựng kho dữ liệu, phân tích, khai phá dữ liệu, dự báo và trực quan hóa.

Trọng tâm của dự án là tìm hiểu:

- ô nhiễm thay đổi như thế nào theo thời gian;
- mức ô nhiễm khác nhau như thế nào giữa các trạm/khu vực;
- các điều kiện khí tượng liên quan như thế nào tới mức ô nhiễm;
- các trạm có thể được phân thành những nhóm đặc trưng nào;
- dữ liệu lịch sử và điều kiện khí tượng có thể được sử dụng để dự báo PM2.5 như thế nào.

---

# 3. Cách hiểu phạm vi “khu vực”

Trong phiên bản hiện tại, **khu vực được hiểu chủ yếu theo trạm quan trắc (monitoring site/station)**.

Dataset chính có 12 trạm quan trắc tại Bắc Kinh.

Không mặc định rằng mỗi trạm tương ứng chính xác với một quận/huyện hoặc một khu vực hành chính.

Nếu dự án muốn:

- hiển thị bản đồ;
- phân tích theo district;
- bổ sung tọa độ;
- gán trạm vào khu vực hành chính;

thì metadata địa lý phải được bổ sung từ nguồn đáng tin cậy và kiểm chứng riêng.

Không tự suy diễn vị trí hành chính chỉ từ tên trạm.

---

# 4. Mục tiêu tổng thể

Dự án cần thể hiện được một pipeline dữ liệu end-to-end:

```text
Data Sources
     ↓
Data Ingestion
     ↓
Data Lake
     ↓
Validation / Processing
     ↓
Staging
     ↓
Data Warehouse
     ↓
Analytics / Data Mining
     ↓
Prediction
     ↓
Web Dashboard
```

Trọng tâm không phải là sử dụng càng nhiều công nghệ càng tốt.

Một hệ thống được xem là tốt khi:

- pipeline có lý do;
- dữ liệu được quản lý rõ;
- Data Lake và Data Warehouse có vai trò khác nhau;
- ETL có thể tái thực hiện;
- mô hình dữ liệu phục vụ được phân tích;
- mining giải quyết câu hỏi cụ thể;
- dự báo được đánh giá đúng;
- dashboard giúp giải thích được kết quả.

---

# 5. Các câu hỏi chính của dự án

Dự án hướng tới trả lời các nhóm câu hỏi sau.

## 5.1. Phân tích theo thời gian

- PM2.5, PM10, SO₂, NO₂, CO và O₃ thay đổi như thế nào theo năm, mùa, tháng, ngày và giờ?
- Có những khung giờ hoặc thời điểm thường xuyên xuất hiện mức ô nhiễm cao hay không?
- Có tính mùa vụ rõ ràng hay không?
- Các đợt ô nhiễm cao thường kéo dài bao lâu?

## 5.2. Phân tích theo trạm/khu vực

- Mức ô nhiễm giữa các trạm khác nhau như thế nào?
- Trạm nào thường xuyên có nồng độ ô nhiễm cao?
- Các trạm có cùng xu hướng biến động hay không?
- Có thể phân nhóm các trạm dựa trên đặc điểm ô nhiễm hay không?

## 5.3. Phân tích yếu tố khí tượng

Tìm hiểu mối quan hệ giữa ô nhiễm và:

- nhiệt độ;
- độ ẩm;
- điểm sương;
- áp suất;
- lượng mưa;
- tốc độ gió;
- hướng gió;
- các yếu tố khí tượng bổ sung nếu thực sự hữu ích.

Không mặc định trước rằng một yếu tố **gây ra** ô nhiễm.

Phân tích dữ liệu quan sát trước hết cho phép xác định **mối liên hệ/correlation/pattern**, không tự động chứng minh quan hệ nhân quả.

## 5.4. Dự báo

Câu hỏi chính:

> Có thể dự báo PM2.5 của một trạm dựa trên dữ liệu lịch sử, thời gian và điều kiện khí tượng hay không?

---

# 6. Phạm vi chất ô nhiễm

Dataset chứa:

```text
PM2.5
PM10
SO2
NO2
CO
O3
```

## Phân tích

Cả 6 chất được giữ trong Data Warehouse và được sử dụng cho:

- EDA;
- dashboard;
- phân tích xu hướng;
- so sánh giữa các trạm;
- clustering;
- tìm mối quan hệ giữa các biến.

## Dự báo

**PM2.5 là target dự báo chính.**

Không xây sáu pipeline Machine Learning giống nhau cho sáu chất chỉ để tăng số lượng mô hình.

Lý do:

- nhóm chỉ có 2 thành viên;
- phần lớn quy trình sẽ bị lặp;
- PM2.5 là một chỉ số phù hợp để tập trung nghiên cứu;
- thời gian nên ưu tiên cho data pipeline, DWH, feature engineering và đánh giá model.

Sau khi pipeline PM2.5 hoàn chỉnh, nhóm có thể chủ động đề xuất thử nghiệm thêm PM10 hoặc chất khác nếu việc mở rộng có giá trị rõ ràng.

---

# 7. Định nghĩa bài toán dự báo

Cần phân biệt:

```text
Ước lượng PM2.5 tại thời điểm t
≠
Dự báo PM2.5 trong tương lai
```

Nếu sử dụng weather tại thời điểm `t` để dự đoán PM2.5 cũng tại `t`, đó chủ yếu là bài toán regression/estimation.

Để đúng với tên **dự báo**, hướng làm mặc định của dự án là:

> **Dự báo PM2.5 ở thời điểm kế tiếp dựa trên thông tin đã có trước thời điểm dự báo.**

### Working target ban đầu

```text
PM2.5(t + 1 giờ)
```

Đây là working hypothesis, chưa phải quyết định bất biến.

Sau EDA có thể đánh giá thêm:

```text
t + 3 giờ
t + 6 giờ
t + 24 giờ
```

nhưng chỉ mở rộng nếu hợp lý.

Không biến bài thành dự báo nhiều horizon nếu điều đó chỉ tăng khối lượng mà không tăng giá trị.

---

# 8. Nguyên tắc chống Data Leakage

Đây là nguyên tắc bắt buộc của phần Machine Learning.

Không được sử dụng một feature nếu trong tình huống dự báo thực tế feature đó **chưa tồn tại tại thời điểm prediction**.

Ví dụ khi dự báo:

```text
PM2.5(t+1)
```

có thể sử dụng:

```text
PM2.5(t)
PM2.5(t-1)
weather(t)
time features
station
historical rolling features
```

nhưng không được vô tình sử dụng:

```text
PM2.5(t+1)
hoặc dữ liệu tương lai chưa biết
```

Nếu sử dụng điều kiện thời tiết tương lai, phải giải thích rằng dữ liệu đó sẽ đến từ **weather forecast**, không phải observed weather mà hệ thống thực tế không thể biết trước.

---

# 9. Nguồn dữ liệu chính

## 9.1. Beijing Multi-Site Air Quality

Nguồn chính:

**UCI Machine Learning Repository – Beijing Multi-Site Air Quality**

Thông tin chính:

- 420.768 observations;
- dữ liệu theo giờ;
- 12 trạm;
- từ 01/03/2013 đến 28/02/2017;
- 6 chất ô nhiễm;
- 6 biến khí tượng;
- có missing values.

Dữ liệu chất lượng không khí gốc đến từ hệ thống quan trắc môi trường Bắc Kinh.

Dữ liệu khí tượng trong dataset đã được ghép với các trạm khí tượng gần các điểm quan trắc.

---

# 10. Cấu trúc dữ liệu UCI

Các trường chính:

## Thời gian

```text
year
month
day
hour
```

Khi ingest sẽ được ghép thành một trường timestamp thống nhất.

## Ô nhiễm

```text
PM2.5
PM10
SO2
NO2
CO
O3
```

## Khí tượng

```text
TEMP   - Temperature
PRES   - Pressure
DEWP   - Dew point
RAIN   - Rainfall
wd     - Wind direction
WSPM   - Wind speed
```

## Metadata

```text
station
No
```

`No` là số thứ tự dòng trong dữ liệu nguồn.

Không sử dụng `No` làm feature Machine Learning hoặc business key của Data Warehouse.

---

# 11. Kết quả kiểm tra file dữ liệu thật

Một file thực tế đã được kiểm tra:

```text
PRSA_Data_Wanshouxigong_20130301-20170228.csv
```

Kết quả:

- 35.064 dòng;
- 18 cột;
- một trạm duy nhất: `Wanshouxigong`;
- từ `2013-03-01 00:00` đến `2017-02-28 23:00`;
- không có timestamp trùng;
- đủ 35.064 timestamp theo giờ trong khoảng thời gian của file;
- pollutant có missing values;
- weather có ít missing hơn nhưng vẫn tồn tại;
- có những giá trị nồng độ rất cao cần kiểm tra kỹ.

Ví dụ missing trong file đã kiểm tra:

```text
PM2.5 : 696
PM10  : 484
SO2   : 669
NO2   : 754
CO    : 1297
O3    : 1078
```

Weather cũng có missing nhưng ít hơn.

### Kết luận

Không thể dùng chiến lược:

```text
df.dropna()
```

cho toàn bộ pipeline mà không đánh giá ảnh hưởng.

Việc xử lý missing phải được thiết kế trong `DATA_GUIDE.md`.

---

# 12. Quy tắc xử lý missing data

Không mặc định:

```text
missing → interpolate
```

Trước tiên cần xác định:

- missing ở biến nào;
- tỷ lệ missing;
- missing đơn lẻ hay liên tục;
- độ dài gap;
- có cùng thời điểm missing ở nhiều trạm hay không;
- có thể suy ra từ nguồn khác hay không.

Có thể áp dụng chiến lược khác nhau cho:

```text
gap ngắn
gap trung bình
gap dài
```

Ví dụ interpolation có thể phù hợp với gap ngắn nhưng không nhất thiết hợp lý với gap kéo dài hàng chục giờ.

Chiến lược chính thức chỉ được chốt sau profiling toàn bộ 12 trạm.

---

# 13. Quy tắc xử lý outlier/extreme values

Không tự động coi một giá trị rất cao là dữ liệu lỗi.

File đã kiểm tra có những giá trị cực đại như:

```text
PM2.5 = 999
PM10  = 961
CO    = 9800
```

Các giá trị như vậy có thể:

- là sự kiện ô nhiễm thực;
- là measurement bất thường;
- hoặc là lỗi dữ liệu.

Trước khi loại bỏ phải kiểm tra:

- các giờ trước và sau;
- pollutant khác cùng thời điểm;
- các trạm khác;
- điều kiện khí tượng;
- distribution;
- tài liệu dataset nếu cần.

Không áp dụng rule tùy ý kiểu:

```text
PM2.5 > 500 → delete
```

chỉ vì giá trị có vẻ lớn.

---

# 14. Nguồn khí tượng bổ sung

Nguồn dự kiến:

**Open-Meteo Historical Weather API**

Dạng nguồn:

```text
REST API
↓
JSON
```

Có thể cung cấp:

- temperature;
- relative humidity;
- dew point;
- precipitation;
- pressure;
- wind speed;
- wind direction;
- cloud-related variables;
- các biến phù hợp khác.

---

# 15. Vai trò của Open-Meteo

UCI **đã có weather**.

Vì vậy Open-Meteo không được thêm chỉ để có thêm một API.

Vai trò dự kiến của Open-Meteo:

1. tạo pipeline ingestion từ REST API/JSON;
2. thể hiện khả năng tích hợp đa nguồn;
3. bổ sung biến UCI không có hoặc không trực tiếp có, ví dụ relative humidity;
4. kiểm tra/đối chiếu một phần dữ liệu weather;
5. cung cấp thêm weather feature nếu kết quả EDA chứng minh có ích.

### Không bắt buộc giữ bằng mọi giá

Sau khi khảo sát, nếu Open-Meteo:

- không cải thiện dữ liệu;
- gây khó khăn lớn về spatial matching;
- tạo duplicated information;
- hoặc không đem lại giá trị cho dự án;

AI và nhóm được quyền chủ động đề xuất:

- giảm số biến lấy;
- thay vai trò của nguồn này;
- dùng nó chỉ để enrichment;
- hoặc thay bằng một nguồn phù hợp hơn.

Không được cố giữ một công nghệ hoặc nguồn dữ liệu chỉ vì nó đã xuất hiện trong proposal ban đầu.

---

# 16. Metadata trạm

Dataset hiện có tên trạm nhưng không có đầy đủ metadata địa lý cần cho visualization theo bản đồ.

Dự án dự kiến xây dựng một reference dataset:

```text
station_id
station_name
latitude
longitude
district (nếu xác minh được)
other_metadata
```

Nguồn tọa độ và district phải được kiểm chứng.

Reference data này có thể được quản lý dưới dạng CSV/seed và ingest vào hệ thống.

Không tự tạo tọa độ giả hoặc gán district theo suy đoán.

---

# 17. Kiến trúc tổng thể

Kiến trúc định hướng:

```text
┌───────────────────────────────┐
│         DATA SOURCES          │
│                               │
│  UCI CSV     Open-Meteo API   │
│      + Station Metadata       │
└───────────────┬───────────────┘
                │
                ▼
       ┌─────────────────┐
       │ Apache Airflow  │
       │  Orchestration  │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │      MinIO      │
       │    Data Lake    │
       └────────┬────────┘
                │
          Validation /
          Standardization
                │
                ▼
       ┌─────────────────┐
       │ PostgreSQL      │
       │ Staging Layer   │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │       dbt       │
       │ Transformation  │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ PostgreSQL DWH  │
       │ Dimensional     │
       │ Model + Marts   │
       └───────┬─┬───────┘
               │ │
        ┌──────┘ └──────┐
        ▼               ▼
 Data Mining       Web Dashboard
 Scikit-learn      Streamlit/Plotly
```

---

# 18. Vai trò Data Lake

Công nghệ:

**MinIO**

MinIO đóng vai trò object storage cho Data Lake.

Data Lake không được sử dụng chỉ để “có Data Lake trong sơ đồ”.

Nó phải giúp:

- giữ bản gốc của dữ liệu;
- tách dữ liệu nguồn khỏi dữ liệu đã transform;
- cho phép rerun pipeline;
- lưu dữ liệu từ nhiều định dạng;
- tạo traceability từ source đến warehouse.

Cấu trúc ban đầu có thể theo hướng:

```text
raw/
    uci/
    openmeteo/
    reference/

processed/
    air_quality/
    weather/
```

Ưu tiên:

- CSV/JSON ở Raw;
- Parquet ở Processed nếu hợp lý.

Không cần tạo ba hoặc bốn zone giống hệ thống enterprise nếu không giải quyết vấn đề thực tế.

---

# 19. Vai trò Apache Airflow

Airflow chịu trách nhiệm **orchestration**, không phải thay thế toàn bộ processing logic.

Airflow dự kiến điều phối:

```text
ingest UCI
      ↓
ingest weather API
      ↓
validate raw data
      ↓
process/standardize
      ↓
load PostgreSQL staging
      ↓
run dbt
      ↓
data quality checks
```

Pipeline phải cố gắng:

- reproducible;
- idempotent;
- có logging;
- xử lý failure rõ;
- có dependency hợp lý.

Không cần tạo nhiều DAG chỉ để làm hệ thống trông phức tạp.

---

# 20. Vai trò Python/Pandas

Python/Pandas dùng cho:

- đọc source data;
- gọi API;
- parsing;
- schema validation;
- cleaning;
- timestamp normalization;
- missing-value processing;
- standardization;
- chuyển đổi format;
- feature preprocessing khi cần.

Business logic quan trọng phải nằm trong code/module rõ ràng, không nhét toàn bộ vào một notebook duy nhất.

Notebook có thể dùng cho:

- EDA;
- thử nghiệm;
- model research.

Pipeline production-like nên nằm trong source code tái sử dụng được.

---

# 21. Vai trò PostgreSQL

PostgreSQL là nền tảng chứa:

```text
Staging
+
Data Warehouse
+
Analytical marts
```

PostgreSQL không chỉ là chỗ:

> import CSV rồi query.

Kho dữ liệu phải phục vụ:

- lịch sử;
- aggregation;
- filtering;
- dimensional analysis;
- dashboard;
- mining;
- reproducible analytics.

Các schema logic dự kiến:

```text
staging
dwh
mart
```

Tên cuối cùng có thể thay đổi khi triển khai.

---

# 22. Vai trò dbt

dbt chủ yếu xử lý transformation **sau khi dữ liệu đã được đưa vào PostgreSQL staging**.

Hướng luồng đúng:

```text
MinIO
  ↓
Python/Airflow
  ↓
PostgreSQL staging
  ↓
dbt
  ↓
DWH / marts
```

dbt dự kiến dùng cho:

- cleaning logic phù hợp với SQL;
- transformation;
- dimensional modeling;
- fact/dimension models;
- analytical marts;
- tests;
- lineage/dependencies;
- documentation.

Không cố dùng dbt để xử lý mọi loại dữ liệu nếu Python phù hợp hơn.

---

# 23. Data Warehouse – grain

Grain mặc định dự kiến:

> **Một bản ghi đại diện cho dữ liệu của một trạm tại một giờ.**

Tức:

```text
station
+
datetime/hour
```

là đơn vị quan sát cốt lõi.

Grain phải được xác nhận sau khi kiểm tra toàn bộ dataset.

Không thiết kế Fact table cuối cùng trước khi grain được xác minh.

---

# 24. Data Warehouse – mô hình dự kiến

Thiết kế ưu tiên dimensional modeling.

Một cấu trúc ban đầu có thể gồm:

```text
DimDate
DimTime
DimStation

FactAirQuality
```

Weather có thể:

- nằm trong `FactAirQuality`;
- hoặc có một Fact/structure riêng;

tùy grain và cách phân tích sau khi khảo sát dữ liệu.

Không tạo `DimWeather` chỉ vì “weather là một chiều”.

Việc một thuộc tính nên là:

```text
dimension
fact
measure
attribute
```

phải dựa trên semantics và grain.

Schema cuối cùng sẽ được thiết kế trong tài liệu DWH riêng.

---

# 25. Clustering

Clustering dùng để trả lời:

> Các trạm/khu vực có đặc điểm ô nhiễm tương đồng như thế nào?

Không clustering trực tiếp từng row theo giờ rồi kết luận “các trạm giống nhau” nếu feature không phản ánh đặc trưng của trạm.

Có thể xây profile cho từng trạm dựa trên:

- mean/median pollutant;
- variability;
- seasonal pattern;
- tỷ lệ giờ ô nhiễm cao;
- pollutant composition;
- các đặc trưng phù hợp khác.

K-Means là ứng viên ban đầu, **không phải thuật toán bắt buộc**.

Có thể so sánh phương pháp khác nếu EDA cho thấy cần thiết.

---

# 26. Dự báo PM2.5

Target chính:

```text
PM2.5
```

Working forecast horizon:

```text
t + 1 hour
```

Model nên bắt đầu bằng **baseline đơn giản**.

Ví dụ:

```text
PM2.5(t+1) ≈ PM2.5(t)
```

Sau đó mới so sánh với Machine Learning.

Các nhóm feature có thể gồm:

```text
time features
station
weather
PM2.5 lags
rolling statistics
other pollutant lags nếu hợp lệ
```

Không sử dụng feature chỉ vì làm metric đẹp hơn nếu feature không có sẵn tại prediction time.

---

# 27. Machine Learning strategy

Ưu tiên các mô hình vừa sức và giải thích được.

Ứng viên:

```text
Linear Regression
Random Forest
Gradient Boosting
HistGradientBoosting / XGBoost nếu thực sự cần
```

Deep Learning không phải yêu cầu.

Không thêm LSTM/Transformer chỉ vì dữ liệu là time-series.

### Evaluation

Ưu tiên:

```text
MAE  - metric chính
RMSE - metric bổ sung
R²   - metric mô tả
```

Phải so sánh với baseline.

---

# 28. Train / Validation / Test

Không random split dữ liệu time-series theo cách thông thường.

Ưu tiên chronological split:

```text
Past
│
├── Train
├── Validation
└── Test
             → Future
```

Có thể dùng rolling/time-series validation nếu cần.

Không để dữ liệu tương lai đi vào train thông qua:

- random split;
- rolling feature sai cách;
- interpolation xuyên qua train/test boundary;
- normalization fit trên toàn dataset.

---

# 29. Open-Meteo và forecast model

Cần phân biệt:

```text
Historical Weather
```

và

```text
Weather Forecast
```

Open-Meteo Historical API dùng để:

- enrichment;
- historical analysis;
- training/validation nếu feature hợp lệ.

Nếu sau này demo prediction tương lai thực sự cần weather trong tương lai, có thể đề xuất sử dụng weather forecast API.

Đây là extension tự nhiên, nhưng **không phải yêu cầu bắt buộc của phiên bản đầu**.

---

# 30. Web Dashboard

Công nghệ:

```text
Streamlit
+
Plotly
```

Dashboard không chỉ để trang trí.

Nó phải giúp người dùng khám phá kết quả của Data Warehouse và Data Mining.

Các trang/view dự kiến:

### Overview

- KPI tổng quan;
- mức ô nhiễm theo thời gian;
- pollutant chính;
- lựa chọn trạm.

### Temporal Analysis

- năm/tháng/ngày/giờ;
- seasonality;
- pollution peaks.

### Station Analysis

- so sánh 12 trạm;
- clustering;
- ranking;
- profile của từng trạm.

### Weather & Pollution

- quan hệ pollutant ↔ weather;
- filter theo điều kiện;
- correlation/pattern.

### Prediction

- giá trị thật;
- giá trị dự báo;
- error;
- model comparison;
- feature importance nếu phù hợp.

Map có thể được thêm khi station coordinates đã được xác minh.

---

# 31. Tech stack hiện tại

| Thành phần | Công nghệ |
|---|---|
| Hệ điều hành | Windows |
| Container | Docker Desktop / Docker Compose |
| Ngôn ngữ | Python |
| Orchestration | Apache Airflow |
| Data Lake | MinIO |
| Processing | Pandas |
| Data Warehouse | PostgreSQL |
| Transformation | dbt |
| Mining / ML | Scikit-learn |
| Dashboard | Streamlit |
| Visualization | Plotly |
| Version control | Git |

Ưu tiên công nghệ **open-source** và có khả năng tùy chỉnh.

---

# 32. Nguyên tắc Docker

Ưu tiên container hóa:

```text
Airflow
MinIO
PostgreSQL
```

dbt có thể:

- chạy local;
- hoặc chạy container;

tùy workflow thuận tiện nhất.

Source code, config và Docker Compose phải giúp một thành viên khác dựng lại môi trường mà không cần cấu hình thủ công quá nhiều.

Không hard-code:

- password;
- API secret;
- machine-specific path;

trong source code.

Sử dụng `.env` khi phù hợp.

---

# 33. Scope bắt buộc

Phiên bản chính của dự án bao gồm:

- ingestion dữ liệu CSV;
- ingestion REST API/JSON;
- Data Lake;
- ETL/ELT;
- data quality;
- PostgreSQL staging;
- Data Warehouse;
- dimensional model;
- dbt transformation;
- phân tích lịch sử;
- phân tích theo trạm;
- phân tích weather ↔ pollution;
- clustering;
- dự báo PM2.5;
- model evaluation;
- Web Dashboard.

---

# 34. Không thuộc scope chính

Không bắt buộc:

- GIS chuyên sâu;
- mô hình phát tán ô nhiễm;
- dự báo phạm vi lan truyền;
- Kriging;
- spatial interpolation phức tạp;
- streaming real-time;
- Kafka;
- hệ thống IoT;
- Hadoop;
- Spark;
- Kubernetes;
- microservices;
- Deep Learning;
- prediction riêng cho tất cả 6 pollutants;
- cloud production deployment.

Không được tự động thêm các công nghệ trên chỉ để kiến trúc trông “enterprise”.

---

# 35. Quy tắc mở rộng dự án

Scope không bị khóa cứng một cách máy móc.

AI và nhóm được **chủ động đề xuất cải tiến** nếu phát hiện:

- dataset tốt hơn;
- công nghệ phù hợp hơn;
- vấn đề thiết kế;
- feature hữu ích;
- visualization có giá trị;
- data-quality issue;
- một extension có thể tăng đáng kể chất lượng bài.

Đề xuất nên trình bày:

```text
Đề xuất
↓
Lý do
↓
Lợi ích
↓
Chi phí / độ khó
↓
Ảnh hưởng scope
↓
Khuyến nghị
```

Các thay đổi lớn phải được thống nhất trước khi áp dụng.

Các cải tiến nhỏ ở mức implementation có thể được thực hiện chủ động.

---

# 36. Quy tắc cho AI / các phiên chat sau

AI phải:

1. đọc `PROJECT_CONTEXT.md`;
2. đọc `PROGRESS.md` nếu tồn tại;
3. xác định phase hiện tại;
4. không hỏi lại những thông tin đã được tài liệu xác nhận;
5. không tự mở rộng scope lớn;
6. chủ động chỉ ra thiết kế chưa tốt;
7. ưu tiên giải pháp vừa sức nhóm 2 người;
8. phân biệt rõ “đã kiểm chứng” và “giả định”;
9. không bịa dữ liệu, schema hoặc kết quả model;
10. cập nhật tài liệu khi một quyết định dài hạn thay đổi.

AI **không được cứng nhắc** chỉ vì context đã ghi một công nghệ.

Nếu có phương án tốt hơn, phải đề xuất.

---

# 37. Quy tắc quyết định kỹ thuật

Ưu tiên theo thứ tự:

```text
Correctness
↓
Data quality
↓
Reproducibility
↓
Clarity
↓
Maintainability
↓
Performance
↓
Extra complexity
```

Với dataset cỡ hiện tại, không thêm distributed processing nếu PostgreSQL/Pandas xử lý tốt.

---

# 38. Quy tắc thiết kế dành cho nhóm 2 người

Kiến trúc phải đủ lớn để thể hiện nội dung môn học nhưng đủ nhỏ để hai người hoàn thành.

Không để một thành viên chỉ làm:

```text
slides/report
```

trong khi người kia làm toàn bộ hệ thống.

Cả hai phải hiểu:

- data flow;
- Data Lake;
- DWH;
- mining;
- dashboard.

Phân chia module cụ thể sẽ được thực hiện sau khi `IMPLEMENTATION_PLAN.md` được xây dựng.

---

# 39. Definition of Done

Dự án chưa được xem là hoàn thành chỉ vì model đã train được.

Phiên bản hoàn chỉnh phải có khả năng demo:

```text
Raw CSV/API
      ↓
Airflow ingestion
      ↓
MinIO Data Lake
      ↓
Processing
      ↓
PostgreSQL staging
      ↓
dbt
      ↓
Dimensional Warehouse
      ↓
Analysis / Mining
      ↓
Prediction
      ↓
Interactive Dashboard
```

Và nhóm phải giải thích được:

- dữ liệu từ đâu;
- tại sao dùng nguồn đó;
- raw data được giữ ở đâu;
- dữ liệu được clean như thế nào;
- warehouse có grain gì;
- Fact/Dimension được thiết kế vì sao;
- clustering mang lại insight gì;
- model dự báo gì;
- model có tốt hơn baseline không;
- có leakage hay không;
- dashboard sử dụng dữ liệu nào;
- hạn chế của hệ thống là gì.

---

# 40. Tiêu chí ưu tiên

Nếu phải lựa chọn giữa:

```text
10 công nghệ nhưng mỗi thứ làm sơ sài
```

và:

```text
6 công nghệ nhưng pipeline hoàn chỉnh,
có test, có giải thích và demo tốt
```

luôn chọn phương án thứ hai.

Ưu tiên dự án theo thứ tự:

```text
Data đúng
↓
Pipeline đúng
↓
Warehouse đúng
↓
Phân tích có ý nghĩa
↓
Mining đúng phương pháp
↓
Prediction đáng tin cậy
↓
Dashboard rõ và đẹp
↓
Extension
```

---

# 41. Rủi ro đã biết

## Missing data

Dataset có missing thực tế.

Cần profiling trước khi quyết định imputation.

## Extreme pollution values

Không được xóa tự động.

Cần kiểm chứng.

## Open-Meteo duplication

Weather của UCI và Open-Meteo có thể bị trùng về thông tin.

Cần chứng minh giá trị của enrichment.

## Station location

UCI không cung cấp trực tiếp toàn bộ metadata địa lý cần cho mapping.

Cần nguồn bổ sung.

## Data leakage

Rủi ro lớn khi tạo lag, rolling features và split time-series.

## Scope creep

Dự án có nhiều thành phần nên dễ thêm công nghệ không cần thiết.

Cần ưu tiên core pipeline.

---

# 42. Các vấn đề chưa chốt

Các vấn đề sau cố tình để mở cho tới khi có đủ dữ liệu.

### Data

- profiling toàn bộ 12 trạm;
- missing strategy;
- outlier strategy;
- station coordinates;
- timezone;
- API weather variables cuối cùng;
- role cuối cùng của Open-Meteo.

### Lake

- bucket/prefix convention;
- format processed;
- retention của processed data.

### Warehouse

- Fact schema cuối;
- date/time dimension design;
- weather modeling;
- marts;
- indexes;
- materialized views nếu cần.

### Mining

- forecast horizon cuối;
- lag window;
- rolling window;
- global model hay per-station model;
- clustering features;
- algorithm cuối;
- hyperparameter tuning strategy.

### Dashboard

- UI structure;
- map;
- prediction interaction;
- mức độ live/demo.

Các quyết định này phải dựa trên kết quả thực nghiệm, không chốt theo cảm tính.

---

# 43. Working assumptions hiện tại

Cho tới khi có bằng chứng khác:

- một observation tương ứng một station-hour;
- PM2.5 là prediction target chính;
- forecast ban đầu là `t+1 hour`;
- sử dụng một **global model** cho nhiều trạm là hướng ưu tiên khảo sát trước;
- station sẽ được đưa vào feature/model một cách phù hợp;
- chronological split được ưu tiên;
- MAE là metric chính;
- persistence model là baseline;
- MinIO giữ raw source;
- PostgreSQL chứa staging + DWH;
- dbt transform staging → DWH/marts;
- dashboard đọc primarily từ warehouse/marts, không đọc trực tiếp raw CSV.

Mọi assumption có thể thay đổi nếu kết quả thực tế chứng minh phương án khác tốt hơn.

---

# 44. Các tài liệu nội bộ tiếp theo

Cấu trúc tài liệu dự kiến:

```text
docs/
│
├── PROJECT_CONTEXT.md
├── DATA_GUIDE.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── IMPLEMENTATION_GUIDE.md
└── PROGRESS.md
```

Không bắt buộc tạo tất cả cùng lúc.

## Thứ tự khuyến nghị

```text
PROJECT_CONTEXT.md
        ↓
DATA_GUIDIDE / Data profiling
        ↓
ARCHITECTURE.md
        ↓
IMPLEMENTATION_PLAN.md
        ↓
Environment setup
        ↓
Implementation
        ↓
PROGRESS.md cập nhật liên tục
```

---

# 45. PROGRESS.md

Sau khi bắt đầu triển khai thật, mỗi milestone nên cập nhật:

```text
Date:
Phase:
Completed:
Evidence / Result:
Decisions:
Problems:
Next steps:
```

Nếu một quyết định ảnh hưởng lâu dài đến:

- scope;
- architecture;
- dataset;
- target;
- technology;

thì ngoài `PROGRESS.md` phải cập nhật lại `PROJECT_CONTEXT.md`.

---

# 46. Source of Truth hierarchy

Nếu các tài liệu mâu thuẫn:

```text
Quyết định mới đã được xác nhận
        ↓
PROJECT_CONTEXT.md
        ↓
PROGRESS.md
        ↓
Tài liệu phase hiện tại
        ↓
Code / notebook cũ
        ↓
Chat cũ
```

Không sử dụng một đoạn chat cũ để ghi đè lên quyết định mới đã được cập nhật trong tài liệu.

---

# 47. Nguyên tắc cuối

Dự án này không nhằm xây dựng một nền tảng giám sát chất lượng không khí production-scale.

Mục tiêu là tạo một bài tập lớn có chiều sâu và có thể giải thích xuyên suốt:

> **Từ dữ liệu thô → tích hợp đa nguồn → Data Lake → Data Warehouse → phân tích → khai phá → dự báo → trực quan hóa.**

Không đánh đổi tính đúng đắn để chạy theo số lượng công nghệ.

Không đánh đổi khả năng hoàn thành để chạy theo một scope quá lớn.

Nhưng cũng không làm pipeline tối giản đến mức mất đi giá trị của môn **Kho dữ liệu và Khai phá dữ liệu**.

Mục tiêu cuối cùng:

> **Một hệ thống vừa sức nhóm 2 người, kiến trúc rõ ràng, dữ liệu được xử lý nghiêm túc, mining có ý nghĩa và demo đủ thuyết phục.**