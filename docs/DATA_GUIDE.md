# DATA_GUIDE.md

> **Project:** Phân tích và dự báo ô nhiễm không khí theo khu vực và điều kiện thời tiết  
> **Vai trò tài liệu:** Quy chuẩn dữ liệu của dự án  
> **Phiên bản:** 1.1  
> **Cập nhật:** 15/09/2026
>
> `PROJECT_CONTEXT.md` quyết định **dự án đang làm gì**.  
> `DATA_GUIDE.md` quyết định **dữ liệu phải được hiểu và xử lý như thế nào**.

---

# 1. Mục đích

Tài liệu này quy định:

- nguồn dữ liệu;
- schema nguồn;
- cách hiểu từng biến;
- naming convention;
- đơn vị;
- timestamp;
- station;
- missing values;
- duplicates;
- extreme values;
- validation;
- cách tích hợp UCI với Open-Meteo;
- cách lưu dữ liệu trong Data Lake;
- các nguyên tắc trước khi đưa dữ liệu vào Data Warehouse và Machine Learning.

Mục tiêu quan trọng nhất:

> Không để cùng một dữ liệu bị các phase hoặc các phiên chat xử lý theo những quy tắc khác nhau.

---

# 2. Trạng thái dữ liệu hiện tại

## Dataset chính

**Beijing Multi-Site Air Quality Data**

Dataset đầy đủ gồm:

- 420.768 observations;
- 12 monitoring sites;
- dữ liệu theo giờ;
- giai đoạn 01/03/2013 – 28/02/2017;
- 6 pollutants;
- 6 meteorological variables;
- có missing values.

## File đã kiểm chứng trực tiếp

```text
PRSA_Data_Wanshouxigong_20130301-20170228.csv
```

Kết quả profiling:

```text
Rows       : 35,064
Columns    : 18
Station    : Wanshouxigong
Start      : 2013-03-01 00:00
End        : 2017-02-28 23:00
Frequency  : hourly
Duplicate timestamps : 0
Missing timestamps   : 0
```

### Trạng thái kiểm chứng

```text
Wanshouxigong   → VERIFIED

11 trạm còn lại → NOT YET PROFILED LOCALLY
```

Không được mặc định 11 file còn lại hoàn toàn giống về chất lượng dữ liệu chỉ vì chúng dùng cùng schema.

---

# 3. Grain của dữ liệu nguồn

Grain cơ bản của PRSA:

> **Một observation tại một trạm trong một giờ.**

Natural key dự kiến:

```text
station + event_time
```

Ví dụ:

```text
Wanshouxigong + 2016-01-01 08:00
```

phải xác định tối đa một observation trong dataset chuẩn hóa.

Đây cũng là grain đang được ưu tiên cho Data Warehouse.

---

# 4. Schema nguồn UCI

Schema file đã kiểm tra:

| Source column | Ý nghĩa | Unit |
|---|---|---|
| `No` | Số thứ tự dòng | - |
| `year` | Năm | - |
| `month` | Tháng | - |
| `day` | Ngày | - |
| `hour` | Giờ | - |
| `PM2.5` | Nồng độ PM2.5 | µg/m³ |
| `PM10` | Nồng độ PM10 | µg/m³ |
| `SO2` | Nồng độ SO₂ | µg/m³ |
| `NO2` | Nồng độ NO₂ | µg/m³ |
| `CO` | Nồng độ CO | µg/m³ |
| `O3` | Nồng độ O₃ | µg/m³ |
| `TEMP` | Nhiệt độ | °C |
| `PRES` | Áp suất | hPa |
| `DEWP` | Nhiệt độ điểm sương | °C |
| `RAIN` | Lượng mưa | mm |
| `wd` | Hướng gió | categorical |
| `WSPM` | Tốc độ gió | m/s |
| `station` | Tên trạm quan trắc | - |

---

# 5. Canonical schema

Raw layer **không đổi tên cột**.

Sau khi chuyển sang processed/staging, sử dụng naming convention thống nhất:

| Source | Canonical |
|---|---|
| `No` | `source_row_no` |
| `year/month/day/hour` | `event_time_local` |
| `PM2.5` | `pm25_ug_m3` |
| `PM10` | `pm10_ug_m3` |
| `SO2` | `so2_ug_m3` |
| `NO2` | `no2_ug_m3` |
| `CO` | `co_ug_m3` |
| `O3` | `o3_ug_m3` |
| `TEMP` | `temperature_c` |
| `PRES` | `pressure_hpa` |
| `DEWP` | `dew_point_c` |
| `RAIN` | `rain_mm` |
| `wd` | `wind_direction` |
| `WSPM` | `wind_speed_m_s` |
| `station` | `station_name` |

Quy ước:

```text
snake_case
lowercase
unit trong tên measure khi hữu ích
```

Không sử dụng tên:

```text
PM2.5
PM 2.5
Temperature
Station Name
```

trong processed/DWH schema.

---

# 6. Xử lý `No`

`No` chỉ là row number của source.

Quy tắc:

```text
Raw       → giữ nguyên
Processed → có thể giữ dưới tên source_row_no để trace
DWH       → không dùng làm business key
ML        → không dùng làm feature
```

Không được dùng `No` làm:

- station identifier;
- time identifier;
- surrogate key;
- predictor.

---

# 7. Timestamp chuẩn

Source lưu thời gian bằng:

```text
year
month
day
hour
```

Trong processed layer phải tạo:

```text
event_time_local
```

Ví dụ:

```text
2013 + 03 + 01 + 08
→
2013-03-01 08:00:00
```

Các cột source ban đầu vẫn được giữ ở Raw.

---

# 8. Timezone

Đây là vấn đề **chưa được phép giả định tùy ý**.

Tài liệu UCI mô tả `year/month/day/hour` nhưng không ghi rõ timezone.

Working assumption hiện tại:

> Timestamp trong PRSA được hiểu như **local wall time tại Beijing** cho đến khi có bằng chứng khác.

Timezone hợp lý về địa lý là:

```text
Asia/Shanghai
UTC+08:00
```

nhưng phải phân biệt:

```text
working assumption
≠
fact đã được UCI document xác nhận
```

Không tự convert UCI sang UTC trong Raw layer.

---

# 9. Open-Meteo timezone

Open-Meteo mặc định có thể trả timestamp theo GMT nếu không chỉ định timezone.

Vì vậy request của dự án **không được bỏ qua timezone**.

Khi quyết định UCI timestamp được xử lý như Beijing local time, request Open-Meteo nên sử dụng cùng timezone:

```text
timezone=Asia/Shanghai
```

Mục tiêu:

```text
UCI 08:00
        ↕
Open-Meteo 08:00
```

không phải:

```text
UCI 08:00
        ↕
Open-Meteo 00:00 UTC
```

Lệch timezone 8 giờ có thể tạo correlation giả và phá toàn bộ mô hình.

---

# 10. Missing timestamp vs missing measurement

Phải phân biệt hai khái niệm.

## Missing timestamp

Một giờ hoàn toàn không tồn tại trong file.

Ví dụ:

```text
10:00
11:00
13:00
```

→ thiếu observation 12:00.

## Missing measurement

Timestamp vẫn tồn tại nhưng một hoặc nhiều sensor value là `NA`.

Ví dụ:

```text
12:00 PM2.5 = NA
```

File Wanshouxigong đã kiểm tra:

```text
Missing timestamp    = 0
Missing measurements > 0
```

Hai loại lỗi này phải được báo cáo riêng.

---

# 11. Missing values đã kiểm chứng

Wanshouxigong:

| Variable | Missing | Tỷ lệ xấp xỉ |
|---|---:|---:|
| PM2.5 | 696 | 1.99% |
| PM10 | 484 | 1.38% |
| SO₂ | 669 | 1.91% |
| NO₂ | 754 | 2.15% |
| CO | 1,297 | 3.70% |
| O₃ | 1,078 | 3.07% |
| TEMP | 19 | 0.05% |
| PRES | 19 | 0.05% |
| DEWP | 19 | 0.05% |
| RAIN | 19 | 0.05% |
| wd | 79 | 0.23% |
| WSPM | 13 | 0.04% |

---

# 12. Missing gap

Không chỉ đếm số lượng `NA`.

Pipeline profiling phải tìm **độ dài chuỗi NA liên tục**.

Wanshouxigong đã phát hiện:

| Variable | Longest observed missing run |
|---|---:|
| PM2.5 | 43 giờ |
| PM10 | 43 giờ |
| SO₂ | 93 giờ |
| NO₂ | 93 giờ |
| CO | 93 giờ |
| O₃ | 93 giờ |
| TEMP | 6 giờ |
| PRES | 6 giờ |
| DEWP | 6 giờ |
| RAIN | 6 giờ |
| wd | 5 giờ |
| WSPM | 5 giờ |

Điều này chứng minh:

> Không thể dùng cùng một interpolation rule cho toàn bộ missing data.

---

# 13. Missing strategy

Chưa khóa thuật toán imputation trước khi profile đủ 12 trạm.

Quy trình bắt buộc:

```text
Detect
↓
Classify gap
↓
Understand variable
↓
Select treatment
↓
Validate impact
```

Không mặc định:

```text
NA → interpolate
```

---

# 14. Quy tắc theo loại dữ liệu

## Pollutant target

Nếu:

```text
pm25(t+1)
```

bị missing thì observation đó **không có target thật**.

Mặc định:

> Không tự tạo target PM2.5 bằng interpolation rồi dùng nó như ground truth để đánh giá model.

Các row thiếu target có thể bị loại khỏi supervised training/evaluation.

## Predictor missing

Có thể xem xét:

- interpolation;
- forward fill giới hạn;
- **external enrichment** (với weather: Open-Meteo sau UCI — xem §24.3 / §44);
- model-based imputation;
- missing indicator;
- loại observation.

Nhưng phải dựa trên độ dài gap và feature.

**Lưu ý:** chiến lược fill weather từ API **không thay** việc xử lý missing pollutant / target (xem mục Pollutant target ở trên).

## Dashboard / Historical Analysis

Không nhất thiết phải impute tất cả.

Trong nhiều biểu đồ lịch sử, giữ `NULL` có thể trung thực hơn việc tạo dữ liệu giả.

---

# 15. Không interpolate xuyên qua data split

Ví dụ:

```text
Train | Test
```

Không được nội suy một điểm ở cuối Train bằng dữ liệu thuộc Test.

Tương tự:

- rolling calculation;
- scaler;
- imputer;
- feature engineering;

không được học thông tin từ tương lai.

---

# 16. Extreme values

Wanshouxigong có các giá trị lớn như:

```text
PM2.5 max = 999 µg/m³
PM10  max = 961 µg/m³
CO    max = 9800 µg/m³
```

Không được mặc định:

```text
large value = outlier = delete
```

Ô nhiễm cao có thể chính là signal quan trọng nhất của bài toán.

---

# 17. Quy trình kiểm tra extreme value

Khi phát hiện giá trị cực đoan:

```text
Value
 ↓
Kiểm tra giờ trước/sau
 ↓
Kiểm tra pollutant khác
 ↓
Kiểm tra weather
 ↓
Kiểm tra trạm khác cùng thời điểm
 ↓
Kiểm tra source/documentation
 ↓
Decision
```

Các decision hợp lệ có thể là:

```text
VALID_EXTREME
SUSPECT
INVALID
UNKNOWN
```

Nếu chưa đủ bằng chứng:

> giữ dữ liệu và đánh dấu, không tự xóa.

---

# 18. Physical validation

Các rule an toàn có thể kiểm tra:

```text
PM2.5 >= 0
PM10  >= 0
SO2   >= 0
NO2   >= 0
CO    >= 0
O3    >= 0
RAIN  >= 0
WSPM  >= 0
```

Nếu vi phạm:

```text
do not silently fix
```

Record phải được:

- báo lỗi;
- đánh dấu;
- hoặc đưa vào quarantine để điều tra.

Không đặt hard upper limit tùy ý trước khi nghiên cứu domain.

---

# 19. Wind direction

Wanshouxigong chứa 16 hướng:

```text
N
NNE
NE
ENE
E
ESE
SE
SSE
S
SSW
SW
WSW
W
WNW
NW
NNW
```

Đây là biến categorical có tính **circular**.

Không nên encode trực tiếp:

```text
N = 1
NNE = 2
...
NNW = 16
```

rồi đưa vào model như số tuyến tính.

Các hướng xử lý có thể gồm:

- one-hot encoding;
- chuyển thành góc;
- sin/cos encoding.

Quyết định cuối nằm trong Mining/Data Guide extension.

---

# 20. Source station

Mỗi row phải có `station_name`.

Kiểm tra bắt buộc với mỗi source file:

```text
station IS NOT NULL
```

Nếu file được thiết kế cho một station:

```text
COUNT(DISTINCT station) = 1
```

Tên station phải được trim và canonicalize nhưng Raw value phải được bảo toàn.

---

# 21. Station ID

Không dùng trực tiếp station name làm khóa kỹ thuật cuối cùng của DWH.

Reference table dự kiến:

```text
station_id
station_code
station_name
latitude
longitude
district
metadata_source
```

Ví dụ `station_id` có thể là surrogate key trong Warehouse.

---

# 22. Station location

UCI CSV / trang dataset **không** chứa tọa độ.

Seed local:

```text
data/raw/reference/stations.csv
```

| Trường | Trạng thái |
|---|---|
| `latitude`, `longitude` | Có — từ Foreback et al. 2022 ACP Supplement Table S1 (12 MEP sites) |
| `district` | Có — Skyviewor station list (区县) + đối chiếu PMC9510312; **không** suy từ tên trạm |
| `station_code` / `station_name` | Khớp tên `station` trong UCI |

Nguồn tọa độ:

```text
https://acp.copernicus.org/articles/22/11089/2022/acp-22-11089-2022-supplement.pdf
```

Nguồn district (ghi trong CSV: `district_source` / `district_source_url`):

```text
https://docs.datastation.skyviewor.com/data-query/china-pollution/pollution-stations-list/
https://pmc.ncbi.nlm.nih.gov/articles/PMC9510312/
```

Ví dụ mapping đặc biệt trong seed: `Dingling` → district `Changping`.

`coordinate_status=LITERATURE`. Seed dùng cho Open-Meteo join và map; citation nằm trong CSV/metadata.

Không:

- lấy tâm quận thay tọa độ trạm;
- dùng coordinate của tên địa danh gần giống;
- sinh tọa độ giả;
- gán district chỉ theo tên trạm;
- trộn nhiều bảng tọa độ khác nhau cho cùng một trạm mà không document.

---

# 23. Nguồn Open-Meteo

Nguồn:

**Open-Meteo Historical Weather API**

Đây là dữ liệu gridded/reanalysis, không phải measurement từ chính sensor PRSA.

Do đó:

```text
UCI weather
≠
Open-Meteo weather
```

và không nên kỳ vọng hai nguồn giống nhau tuyệt đối.

UCI weather được ghép từ weather station gần air-quality site.

Open-Meteo historical data được xây dựng từ các reanalysis/model grid.

Mục tiêu là **tích hợp/enrichment**, không phải chứng minh một nguồn sai chỉ vì hai giá trị lệch nhau.

---

# 24. Biến Open-Meteo ưu tiên thử nghiệm

Không lấy hàng chục biến ngay từ đầu.

## 24.1. Relative humidity — derive ưu tiên hơn API

UCI **không có** cột RH trực tiếp, nhưng có `TEMP` và `DEWP`.

**Working preference:** derive `relative_humidity_pct` trong ETL/processing từ `TEMP` + `DEWP` (công thức khí tượng chuẩn), ghi rõ đây là biến dẫn xuất.

Không ưu tiên lấy `relative_humidity_2m` từ Open-Meteo chỉ để có RH — trừ khi cần đối chiếu derive vs API.

## 24.2. Enrichment chính từ Open-Meteo

Candidate **ưu tiên đưa vào pipeline enrichment**:

```text
cloud_cover
```

Lý do: UCI không có; có thể hữu ích khi phân tích tương quan với pollutant (PM vs O₃ có thể khác hướng). Không mặc định kết luận nhân quả.

Tối đa thêm **một** biến phụ sau EDA nếu có tín hiệu, ví dụ:

```text
shortwave_radiation
weather_code
```

## 24.3. Biến trùng UCI — fill missing (source priority)

Gọi và lưu các biến chồng với UCI để **bổ sung khi UCI thiếu** và (tuỳ chọn) đối chiếu nguồn:

```text
temperature_2m
dew_point_2m
surface_pressure
rain
wind_speed_10m
wind_direction_10m
```

Working preference khi build cột analytical:

```text
weather_final = UCI          nếu UCI không missing
              = Open-Meteo   nếu UCI missing và API có giá trị
              = null/impute  nếu cả hai thiếu
```

Nên giữ:

- giá trị theo từng nguồn ở processed hoặc cột riêng khi cần đối chiếu;
- **flag / lineage** cho biết measure analytical đến từ nguồn nào.

Fact/mart nhận:

- weather đã resolve (ưu tiên UCI);
- enrichment `cloud_cover` (và biến phụ nếu có).

Pollutant missing không fill bằng Open-Meteo.

Khóa chi tiết sau Phase 5 (đo tỷ lệ fill thực tế; seed tọa độ đã có tại `data/raw/reference/stations.csv`).

---

# 25. Chuẩn hóa unit Open-Meteo

### Temperature

```text
UCI TEMP          = °C
Open-Meteo        = °C
```

Giữ °C.

### Rain

```text
UCI RAIN          = mm
Open-Meteo rain   = mm
```

### Wind

UCI:

```text
WSPM = m/s
```

Open-Meteo mặc định có thể sử dụng km/h.

Do đó API phải:

```text
request wind speed in m/s
```

hoặc pipeline phải convert rõ ràng.

Không join/compare:

```text
km/h ↔ m/s
```

mà không chuẩn hóa.

### Pressure

UCI chỉ mô tả `PRES` là pressure (hPa).

Open-Meteo phân biệt:

```text
surface_pressure
pressure_msl
```

Không mặc định `PRES` bằng một trong hai cho tới khi semantics được kiểm tra.

---

# 26. Naming weather theo source

Trong processed layer **không ghi đè** weather UCI bằng Open-Meteo.

Giữ cột theo nguồn (để đối chiếu và lineage):

```text
uci_temperature_c
uci_pressure_hpa
uci_dew_point_c
uci_rain_mm
uci_wind_direction
uci_wind_speed_m_s

om_temperature_c
om_dew_point_c
om_surface_pressure_hpa
om_rain_mm
om_wind_speed_m_s
om_wind_direction_deg
om_cloud_cover_pct
```

Cột analytical đã resolve (`weather_final` / tương đương) và flag nguồn được tạo **sau** bước này, theo rule §24.3:

```text
UCI → Open-Meteo fill khi UCI missing → impute/flag nếu cả hai thiếu
```

`relative_humidity_pct` derive từ TEMP/DEWP **đã resolve**, không lấy từ `om_*` làm mặc định (xem §24.1).

---

# 27. Join UCI ↔ Open-Meteo

Join candidate:

```text
station
+
event_time_local
```

Nhưng station chỉ join được với Open-Meteo sau khi có:

```text
station → latitude/longitude
```

Flow đúng:

```text
Station reference
      ↓
Coordinates
      ↓
Open-Meteo request
      ↓
Weather per station/hour
      ↓
Join with PRSA
```

Không gọi một weather coordinate duy nhất cho toàn Beijing rồi gán cho cả 12 trạm mà không đánh giá hậu quả.

---

# 28. Open-Meteo request metadata

Mỗi lần ingestion API phải lưu metadata đủ để tái tạo request.

Tối thiểu:

```text
station
requested_latitude
requested_longitude
returned_latitude
returned_longitude
timezone
start_date
end_date
weather_model
hourly_variables
units
request_time
HTTP status
source
```

Không chỉ lưu mảng weather rồi mất context của request.

---

# 29. Data lineage

Mỗi dataset processed phải truy ngược được về nguồn.

Đối với CSV:

```text
source_file_name
source_system
ingestion_time
```

Khuyến nghị thêm:

```text
file_size
checksum
```

Đối với API:

```text
source_system
request_parameters
request_time
raw_object_path
```

Mục tiêu:

> Biết chính xác một row trong pipeline đến từ đâu và có thể tái xử lý dữ liệu.

---

# 30. Data Lake rules

Data Lake dự kiến dùng **MinIO**.

## Raw layer

Raw là immutable.

Ví dụ:

```text
raw/
├── uci/
│   └── air_quality/
├── openmeteo/
│   └── historical_weather/
└── reference/
    └── stations/
```

Raw giữ dữ liệu gần source nhất.

Không:

```text
dropna
rename columns
convert pollutants
overwrite original file
```

trong Raw.

---

# 31. Processed layer

Processed chứa dữ liệu đã:

- parse;
- rename;
- type cast;
- chuẩn hóa timestamp;
- chuẩn hóa unit;
- validate schema;
- bổ sung lineage;
- xử lý data quality theo rule đã phê duyệt.

Candidate format:

```text
Parquet
```

vì:

- có schema;
- hiệu quả cho dữ liệu dạng bảng;
- nhỏ hơn CSV;
- thuận lợi đọc theo analytics pipeline.

Tuy nhiên format cuối sẽ được xác nhận khi triển khai MinIO.

---

# 32. PostgreSQL staging

Các bảng staging dự kiến:

```text
staging.air_quality_hourly
staging.weather_openmeteo_hourly
staging.station_reference
```

Staging nên còn đủ thông tin source để kiểm tra.

Không ép staging thành Star Schema.

Vai trò staging:

> bridge giữa processed data và dbt/DWH.

---

# 33. Data Warehouse hand-off

`DATA_GUIDE.md` không quyết định schema DWH cuối cùng.

Nhưng dữ liệu bàn giao cho DWH phải đáp ứng:

```text
station identity resolved
timestamp standardized
units standardized
schema validated
duplicates handled
data-quality status known
lineage retained
```

Sau đó `DWH_DESIGN` mới quyết định Fact/Dimension.

---

# 34. Duplicate policy

Duplicate được kiểm tra trên:

```text
station + event_time_local
```

Nếu duplicate xuất hiện:

> không dùng `drop_duplicates()` rồi giữ row đầu tiên một cách im lặng.

Phải kiểm tra:

- hai row có giống hoàn toàn không;
- source file;
- pollutant values;
- ingestion duplicate;
- source duplicate;
- version của dataset.

Sau đó mới xác định rule.

---

# 35. Schema validation bắt buộc

Mỗi PRSA source file phải được kiểm tra:

```text
required columns exist
types parse correctly
station not null
timestamp parseable
timestamp within expected dataset period
station+timestamp uniqueness
```

Ngoài ra báo cáo:

```text
row_count
start_time
end_time
missing_timestamp_count
duplicate_count
missing_count per column
missing_percentage per column
longest_missing_run per column
min/max
negative_count
```

---

# 36. Automated profiling output

Khi ingest toàn bộ dataset, tạo một profiling artifact.

Ví dụ:

```text
data_profile_station.csv
```

có thể chứa:

```text
station
row_count
start_time
end_time
duplicate_count
missing_hour_count

pm25_missing_pct
pm25_longest_gap
pm25_min
pm25_max

...

weather_missing_pct
```

Ngoài ra tạo report tổng hợp toàn dataset.

Không dựa vào kiểm tra bằng mắt cho 12 file.

---

# 37. Data-quality flags

Không nhất thiết sửa mọi vấn đề ngay.

Có thể bổ sung các flag như:

```text
has_missing_pollutant
has_missing_weather
is_extreme_pm25
data_quality_status
```

Các flag giúp:

- dashboard;
- debugging;
- model filtering;
- audit.

Rule cụ thể sẽ được quyết định sau profiling.

---

# 38. Raw vs analytical truth

Có hai khái niệm khác nhau.

### Raw truth

Dữ liệu chính xác như source cung cấp.

### Analytical dataset

Dữ liệu được:

- clean;
- transform;
- impute nếu cần;
- feature engineer;

để phục vụ một mục tiêu nhất định.

Không được overwrite Raw bằng Analytical data.

---

# 39. Dataset cho dashboard và ML có thể khác nhau

Không mặc định một bảng xử lý duy nhất dùng cho mọi mục đích.

Ví dụ:

### Dashboard

Có thể ưu tiên dữ liệu lịch sử thật, giữ một số `NULL`.

### Machine Learning

Có thể cần:

- complete target;
- lag;
- rolling feature;
- encoding;
- missing treatment.

Do đó:

```text
DWH analytical data
        ↓
    ┌───┴────┐
    ↓        ↓
Dashboard   ML dataset
```

là hợp lệ.

---

# 40. ML feature dataset

ML dataset không được coi là Data Warehouse.

Nó là downstream dataset được tạo từ dữ liệu đã kiểm soát.

Dự kiến grain:

```text
station + prediction_origin_time
```

Target:

```text
pm25(t+1h)
```

Candidate features:

```text
station
hour
day_of_week
month
season

pm25 lag
weather
rolling statistics
other historical pollutant features
```

Feature list cuối chưa chốt.

---

# 41. Train/test integrity

Khi tạo ML dataset:

```text
feature_time <= prediction_origin_time
```

Target:

```text
target_time > prediction_origin_time
```

Không sử dụng feature đến từ tương lai.

Scalers/imputers/encoders phải được fit đúng theo training data.

---

# 42. Data-quality evidence

Mỗi bước cleaning đáng kể phải trả lời được:

```text
Before?
After?
Rule?
Reason?
Rows affected?
Impact?
```

Ví dụ không chỉ ghi:

> “Đã xử lý missing.”

Mà cần có khả năng chứng minh:

```text
PM2.5 missing before : x%
PM2.5 missing after  : y%

Method:
...

Rows affected:
...
```

Đây sẽ là evidence hữu ích cho báo cáo cuối và bảo vệ.

---

# 43. Không làm sạch quá mức

Đặc biệt với bài toán ô nhiễm:

> Extreme events là dữ liệu có giá trị.

Một dataset sau cleaning mà:

- quá mượt;
- không còn pollution peaks;
- distribution thay đổi mạnh;

có thể đã bị xử lý sai.

Cleaning phải giảm lỗi, không được xóa đặc tính thực của hiện tượng.

---

# 44. Source priority

### Air pollution

Primary source:

```text
UCI / PRSA
```

### UCI weather

Là nguồn khí tượng đi kèm dataset và có giá trị thực.

### Open-Meteo

Là:

```text
external enrichment / second source
```

không mặc định thay thế UCI weather.

Working priority cho **weather trùng**:

```text
1. UCI (primary)
2. Open-Meteo (fill khi UCI missing)
3. imputation / flag (nếu cả hai thiếu)
```

Đồng thời Open-Meteo cung cấp biến UCI không có (ưu tiên `cloud_cover`).

Nếu hai nguồn **cùng có giá trị nhưng lệch nhau**:

> điều tra / ghi nhận; không tự chọn Open-Meteo vì “API mới hơn” khi UCI đã có đo.

---

# 45. Vấn đề lịch sử dữ liệu

PRSA chỉ có:

```text
2013–2017
```

Do đó kết quả dự án mô tả:

> Pattern trong dataset Beijing 2013–2017.

Không kết luận:

> “Đây là tình trạng ô nhiễm Bắc Kinh hiện nay.”

Model cũng không được quảng bá là model dự báo chất lượng không khí năm 2026 nếu chưa retrain bằng dữ liệu phù hợp.

---

# 46. Quy tắc reproducibility

Source dataset phải được version/freeze.

Không để pipeline phụ thuộc vào:

```text
một file tải lại sau này nhưng nội dung đã thay đổi
```

Raw dataset được lưu vào Data Lake.

API response cũng nên được lưu Raw để lần chạy sau không phụ thuộc hoàn toàn vào API bên ngoài.

---

# 47. Quy tắc cho AI khi làm dữ liệu

Trước khi đề xuất xử lý dữ liệu, AI phải kiểm tra:

1. biến đang xử lý là pollutant, weather hay metadata;
2. đó là Raw, Processed, DWH hay ML dataset;
3. mục tiêu xử lý là gì;
4. có nguy cơ data leakage không;
5. rule đã được kiểm chứng chưa.

AI được chủ động đề xuất phương pháp tốt hơn.

Nhưng AI không được:

- tự xóa outlier;
- tự nội suy gap dài;
- tự đoán timezone;
- tự sinh tọa độ;
- tự đổi unit;
- tự thêm source;
- tự coi correlation là causation;
- tự dùng future data cho forecasting.

---

# 48. Những việc chưa được chốt

Các quyết định sau phải dựa vào profiling hoặc thử nghiệm.

## Full dataset

- profiling đủ 12 station;
- kiểm tra row count từng station;
- kiểm tra timestamp continuity;
- kiểm tra duplicates;
- missing pattern giữa các station.

## Missing

- ngưỡng thế nào là gap ngắn/dài;
- imputation theo từng variable;
- treatment của missing wind direction.

## Extreme values

- rule xác định suspect value;
- có winsorization cho model hay không;
- có transform target hay không.

## Weather

- Open-Meteo model/grid cuối;
- variables cuối *(working preference: cloud_cover; UCI→Open-Meteo fill; RH derive — xem §24)*;
- role cuối của Open-Meteo sau POC;
- semantics của UCI pressure;
- công thức derive RH và kiểm tra biên (TEMP/DEWP missing).

## Station

- coordinates *(seed LITERATURE: `data/raw/reference/stations.csv` — ACP 2022 Supp. Table S1)*;
- district *(đã gán; nguồn ghi trong `stations.csv`)*;
- có giữ một nguồn tọa độ duy nhất (ACP S1) hay bổ sung đối chiếu.

## Storage

- final MinIO bucket names;
- Parquet partition strategy;
- retention/version convention.

---

# 49. Data checklist trước khi thiết kế DWH

Không thiết kế DWH cuối cùng cho đến khi có câu trả lời cho:

```text
[ ] Đủ inventory 12 file chưa?
[ ] Grain đã xác nhận chưa?
[ ] Timestamp continuity đã kiểm tra chưa?
[ ] Duplicate đã kiểm tra chưa?
[ ] Missing profile đủ chưa?
[ ] Station names chuẩn chưa?
[ ] Units chuẩn chưa?
[ ] Timezone strategy rõ chưa?
[ ] Open-Meteo role rõ chưa?
[ ] Station metadata đủ chưa?
```

Không nhất thiết mọi missing phải được xử lý xong, nhưng phải **hiểu chúng**.

---

# 50. Data checklist trước khi train model

```text
[ ] Target được định nghĩa rõ
[ ] Forecast horizon được định nghĩa
[ ] Chronological split
[ ] Không future leakage
[ ] Target missing được xử lý
[ ] Feature missing strategy rõ
[ ] Encoding chỉ fit từ train
[ ] Scaling chỉ fit từ train
[ ] Baseline tồn tại
[ ] Extreme-value strategy được ghi lại
[ ] Metric được chốt
```

---

# 51. Output của Data Preparation Phase

Phase dữ liệu được xem là hoàn thành khi có:

```text
1. Full raw UCI dataset trong Data Lake
2. Station inventory
3. Profiling đủ 12 trạm
4. Data-quality report
5. Timestamp standard
6. Canonical schema
7. Station reference
8. Open-Meteo thử nghiệm thành công
9. Quyết định chính thức về missing
10. Processed dataset reproducible
```

Sau đó mới chuyển trọng tâm sang DWH modeling.

---

# 52. Nguyên tắc cuối

Dữ liệu trong dự án này không được xử lý với tư duy:

```text
“Làm sao cho dataset sạch để model chạy được?”
```

Mà phải là:

```text
“Làm sao giữ đúng ý nghĩa dữ liệu,
biết rõ mình đã thay đổi gì,
và tạo dataset phù hợp cho từng mục đích?”
```

Raw data phải được bảo toàn.

Cleaning phải có lý do.

Missing phải được hiểu trước khi điền.

Extreme values phải được điều tra trước khi loại bỏ.

Dữ liệu tương lai không được phép lọt vào forecasting pipeline.

Và mọi transformation quan trọng phải có khả năng truy ngược về source.